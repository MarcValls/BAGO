"""handlers_chat.py \u2014 POST /chat for the BAGO HTTP bridge.

Migrated from bridge._handle_chat on 2026-06-24. Same semantics:
  - 400 if 'message' missing
  - 503 if SessionManager not wired
  - threaded call with timeout watchdog
  - shadow event on every completed action (success or timeout)
  - 504 with chat_timeout_s + chat_latency_ms + timed_out=True on timeout
  - 200 with response/session_id/provider/model/history_count on success

The threading concern lives entirely in this module \u2014 callers just
get a RequestContext. Uses RequestContext for everything else.
"""
from __future__ import annotations
import threading
import time
import inspect
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _inject_manager_context(message: str, body: dict[str, Any]) -> str:
    """Si `body['manager_context']` está presente y completo, prefijar
    el mensaje con un bloque [BAGO_CTX:...] para que el modelo sepa en
    qué vista del gestor se encuentra.
    """
    ctx = body.get("manager_context")
    if not (ctx and isinstance(ctx, dict)):
        return message
    parts: list[str] = []
    view_label = (ctx.get("viewLabel") or ctx.get("view") or "").strip()
    if view_label:
        parts.append(f"Vista activa del gestor: {view_label}")
    installs = ctx.get("installations")
    if installs not in (None, "?"):
        parts.append(f"{installs} instalaciones")
    pieces = ctx.get("pieces")
    if pieces not in (None, "?"):
        parts.append(f"{pieces} piezas")
    if not parts:
        return message
    return f"[BAGO_CTX:{'; '.join(parts)}]\n{message}"


def _send_with_watchdog(ctx, ai_message: str, timeout_s: float, *, internal: bool = False) -> tuple[str | None, dict | None, float]:
    """Run mgr.send(ai_message) with a renewable inactivity timeout."""
    started = time.time()
    started_monotonic = time.monotonic()
    method = ctx.session_mgr.send_internal if internal else ctx.session_mgr.send
    try:
        signature = inspect.signature(method)
        accepts_callback = "activity_callback" in signature.parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
    except (TypeError, ValueError):
        accepts_callback = False
    if timeout_s <= 0:
        try:
            return method(ai_message), None, (time.time() - started) * 1000
        except Exception as exc:
            return None, {"ok": False, "error": f"Error interno: {exc}"}, (time.time() - started) * 1000

    done = threading.Event()
    wake = threading.Event()
    worker_result: dict[str, Any] = {}
    worker_exc: dict[str, BaseException] = {}
    activity_lock = threading.Lock()
    last_activity = time.monotonic()

    def _touch() -> None:
        nonlocal last_activity
        with activity_lock:
            last_activity = time.monotonic()
        wake.set()

    def _runner() -> None:
        try:
            if accepts_callback:
                worker_result["response"] = method(ai_message, activity_callback=_touch)
            else:
                worker_result["response"] = method(ai_message)
        except BaseException as exc:  # propagate after the wait
            worker_exc["exc"] = exc
        finally:
            done.set()
            wake.set()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    hard_timeout_s = max(timeout_s * 10.0, 1800.0)
    worker_heartbeat_s = max(min(timeout_s / 3.0, 30.0), 0.01)
    timeout_reason = ""
    while not done.is_set():
        now = time.monotonic()
        with activity_lock:
            idle_for = now - last_activity
        total_for = now - started_monotonic
        if accepts_callback and t.is_alive() and idle_for >= worker_heartbeat_s:
            # A cooperative manager owns the provider process and its
            # cancellation policy. Its live worker is a valid request-level
            # heartbeat even when the provider emits no token events while
            # reasoning or initializing.
            _touch()
            continue
        if idle_for >= timeout_s:
            timeout_reason = "inactivity"
            break
        if total_for >= hard_timeout_s:
            timeout_reason = "total"
            break
        wake.wait(timeout=min(timeout_s - idle_for, hard_timeout_s - total_for, 0.25))
        wake.clear()

    if timeout_reason:
        detail = (
            f"El modelo no mostr\u00f3 actividad durante {timeout_s:g}s (timeout de inactividad)."
            if timeout_reason == "inactivity"
            else f"El modelo super\u00f3 el l\u00edmite total de {hard_timeout_s:g}s."
        )
        return None, {
            "ok": False,
            "error": detail,
            "chat_timeout_s": timeout_s,
            "chat_timeout_mode": timeout_reason,
            "chat_total_timeout_s": hard_timeout_s,
            "timed_out": True,
        }, (time.time() - started) * 1000

    if worker_exc:
        return None, {"ok": False, "error": f"Error interno: {worker_exc['exc']}"}, (time.time() - started) * 1000
    return worker_result.get("response"), None, (time.time() - started) * 1000


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from request_context import build_context
    from event_bus import emit
    from error_payload_filter import (
        extract_diagnostic,
        is_canonical_error_payload,
        rewrite_to_user_friendly,
    )

    ctx = build_context(handler)
    if ctx.session_mgr is None:
        ctx.send_json(503, {"error": "SessionManager no disponible"})
        return

    raw_message = body.get("message", "")
    if not isinstance(raw_message, str) or not raw_message.strip():
        ctx.send_json(400, {"error": "Campo 'message' requerido"})
        return

    message = raw_message
    ai_message = _inject_manager_context(message, body)
    channel = ctx.channel(body)
    internal = body.get("internal") is True
    pre_state = ctx.session_mgr.status()
    timeout_s = float(ctx.chat_timeout_s or 0.0)

    response, error_payload, elapsed_ms = _send_with_watchdog(ctx, ai_message, timeout_s, internal=internal)

    if error_payload is not None:
        error_payload.setdefault("provider", ctx.session_mgr.provider)
        error_payload.setdefault("model", ctx.session_mgr.model)
        error_payload.setdefault("session_id", ctx.session_mgr.session_id)
        # Timeout or worker exception \u2014 still record the shadow event.
        ctx.record_shadow(
            action_kind="internal_chat" if internal else "chat",
            channel=channel,
            payload={"message": message},
            pre_state=pre_state,
            post_state=ctx.session_mgr.status(),
            result={**error_payload, "chat_latency_ms": elapsed_ms},
            elapsed_ms=elapsed_ms,
        )
        if error_payload.get("timed_out"):
            error_payload["chat_latency_ms"] = elapsed_ms
            ctx.send_json(504, error_payload)
            emit("chat.timeout", {"session_id": ctx.session_mgr.session_id, "timeout_s": timeout_s})
        else:
            ctx.send_json(500, error_payload)
            emit("chat.failed", {"session_id": ctx.session_mgr.session_id, "error": error_payload.get("error", "")})
        return

    try:
        # Intercept BAGO's internal canonical error payload (emitted by
        # `_canonical_task_failure_payload` when the model fails the JSON
        # contract). It must never reach the user-facing JSON response.
        leaked_error: dict[str, Any] | None = None
        if is_canonical_error_payload(response):
            leaked_error = {
                "response": rewrite_to_user_friendly(response),
                "diagnostic": extract_diagnostic(response),
            }
            user_response = leaked_error["response"]
        else:
            user_response = response

        current_receipt = ctx.session_mgr.last_receipt
        # The receipt is canonical session evidence. Some adapters update the
        # existing object in place, so object identity cannot determine whether
        # it belongs in the public response. Internal turns remain private.
        receipt_payload = current_receipt.to_dict() if current_receipt is not None and not internal else None
        receipt_metadata = receipt_payload.get("metadata", {}) if isinstance(receipt_payload, dict) else {}
        response_state = "done" if internal else str(getattr(ctx.session_mgr, "last_response_state", "done") or "done")
        payload = {
            "ok": True,
            "response": user_response,
            "session_id": ctx.session_mgr.session_id,
            "provider": ctx.session_mgr.provider,
            "model": ctx.session_mgr.model,
            "history_count": len(ctx.session_mgr.store.get_history()),
            "chat_latency_ms": elapsed_ms,
            "context_receipt": receipt_payload,
            "response_state": response_state,
            "clarification": None if internal else getattr(ctx.session_mgr, "last_clarification", None),
            "task_contract": receipt_metadata.get("task_contract") if isinstance(receipt_metadata, dict) else None,
            "internal": internal,
            "binding": ctx.session_mgr.status(),
        }
        if leaked_error is not None:
            payload["diagnostic"] = leaked_error["diagnostic"]
        if timeout_s > 0:
            payload["chat_timeout_s"] = timeout_s
        ctx.record_shadow(
            action_kind="internal_chat" if internal else "chat",
            channel=channel,
            payload={"message": message},
            pre_state=pre_state,
            post_state=ctx.session_mgr.status(),
            result=payload,
            elapsed_ms=elapsed_ms,
        )
        ctx.send_json(200, payload)
        emit("chat.completed", {
            "session_id": ctx.session_mgr.session_id,
            "provider": ctx.session_mgr.provider,
            "model": ctx.session_mgr.model,
            "latency_ms": elapsed_ms,
            "history_count": payload["history_count"],
            "has_receipt": bool(payload.get("context_receipt")),
        })
        if payload.get("context_receipt"):
            emit("evidence.created", {
                "receipt_id": payload["context_receipt"].get("receipt_id") or payload["context_receipt"].get("envelope_id"),
                "envelope_id": payload["context_receipt"].get("envelope_id"),
                "state": payload["context_receipt"].get("state", "unknown"),
                "session_id": ctx.session_mgr.session_id,
            })
    except Exception:
        payload = {
            "ok": False,
            "error": "Error interno al procesar el mensaje",
            "provider": ctx.session_mgr.provider,
            "model": ctx.session_mgr.model,
            "session_id": ctx.session_mgr.session_id,
        }
        ctx.record_shadow(
            action_kind="chat",
            channel=channel,
            payload={"message": message},
            pre_state=pre_state,
            post_state=ctx.session_mgr.status(),
            result=payload,
            elapsed_ms=elapsed_ms,
        )
        ctx.send_json(500, payload)
        emit("chat.failed", {"session_id": ctx.session_mgr.session_id, "error": payload["error"]})

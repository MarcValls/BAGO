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
import copy
import time
from contextlib import nullcontext
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


def _capture_turn_state(manager, *, internal: bool) -> dict[str, Any]:
    receipt = getattr(manager, "last_receipt", None)
    receipt_payload = receipt.to_dict() if receipt is not None and not internal else None
    metadata = receipt_payload.get("metadata", {}) if isinstance(receipt_payload, dict) else {}
    store = getattr(manager, "store", None)
    status = getattr(manager, "status", None)
    history = getattr(store, "get_history", None)
    return copy.deepcopy({
        "session_id": getattr(manager, "session_id", ""),
        "provider": getattr(manager, "provider", ""),
        "model": getattr(manager, "model", ""),
        "conversation_id": getattr(store, "active_conversation_id", None),
        "history_count": len(history()) if callable(history) else 0,
        "context_receipt": receipt_payload,
        "response_state": "done" if internal else str(getattr(manager, "last_response_state", "done") or "done"),
        "clarification": None if internal else getattr(manager, "last_clarification", None),
        "task_contract": metadata.get("task_contract") if isinstance(metadata, dict) else None,
        "internal": internal,
        "binding": status() if callable(status) else {},
    })


def _send_with_watchdog(
    ctx,
    ai_message: str,
    timeout_s: float,
    *,
    internal: bool = False,
    turn_id: str = "",
    conversation_id: str | None = None,
    conversation_bound: bool = False,
) -> tuple[str | None, dict | None, float]:
    """Timeout stops waiting, not execution; return an idempotent operation ID."""
    from chat_turns import turn_store
    started = time.monotonic()
    store = getattr(ctx.session_mgr, "store", None)
    scope = getattr(store, "conversation_scope", None)
    if not conversation_bound:
        conversation_id = getattr(store, "active_conversation_id", None)

    def send_bound():
        with scope(conversation_id) if callable(scope) else nullcontext():
            method = ctx.session_mgr.send_internal if internal else ctx.session_mgr.send
            response = method(ai_message)
            return response, _capture_turn_state(ctx.session_mgr, internal=internal)

    turn = turn_store(ctx.session_mgr).get_or_start(
        ai_message, internal, conversation_id, send_bound, turn_id=turn_id,
    )
    ctx.chat_turn = turn
    finished = turn.done.wait(timeout=timeout_s if timeout_s > 0 else None)
    elapsed = (time.monotonic() - started) * 1000
    if not finished:
        return None, {
            "ok": False,
            "error": "La espera expiró; el turno sigue en curso. Consulta el mismo turn_id; no inicies otro turno.",
            "chat_timeout_s": timeout_s,
            "timed_out": True,
            "response_state": "running",
            "turn_id": turn.turn_id,
            "conversation_id": turn.conversation_id,
            "retry_with_same_turn_id": True,
        }, elapsed
    if turn.error:
        return None, {**turn.error, "turn_id": turn.turn_id, "response_state": "failed"}, turn.elapsed_ms
    return turn.response, None, turn.elapsed_ms


def _handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
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

    from chat_turns import ChatTurnError, turn_store
    turn_id = str(body.get("turn_id") or "").strip()
    raw_message = body.get("message", "")
    internal = body.get("internal") is True
    turn_conversation_id = None
    if turn_id:
        try:
            previous = turn_store(ctx.session_mgr).lookup(turn_id)
        except ChatTurnError as exc:
            ctx.send_json(404, {"ok": False, "code": exc.code, "error": str(exc), "turn_id": turn_id})
            return
        if "conversation_id" in body and body.get("conversation_id") != previous.conversation_id:
            ctx.send_json(409, {
                "ok": False,
                "code": "chat_turn_request_mismatch",
                "error": "El turno pertenece a otra conversación.",
                "turn_id": turn_id,
            })
            return
        turn_conversation_id = previous.conversation_id
        # A poll may contain only turn_id. Supplied content must still match.
        if "message" not in body:
            raw_message = previous.message
            internal = previous.internal
            ai_message = previous.message
        else:
            ai_message = _inject_manager_context(raw_message, body) if isinstance(raw_message, str) else ""
    else:
        ai_message = _inject_manager_context(raw_message, body) if isinstance(raw_message, str) else ""
    if not isinstance(raw_message, str) or not raw_message.strip():
        ctx.send_json(400, {"error": "Campo 'message' requerido"})
        return

    message = raw_message
    channel = ctx.channel(body)
    pre_state = ctx.session_mgr.status()
    timeout_s = float(ctx.chat_timeout_s or 0.0)

    try:
        response, error_payload, elapsed_ms = _send_with_watchdog(
            ctx,
            ai_message,
            timeout_s,
            internal=internal,
            turn_id=turn_id,
            conversation_id=turn_conversation_id,
            conversation_bound=bool(turn_id),
        )
    except ChatTurnError as exc:
        ctx.send_json(404 if exc.code == "chat_turn_not_found" else 409, {
            "ok": False, "code": exc.code, "error": str(exc), "turn_id": exc.turn_id,
            "response_state": "running" if exc.code == "chat_turn_in_progress" else "blocked",
        })
        return

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

        # Snapshot in the worker's conversation scope; a later turn/switch may
        # have changed manager.last_receipt by the time this result is polled.
        payload = {
            **copy.deepcopy(ctx.chat_turn.snapshot),
            "ok": True,
            "response": user_response,
            "chat_latency_ms": elapsed_ms,
            "turn_id": ctx.chat_turn.turn_id,
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


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    """Trace the inbound agent request; the worker inherits this context."""
    import hashlib

    from runtime_observability import traced_span

    attributes = {
        "http.request.method": str(getattr(handler, "command", "POST")),
        "bago.request.digest": hashlib.sha256(
            str(body.get("message") or "").encode("utf-8", errors="replace")
        ).hexdigest(),
        "bago.conversation_id": str(body.get("conversation_id") or ""),
        "bago.chat.retry": bool(body.get("turn_id")),
    }
    with traced_span("bago.agent.request", attributes):
        _handle(handler, body)

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
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _inject_manager_context(message: str, body: dict[str, Any]) -> str:
    """If `body['manager_context']` is set, prefix the user message with a
    `[BAGO_CTX:...]` marker so the AI knows which manager view is active.
    Returns the original message if no manager_context was provided.

    NOTE: this hook was aspirational in the original bridge code; it's
    wired here so that the contract is real (the manager UI sets
    manager_context on every chat call), but the legacy code never
    actually emitted the prefix. Both the legacy handler and this one
    behave identically today (no prefix); the field is a no-op until
    the manager UI starts sending it AND we wire the consumer side.
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


def _send_with_watchdog(ctx, ai_message: str, timeout_s: float) -> tuple[str | None, dict | None, float]:
    """Run mgr.send(ai_message) on a background thread with a timeout.

    Returns (response, error_payload, elapsed_ms). Exactly one of
    `response` or `error_payload` is non-None on success vs. timeout.
    """
    started = time.time()
    if timeout_s <= 0:
        try:
            return ctx.session_mgr.send(ai_message), None, (time.time() - started) * 1000
        except Exception as exc:
            return None, {"ok": False, "error": f"Error interno: {exc}"}, (time.time() - started) * 1000

    done = threading.Event()
    worker_result: dict[str, Any] = {}
    worker_exc: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            worker_result["response"] = ctx.session_mgr.send(ai_message)
        except BaseException as exc:  # propagate after the wait
            worker_exc["exc"] = exc
        finally:
            done.set()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    finished = done.wait(timeout=timeout_s)
    if not finished:
        return None, {
            "ok": False,
            "error": (
                f"El modelo no respondi\u00f3 en {timeout_s:g}s "
                "(timeout). Posible cuelgue del provider o del modelo."
            ),
            "chat_timeout_s": timeout_s,
            "timed_out": True,
        }, (time.time() - started) * 1000

    if worker_exc:
        return None, {"ok": False, "error": f"Error interno: {worker_exc['exc']}"}, (time.time() - started) * 1000
    return worker_result.get("response"), None, (time.time() - started) * 1000


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from request_context import build_context

    ctx = build_context(handler)
    if ctx.session_mgr is None:
        ctx.send_json(503, {"error": "SessionManager no disponible"})
        return

    message = body.get("message", "")
    if not message:
        ctx.send_json(400, {"error": "Campo 'message' requerido"})
        return

    ai_message = _inject_manager_context(message, body)
    channel = ctx.channel(body)
    pre_state = ctx.session_mgr.status()
    timeout_s = float(ctx.chat_timeout_s or 0.0)

    response, error_payload, elapsed_ms = _send_with_watchdog(ctx, ai_message, timeout_s)

    if error_payload is not None:
        # Timeout or worker exception \u2014 still record the shadow event.
        ctx.record_shadow(
            action_kind="chat",
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
        else:
            ctx.send_json(500, error_payload)
        return

    try:
        payload = {
            "ok": True,
            "response": response,
            "session_id": ctx.session_mgr.session_id,
            "provider": ctx.session_mgr.provider,
            "model": ctx.session_mgr.model,
            "history_count": len(ctx.session_mgr.store.get_history()),
            "chat_latency_ms": elapsed_ms,
            "chat_timeout_s": timeout_s,
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
        ctx.send_json(200, payload)
    except Exception:
        payload = {"ok": False, "error": "Error interno al procesar el mensaje"}
        ctx.record_shadow(
            action_kind="chat",
            channel=channel,
            payload={"message": message},
            pre_state=pre_state,
            post_state=ctx.session_mgr.status(),
            result=payload,
            elapsed_ms=(time.time() * 1000),
        )
        ctx.send_json(500, payload)

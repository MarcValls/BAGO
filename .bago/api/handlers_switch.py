"""handlers_switch.py \u2014 POST /switch for the BAGO HTTP bridge.

Migrated from bridge._handle_switch on 2026-06-24. Same semantics:
  - validate body
  - compute pre_state
  - delegate to SwitchEngine.execute
  - record shadow event
  - send JSON response

Uses RequestContext so the handler no longer depends on `self`.
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from request_context import build_context

    ctx = build_context(handler)
    if ctx.session_mgr is None or ctx.switch_engine is None:
        ctx.send_json(503, {"error": "SessionManager/SwitchEngine no disponible"})
        return

    provider = body.get("provider", "")
    model = body.get("model")
    force = body.get("force", False)
    if not provider:
        ctx.send_json(400, {"error": "Campo 'provider' requerido"})
        return

    channel = ctx.channel(body)
    pre_state = ctx.session_mgr.status()

    def _do_switch() -> Any:
        return ctx.switch_engine.execute(ctx.session_mgr, provider, model, force=force)

    try:
        result, elapsed_ms = ctx.timed_call(_do_switch)
        payload = {
            "ok": result.ok,
            "message": result.message,
            "provider": ctx.session_mgr.provider,
            "model": ctx.session_mgr.model,
        }
        ctx.record_shadow(
            action_kind="switch",
            channel=channel,
            payload={"provider": provider, "model": model, "force": force},
            pre_state=pre_state,
            post_state=ctx.session_mgr.status(),
            result=payload,
            elapsed_ms=elapsed_ms,
        )
        ctx.send_json(200 if result.ok else 400, payload)
    except Exception:
        ctx.send_json(500, {"error": "Error interno al cambiar provider/modelo"})

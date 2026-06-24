"""handlers_command.py \u2014 POST /command for the BAGO HTTP bridge.

Migrated from bridge._handle_command on 2026-06-24. Same semantics as
the legacy implementation: validate body, prepend "/" if missing,
delegate to chat.commands.execute, record shadow event, send JSON
response. Uses RequestContext so the handler does not depend on `self`.
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


# `commands` resolves ambiguously when both `bago_core/commands/` and
# `.bago/chat/commands.py` are on sys.path. Load the chat-side module
# under a private alias (`_chat_commands`) so its `execute` function is
# reachable without colliding with `bago_core.commands`.
_CHAT_COMMANDS_PATH = Path(__file__).resolve().parents[1] / "chat" / "commands.py"
_spec = importlib.util.spec_from_file_location("_chat_commands", _CHAT_COMMANDS_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("_chat_commands", _mod)
_spec.loader.exec_module(_mod)

execute_command = _mod.execute


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from request_context import build_context

    ctx = build_context(handler)
    if ctx.session_mgr is None or ctx.switch_engine is None:
        ctx.send_json(503, {"error": "SessionManager/SwitchEngine no disponible"})
        return

    command_line = str(body.get("command", "")).strip()
    if not command_line:
        ctx.send_json(400, {"error": "Campo 'command' requerido"})
        return
    if not command_line.startswith("/"):
        command_line = "/" + command_line

    channel = ctx.channel(body)
    pre_state = ctx.session_mgr.status()

    def _do_command() -> dict[str, Any]:
        return dict(execute_command(command_line, ctx.session_mgr, ctx.switch_engine))

    try:
        result, elapsed_ms = ctx.timed_call(_do_command)
    except Exception:
        ctx.send_json(500, {"ok": False, "error": "Error interno al ejecutar el comando"})
        return

    payload = {
        "ok": bool(result.get("ok")),
        "message": result.get("message", ""),
        "action": result.get("action"),
        "session_id": ctx.session_mgr.session_id,
        "provider": ctx.session_mgr.provider,
        "model": ctx.session_mgr.model,
        "data": ctx.json_safe(result.get("data", result.get("result"))),
        "plan": ctx.json_safe(result.get("plan")),
    }
    ctx.record_shadow(
        action_kind="command",
        channel=channel,
        payload={"command": command_line},
        pre_state=pre_state,
        post_state=ctx.session_mgr.status(),
        result=payload,
        elapsed_ms=elapsed_ms,
    )
    ctx.send_json(200 if payload["ok"] else 400, payload)

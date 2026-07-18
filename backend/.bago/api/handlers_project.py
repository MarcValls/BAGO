"""handlers_project.py - Real HTTP endpoints for project/workspace control.

These routes expose the same semantics as `/project ...` slash commands,
but as first-class HTTP endpoints so the UI does not need to tunnel through
`/command` for workspace activation flows.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


_CHAT_PROJECT_COMMANDS_PATH = Path(__file__).resolve().parents[1] / "chat" / "project_commands.py"
_spec = importlib.util.spec_from_file_location("_bago_project_commands", _CHAT_PROJECT_COMMANDS_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("_bago_project_commands", _mod)
_spec.loader.exec_module(_mod)

cmd_project = _mod.cmd_project


def _mgr(handler):
    from api_state import get_mgr

    return get_mgr(handler)


def _ctx(handler):
    from request_context import build_context

    return build_context(handler)


def _action_args(action: str, body: dict[str, Any] | None = None) -> list[str]:
    payload = body or {}
    root = str(
        payload.get("root")
        or payload.get("path")
        or payload.get("workspace")
        or payload.get("project_root")
        or ""
    ).strip()
    args = [action]
    if root and action != "sync":
        args.append(root)
    return args


def _handle(handler: "BaseHTTPRequestHandler", action: str, body: dict[str, Any] | None = None) -> None:
    ctx = _ctx(handler)
    if ctx.session_mgr is None or ctx.switch_engine is None:
        ctx.send_json(503, {"ok": False, "error": "SessionManager/SwitchEngine no disponible"})
        return

    args = _action_args(action, body)
    channel = ctx.channel(body)
    # FIX v0.2.1 (R1.1): cachear status() durante la request. status() es
    # caro (6+ segundos en proyectos grandes) y se llamaba 4 veces por
    # request. Usamos un dict por-request para que la siguiente llamada
    # sea O(1) sin cambiar el comportamiento del SessionManager.
    state_cache: dict[str, Any] = {}

    def _cached_status() -> dict[str, Any]:
        if "status" not in state_cache:
            state_cache["status"] = ctx.session_mgr.status()
        return state_cache["status"]

    pre_state = _cached_status()

    def _do() -> dict[str, Any]:
        return dict(cmd_project(ctx.session_mgr, ctx.switch_engine, args))

    try:
        result, elapsed_ms = ctx.timed_call(_do)
    except Exception:
        ctx.send_json(500, {"ok": False, "error": f"Error interno al ejecutar /project {action}"})
        return

    payload = {
        "ok": bool(result.get("ok")),
        "message": result.get("message", ""),
        "action": action,
        "endpoint": f"/project/{action}",
        "session_id": ctx.session_mgr.session_id,
        "provider": ctx.session_mgr.provider,
        "model": ctx.session_mgr.model,
        "data": ctx.json_safe(result.get("data", result.get("result"))),
    }
    ctx.record_shadow(
        action_kind="project",
        channel=channel,
        payload={"action": action, "args": args, "body": body or {}},
        pre_state=pre_state,
        post_state=_cached_status(),
        result=payload,
        elapsed_ms=elapsed_ms,
    )
    if payload["ok"]:
        from event_bus import emit
        post_state = _cached_status()
        event_name = {
            "init": "workspace.initialized",
            "link": "workspace.linked",
            "seed": "workspace.seeded",
            "sync": "workspace.synced",
        }.get(action, f"project.{action}")
        emit(event_name, {
            "action": action,
            "root": post_state.get("project_root") or post_state.get("workspace_state_root") or "",
            "binding_confirmed": post_state.get("binding_confirmed", False),
        })
    ctx.send_json(200 if payload["ok"] else 400, payload)


def handle_project_status(handler: "BaseHTTPRequestHandler") -> None:
    _handle(handler, "status")


def handle_project_analyze(handler: "BaseHTTPRequestHandler") -> None:
    _handle(handler, "analyze")


def handle_project_inspect(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    """Lee el estado REAL del filesystem en `root` sin tocar el session manager.

    La UI usa esto antes de ofrecer "Sembrar y activar" para detectar si el
    workspace ya está vinculado y configurado. Devuelve `configured` y
    `linked` basados en la presencia de archivos en `.bago/` y `.gabo/`,
    no en el snapshot cacheado del session manager.
    """
    from api_serializers import send_json
    from project_memory import status_data, _expected_files, _expected_dirs

    root = str(body.get("root", "") or "").strip()
    if not root:
        send_json(handler, 400, {"ok": False, "error": "Campo 'root' requerido"})
        return

    from pathlib import Path
    # Manejar rutas Windows con backslashes: el cliente envía "C:\Users\..." y
    # `Path(ruta)` no las entiende como absolutas en algunos casos. Normalizamos
    # a forward-slashes y luego a Path.
    normalized = root.replace("/", "\\")
    if len(normalized) >= 2 and normalized[1] == ":":
        # Ya es una ruta absoluta tipo "C:\..." o "C:/..."
        root_path = Path(normalized)
    else:
        root_path = Path(normalized).expanduser().resolve()
    if not root_path.exists():
        send_json(handler, 404, {"ok": False, "error": f"Ruta no existe: {root_path}"})
        return

    try:
        data = status_data(root_path)
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"Error al inspeccionar: {exc}"})
        return

    # Enriquecer con la lectura del manifest `.gabo/workspace.json` si existe.
    gabo = root_path / ".gabo"
    manifest = gabo / "workspace.json"
    manifest_data: dict[str, Any] = {}
    if manifest.exists():
        try:
            import json
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}

    send_json(handler, 200, {
        "ok": True,
        "root": str(root_path),
        "configured": data.get("configured", False),
        "linked": data.get("linked", False),
        "link_mode": data.get("link_mode", "none"),
        "marker": data.get("marker", ""),
        "directories": data.get("directories", {}),
        "files": data.get("files", {}),
        "manifest": manifest_data,
        "manifest_exists": manifest.exists(),
        "binding_confirmed": bool(manifest_data.get("binding_confirmed", False)),
        "binding_reason": str(manifest_data.get("binding_reason", "")),
    })


def handle_project_init(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "init", body)


def handle_project_link(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "link", body)


def handle_project_seed(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "seed", body)


def handle_project_sync(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "sync", body)


def handle_workspace_init(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "init", body)


def handle_workspace_link(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "link", body)


def handle_workspace_seed(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "seed", body)


def handle_workspace_sync(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    _handle(handler, "sync", body)

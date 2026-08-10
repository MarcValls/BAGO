"""GET/POST /sessions - recuperación real de sesiones persistentes."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


_SESSION_SWITCH_LOCK = threading.RLock()


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def _payload(manager: Any) -> dict[str, Any]:
    from session_registry import list_session_summaries
    sessions = list_session_summaries(
        manager.state_root,
        current_session_id=manager.session_id,
    )
    archived_sessions = list_session_summaries(
        manager.state_root,
        current_session_id="",
        archived_only=True,
        limit=100,
    )
    return {
        "ok": True,
        "active_session_id": manager.session_id,
        "sessions": sessions,
        "count": len(sessions),
        "archived_sessions": archived_sessions,
        "archived_count": len(archived_sessions),
    }


def _activate(handler: "BaseHTTPRequestHandler", manager: Any) -> None:
    from handlers_router import restore_session_model, restore_session_reasoning
    from session_registry import mark_active_session
    restore_session_model(manager)
    restore_session_reasoning(manager)
    mark_active_session(manager)
    handler_type = type(handler)
    handler_type.session_mgr = manager
    handler.session_mgr = manager
    engine = getattr(handler_type, "switch_engine", None) or getattr(handler, "switch_engine", None)
    if engine is not None and hasattr(engine, "adapters"):
        engine.adapters = manager.adapters


def handle_get(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    manager = _mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    send_json(handler, 200, _payload(manager))


def handle_post(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from api_serializers import send_json
    from session_registry import archive_session, list_session_summaries, rename_session, restore_session, session_archived, session_exists, validate_session_id

    current = _mgr(handler)
    if current is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    action = str((body or {}).get("action") or "").strip().lower()
    if action not in {"create", "switch", "rename", "archive", "restore"}:
        send_json(handler, 400, {"ok": False, "error": "action debe ser create|switch|rename|archive|restore"})
        return

    with _SESSION_SWITCH_LOCK:
        try:
            current.save()
            if action == "rename":
                session_id = validate_session_id(str((body or {}).get("session_id") or current.session_id))
                rename_session(current.state_root, session_id, str((body or {}).get("title") or ""))
                if session_id == current.session_id:
                    current.store.update_meta({
                        "session_title": " ".join(str((body or {}).get("title") or "").split()).strip(),
                    })
                    current.save()
                send_json(handler, 200, _payload(current))
                return
            if action == "archive":
                session_id = validate_session_id(str((body or {}).get("session_id") or current.session_id))
                archive_session(current.state_root, session_id)
                if session_id != current.session_id:
                    send_json(handler, 200, _payload(current))
                    return
                current.store.update_meta({"archived": True})
                candidates = list_session_summaries(current.state_root, current_session_id="")
                replacement = next((item for item in candidates if item["session_id"] != session_id), None)
                if replacement:
                    manager = current.__class__.load(
                        replacement["session_id"],
                        base_path=str(getattr(current, "project_root", current.base_path)),
                        state_root=str(current.state_root),
                    )
                else:
                    manager = current.__class__(
                        provider=current.provider,
                        model=current.model,
                        base_path=str(getattr(current, "project_root", current.base_path)),
                        state_root=str(current.state_root),
                        system_prompt=current.system_prompt,
                        bago_mode=current.bago_mode,
                        active_agent=current.agent_gateway.active.name,
                        active_bridges=list(current.active_bridges),
                    )
                _activate(handler, manager)
            elif action == "create":
                manager = current.__class__(
                    provider=current.provider,
                    model=current.model,
                    base_path=str(getattr(current, "project_root", current.base_path)),
                    state_root=str(current.state_root),
                    system_prompt=current.system_prompt,
                    bago_mode=current.bago_mode,
                    active_agent=current.agent_gateway.active.name,
                    active_bridges=list(current.active_bridges),
                )
            elif action == "switch":
                session_id = validate_session_id(str((body or {}).get("session_id") or ""))
                if session_id == current.session_id:
                    send_json(handler, 200, _payload(current))
                    return
                if not session_exists(current.state_root, session_id):
                    send_json(handler, 404, {"ok": False, "error": f"Sesión no encontrada: {session_id}"})
                    return
                if session_archived(current.state_root, session_id):
                    send_json(handler, 409, {"ok": False, "error": "La sesión está archivada; restáurala antes de abrirla"})
                    return
                manager = current.__class__.load(
                    session_id,
                    base_path=str(getattr(current, "project_root", current.base_path)),
                    state_root=str(current.state_root),
                )
            elif action == "restore":
                session_id = validate_session_id(str((body or {}).get("session_id") or ""))
                if not session_exists(current.state_root, session_id):
                    send_json(handler, 404, {"ok": False, "error": f"Sesión no encontrada: {session_id}"})
                    return
                manager = current.__class__.load(
                    session_id,
                    base_path=str(getattr(current, "project_root", current.base_path)),
                    state_root=str(current.state_root),
                )
                restored_meta = restore_session(current.state_root, session_id)
                manager.store.update_meta({
                    "archived": False,
                    "restored_at": restored_meta.get("restored_at", ""),
                    "updated_at": restored_meta.get("updated_at", ""),
                })
            if action != "archive":
                _activate(handler, manager)
        except ValueError as exc:
            send_json(handler, 400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            send_json(handler, 409, {"ok": False, "error": f"No se pudo recuperar la sesión: {exc}"})
            return
    send_json(handler, 200, _payload(manager))

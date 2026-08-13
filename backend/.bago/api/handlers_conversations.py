"""GET/POST /conversations - conversaciones persistentes de la sesión activa."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def _payload(mgr: Any, *, conversation: dict[str, Any] | None = None) -> dict[str, Any]:
    store = mgr.store
    active = store.active_conversation_id
    history = store.get_history(conversation_id=active)
    conversations = store.list_conversations()
    payload: dict[str, Any] = {
        "ok": True,
        "session_id": mgr.session_id,
        "active_conversation_id": active,
        "conversations": conversations,
        "count": len(conversations),
        "history": {
            "session_id": mgr.session_id,
            "conversation_id": active,
            "messages": history,
            "count": len(history),
        },
    }
    if conversation is not None:
        payload["conversation"] = conversation
    return payload


def handle_get(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None or getattr(mgr, "store", None) is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    send_json(handler, 200, _payload(mgr))


def handle_post(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None or getattr(mgr, "store", None) is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    if not isinstance(body, dict):
        send_json(handler, 400, {"ok": False, "error": "body debe ser objeto"})
        return

    action = str(body.get("action") or "").strip().lower()
    conversation_id = str(body.get("conversation_id") or "").strip()
    try:
        if action == "create":
            conversation = mgr.store.create_conversation(str(body.get("title") or ""))
            history = mgr.store.get_history(conversation_id=conversation["conversation_id"])
            conversation["message_count"] = len(history)
            conversation["preview"] = ""
        elif action == "switch":
            conversation = mgr.store.switch_conversation(conversation_id)
        elif action == "rename":
            conversation = mgr.store.rename_conversation(conversation_id, str(body.get("title") or ""))
        elif action == "archive":
            conversation = mgr.store.archive_conversation(conversation_id)
        else:
            send_json(handler, 400, {"ok": False, "error": "action debe ser create|switch|rename|archive"})
            return
        mgr.save()
    except ValueError as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc)})
        return
    send_json(handler, 200, _payload(mgr, conversation=conversation))

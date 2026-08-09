"""Keep chat history scoped to the confirmed workspace."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    from api_serializers import send_json
    from api_state import get_mgr

    mgr = get_mgr(handler)
    root = str((body or {}).get("root") or "").strip()
    store = getattr(mgr, "store", None)
    if mgr is None or store is None or not root:
        send_json(handler, 400, {"ok": False, "error": "Workspace o SessionManager no disponible"})
        return
    normalized = root.lower().replace("/", "\\").rstrip("\\")
    mappings = store._meta.setdefault("workspace_conversations", {})
    conversation_id = str(mappings.get(normalized) or "")
    existing = {str(item.get("conversation_id")) for item in store.list_conversations()}
    if not conversation_id or conversation_id not in existing:
        workspace_name = root.rstrip("\\/").replace("/", "\\").split("\\")[-1] or root
        store.create_conversation(f"Workspace · {workspace_name}")
        conversation_id = store.active_conversation_id
        mappings[normalized] = conversation_id
        store._save_meta()
    else:
        store.switch_conversation(conversation_id)
    mgr.save()
    send_json(handler, 200, {
        "ok": True,
        "workspace_root": root,
        "conversation_id": conversation_id,
        "history": store.get_history(conversation_id=conversation_id),
        "count": len(store.get_history(conversation_id=conversation_id)),
    })

"""handlers_memory.py — GET /memory/list[?scope=...] for the BAGO HTTP bridge."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

_CORE_DIR = Path(__file__).resolve().parents[1] / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from api_state import resolve_state_root
    from knowledge_base import KnowledgeBase
    from urllib.parse import parse_qs, urlparse

    scope = parse_qs(urlparse(handler.path).query).get("scope", ["user"])[0]
    try:
        mgr = getattr(handler, "session_mgr", None)
        base_path = str(getattr(mgr, "base_path", resolve_state_root(handler)))
        state_root = str(resolve_state_root(handler))
        kb = KnowledgeBase(base_path=base_path, state_root=state_root)
        entries = kb.list_recent(limit=20)
        send_json(
            handler,
            200,
            {
                "scope": scope,
                "entries": [
                    {
                        "id": entry["id"],
                        "scope": scope,
                        "type": "memory",
                        "description": entry["content"],
                        "path": f"memory:{entry['id']}",
                        "content": entry["content"],
                        "source_session": entry["source_session"],
                        "created_at": entry["created_at"],
                    }
                    for entry in entries
                ],
            },
        )
    except Exception as exc:
        send_json(handler, 500, {"error": f"list_memories falló: {exc}"})

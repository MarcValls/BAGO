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


def _stores(handler):
    from api_state import resolve_state_root
    from embedding_store import EmbeddingStore
    from knowledge_base import KnowledgeBase

    mgr = getattr(handler, "session_mgr", None)
    base_path = str(getattr(mgr, "base_path", resolve_state_root(handler)))
    state_root = str(resolve_state_root(handler))
    return (
        KnowledgeBase(base_path=base_path, state_root=state_root),
        EmbeddingStore(base_path=base_path, state_root=state_root),
    )


def handle_status(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    kb = embeddings = None
    try:
        kb, embeddings = _stores(handler)
        send_json(handler, 200, {
            "ok": True,
            "contract": "bago.knowledge.v1",
            "knowledge": {"active": kb.count(), "total": kb.count(include_deprecated=True), "search": "fts5+like"},
            "embeddings": {**embeddings.stats(), "search": "cosine", "vectors_generated_by_server": False},
        })
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"memory status falló: {exc}"})
    finally:
        if kb:
            kb.close()
        if embeddings:
            embeddings.close()


def handle_search(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /memory/search — lexical search plus optional caller-supplied vector."""
    from api_serializers import send_json
    kb = embeddings = None
    try:
        query = str(body.get("query", "")).strip()
        vector = body.get("query_vector")
        limit = max(1, min(int(body.get("limit", 10)), 100))
        if not query and not isinstance(vector, list):
            send_json(handler, 400, {"error": "query o query_vector requerido"})
            return
        kb, embeddings = _stores(handler)
        lexical = kb.search(query, limit=limit) if query else []
        semantic = embeddings.search(
            query_vector=vector,
            limit=limit,
            provider=str(body.get("provider", "")),
            model=str(body.get("model", "")),
        ) if isinstance(vector, list) else []
        send_json(handler, 200, {
            "ok": True,
            "mode": "hybrid" if query and isinstance(vector, list) else ("vector" if isinstance(vector, list) else "lexical"),
            "lexical": lexical,
            "semantic": semantic,
            "count": len(lexical) + len(semantic),
        })
    except (TypeError, ValueError) as exc:
        send_json(handler, 400, {"error": str(exc)})
    except Exception as exc:
        send_json(handler, 500, {"error": f"memory search falló: {exc}"})
    finally:
        if kb:
            kb.close()
        if embeddings:
            embeddings.close()


def handle_embedding_upsert(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /memory/embeddings/upsert — persist a validated embedding."""
    from api_serializers import send_json
    embeddings = None
    try:
        memory_id = str(body.get("memory_id", "")).strip()
        content = str(body.get("content", "")).strip()
        vector = body.get("vector")
        if not memory_id or not content or not isinstance(vector, list):
            send_json(handler, 400, {"error": "memory_id, content y vector son requeridos"})
            return
        _kb, embeddings = _stores(handler)
        _kb.close()
        row_id = embeddings.add(
            memory_id=memory_id,
            content=content,
            vector=vector,
            source_session=str(body.get("source_session", "")),
            provider=str(body.get("provider", "")),
            model=str(body.get("model", "")),
        )
        send_json(handler, 200, {"ok": True, "id": row_id, "memory_id": memory_id, "vector_dim": len(vector)})
    except (TypeError, ValueError) as exc:
        send_json(handler, 400, {"error": str(exc)})
    except Exception as exc:
        send_json(handler, 500, {"error": f"embedding upsert falló: {exc}"})
    finally:
        if embeddings:
            embeddings.close()

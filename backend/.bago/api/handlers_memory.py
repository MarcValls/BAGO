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
    from knowledge_base import KnowledgeBase
    from urllib.parse import parse_qs, urlparse

    scope = parse_qs(urlparse(handler.path).query).get("scope", ["user"])[0]
    try:
        mgr = getattr(handler, "session_mgr", None)
        if mgr is None or not getattr(mgr, "state_root", None):
            send_json(handler, 503, {"error": "SessionManager no disponible"})
            return
        base_path = str(getattr(mgr, "base_path", ""))
        state_root = str(mgr.state_root)
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
    from embedding_store import EmbeddingStore
    from knowledge_base import KnowledgeBase

    mgr = getattr(handler, "session_mgr", None)
    if mgr is None or not getattr(mgr, "state_root", None):
        raise RuntimeError("SessionManager no disponible")
    base_path = str(getattr(mgr, "base_path", ""))
    state_root = str(mgr.state_root)
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
    """POST /memory/embeddings/upsert — persist a validated embedding for the active session."""
    from api_serializers import send_json
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from database_write_request import build_memory_database_request
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_gateway import ExecutionGateway
    try:
        memory_id = str(body.get("memory_id", "")).strip()
        content = str(body.get("content", "")).strip()
        vector = body.get("vector")
        if not memory_id or not content or not isinstance(vector, list):
            send_json(handler, 400, {"error": "memory_id, content y vector son requeridos"})
            return
        manager = getattr(handler, "session_mgr", None)
        if manager is None:
            send_json(handler, 503, {"error": "SessionManager no disponible"})
            return
        source_session = str(getattr(manager, "session_id", "") or "").strip()
        if not source_session:
            send_json(handler, 409, {"error": "active_session_required"})
            return
        request = build_memory_database_request(
            manager,
            operation="embedding.upsert",
            arguments={
                "memory_id": memory_id,
                "content": content,
                "vector": vector,
                "provider": str(body.get("provider", "")),
                "model": str(body.get("model", "")),
            },
            source_surface="api.memory.embedding_upsert",
        )
        boundary = AuthorizationBoundary()
        payload = dict(body or {})
        action = str(payload.get("authorization_action") or "").strip().lower()
        interaction_id = str(payload.get("interaction_id") or "").strip()
        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            send_json(handler, 200, {"ok": True, "authorization": {"state": "challenge", "challenge": challenge}})
            return
        if action == "approve":
            if str(payload.get("user_decision") or "").strip().lower() != "approve":
                raise AuthorizationError("La decisión explícita del usuario debe ser approve", code="authorization_user_decision_required")
            headers = getattr(handler, "headers", {}) or {}
            channel = headers.get("X-Bago-Channel", "") if hasattr(headers, "get") else ""
            approval = boundary.approve_challenge(
                challenge_id=str(payload.get("challenge_id") or ""),
                interaction_id=interaction_id,
                session_id=request.session_id,
                channel=channel,
            )
            send_json(handler, 200, {"ok": True, "authorization": {"state": "authorized", **approval}})
            return
        if action != "execute":
            send_json(handler, 400, {"error": "authorization_action_required"})
            return
        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""),
            request=request,
            context=ExecutionContext(manager=manager),
        )
        send_json(handler, 200, {
            "ok": True,
            "id": result["embedding_id"],
            "memory_id": memory_id,
            "vector_dim": len(vector),
            "authorization": {"state": "consumed", "permit_id": authorization.get("permit_id")},
        })
    except AuthorizationError as exc:
        send_json(handler, 409 if "challenge" in exc.code or "permit" in exc.code else 403, {"error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        send_json(handler, 409 if not exc.code.endswith("failed") else 500, {"error": str(exc), "code": exc.code})
    except (TypeError, ValueError) as exc:
        send_json(handler, 400, {"error": str(exc)})
    except Exception as exc:
        send_json(handler, 500, {"error": f"embedding upsert falló: {exc}"})

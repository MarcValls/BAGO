"""Canonical request construction for persistent memory database writes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bago_core.user_state_paths import state_root as configured_state_root
from execution_request import ExecutionRequest, build_execution_request


_OPERATIONS = frozenset({
    "knowledge.add",
    "knowledge.delete",
    "knowledge.delete_many",
    "knowledge.deprecate",
    "knowledge.delete_by_source_prefix",
    "knowledge.hybrid_add",
    "embedding.upsert",
    "embedding.delete_for_memory",
})


def memory_database_paths(manager: Any) -> tuple[Path, Path, Path]:
    raw_root = getattr(manager, "state_root", None)
    root = Path(raw_root).expanduser().resolve() if raw_root else Path(configured_state_root()).resolve()
    return root, root / "knowledge.db", root / "embeddings.db"


def build_memory_database_request(
    manager: Any,
    *,
    operation: str,
    arguments: dict[str, Any],
    source_surface: str,
) -> ExecutionRequest:
    sid = str(getattr(manager, "session_id", "") or "").strip()
    if not sid:
        raise ValueError("Active SessionManager session is required for persistent memory writes")
    clean_operation = str(operation or "").strip()
    if clean_operation not in _OPERATIONS:
        raise ValueError("Unsupported memory database operation")
    root, knowledge_db, embedding_db = memory_database_paths(manager)
    payload = dict(arguments)
    if clean_operation in {"knowledge.add", "knowledge.hybrid_add", "embedding.upsert"}:
        payload["source_session"] = sid
    target = {
        "resource": "memory_database",
        "operation": clean_operation,
        "state_root": str(root),
        "knowledge_db": str(knowledge_db),
        "embedding_db": str(embedding_db),
        "session_id": sid,
        "workspace_id": str(getattr(manager, "workspace_id", "") or ""),
        "workspace_root": str(getattr(manager, "project_root", "") or ""),
    }
    return build_execution_request(
        effect_id="database.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=sid,
        source_surface=source_surface,
        target=target,
        arguments=payload,
        scope="persistent",
    )

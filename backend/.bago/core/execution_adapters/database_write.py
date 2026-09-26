"""Gateway owner for bounded KnowledgeBase and EmbeddingStore mutations."""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database_write_request import memory_database_paths
from memory_database_schema import (
    EMBEDDING_TABLE_SCHEMA,
    KNOWLEDGE_FTS_SCHEMA,
    KNOWLEDGE_TABLE_SCHEMA,
)
from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


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
_MAX_TEXT = 1024 * 1024
_DATABASE_LOCKS: dict[str, threading.RLock] = {}
_DATABASE_LOCKS_GUARD = threading.Lock()


def _database_lock(state_root: Path) -> threading.RLock:
    key = str(state_root.resolve())
    with _DATABASE_LOCKS_GUARD:
        lock = _DATABASE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _DATABASE_LOCKS[key] = lock
        return lock


def _no_links(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if current.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            return False
    return True


def _validate_arguments(operation: str, arguments: dict[str, Any]) -> None:
    if operation in {"knowledge.add", "knowledge.hybrid_add", "embedding.upsert"}:
        content = arguments.get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > _MAX_TEXT:
            raise ExecutionGatewayError("Memory content is invalid or too large", code="database_write_content_invalid")
    if operation in {"knowledge.delete", "knowledge.deprecate"}:
        try:
            memory_id = int(arguments.get("memory_id"))
        except (TypeError, ValueError) as exc:
            raise ExecutionGatewayError("Memory id must be an integer", code="database_write_memory_id_invalid") from exc
        if memory_id <= 0:
            raise ExecutionGatewayError("Memory id must be positive", code="database_write_memory_id_invalid")
    if operation == "knowledge.delete_many":
        memory_ids = arguments.get("memory_ids")
        if not isinstance(memory_ids, list) or not memory_ids or len(memory_ids) > 100:
            raise ExecutionGatewayError("Memory ids must be a non-empty bounded list", code="database_write_memory_ids_invalid")
        try:
            normalized = [int(item) for item in memory_ids]
        except (TypeError, ValueError) as exc:
            raise ExecutionGatewayError("Memory ids must be integers", code="database_write_memory_ids_invalid") from exc
        if any(item <= 0 for item in normalized) or len(set(normalized)) != len(normalized):
            raise ExecutionGatewayError("Memory ids must be unique positive integers", code="database_write_memory_ids_invalid")
    if operation == "knowledge.delete_by_source_prefix":
        prefix = arguments.get("source_prefix")
        if not isinstance(prefix, str) or not prefix or len(prefix) > 512:
            raise ExecutionGatewayError("Memory source prefix is invalid", code="database_write_source_prefix_invalid")
    if operation == "embedding.delete_for_memory":
        memory_id = arguments.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id.strip() or len(memory_id) > 512:
            raise ExecutionGatewayError("Embedding memory_id is invalid", code="database_write_memory_id_invalid")
    if operation in {"knowledge.hybrid_add", "embedding.upsert"}:
        vector = arguments.get("vector")
        if not isinstance(vector, list) or not vector or len(vector) > 65536:
            raise ExecutionGatewayError("Embedding vector is invalid", code="database_write_vector_invalid")
        try:
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector):
                raise TypeError("boolean and non-numeric vector entries are forbidden")
            normalized = [float(value) for value in vector]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ExecutionGatewayError("Embedding vector contains non-numeric data", code="database_write_vector_invalid") from exc
        if not all(math.isfinite(value) for value in normalized):
            raise ExecutionGatewayError("Embedding vector contains non-finite values", code="database_write_vector_invalid")
        for name in ("memory_id", "provider", "model"):
            value = arguments.get(name, "")
            if not isinstance(value, str) or len(value) > 512:
                raise ExecutionGatewayError(f"Embedding {name} is invalid", code="database_write_argument_invalid")
        if operation == "embedding.upsert" and not arguments.get("memory_id", "").strip():
            raise ExecutionGatewayError("Embedding memory_id is required", code="database_write_memory_id_required")


def _ensure_knowledge_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(KNOWLEDGE_TABLE_SCHEMA)
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(memories)").fetchall()}
    if "deprecated" not in columns:
        connection.execute("ALTER TABLE memories ADD COLUMN deprecated INTEGER NOT NULL DEFAULT 0")
    try:
        connection.execute(KNOWLEDGE_FTS_SCHEMA)
    except sqlite3.OperationalError:
        pass


def _ensure_embedding_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(EMBEDDING_TABLE_SCHEMA)
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(embeddings)").fetchall()}
    if "vector_dim" not in columns:
        connection.execute("ALTER TABLE embeddings ADD COLUMN vector_dim INTEGER NOT NULL DEFAULT 0")
    if "updated_at" not in columns:
        connection.execute("ALTER TABLE embeddings ADD COLUMN updated_at TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_scope ON embeddings(memory_id, provider, model)")


def _insert_embedding(connection: sqlite3.Connection, arguments: dict[str, Any], memory_id: str) -> int:
    vector = [float(value) for value in arguments["vector"]]
    vector_json = json.dumps(vector, separators=(",", ":"), allow_nan=False)
    existing = connection.execute(
        "SELECT id FROM embeddings WHERE memory_id = ? AND provider = ? AND model = ? ORDER BY id DESC LIMIT 1",
        (memory_id, arguments.get("provider", ""), arguments.get("model", "")),
    ).fetchone()
    values = (
        arguments["content"], vector_json, len(vector),
        arguments.get("source_session", ""), arguments.get("provider", ""), arguments.get("model", ""),
    )
    if existing:
        connection.execute(
            "UPDATE embeddings SET content=?, vector_json=?, vector_dim=?, source_session=?, provider=?, model=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*values, int(existing["id"])),
        )
        return int(existing["id"])
    cursor = connection.execute(
        "INSERT INTO embeddings(memory_id, content, vector_json, vector_dim, source_session, provider, model, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (memory_id, *values),
    )
    return int(cursor.lastrowid)


class DatabaseWriteEffectAdapter:
    """Single registered authority; operations stay bounded to memory stores."""

    effect_ids = frozenset({"database.write"})

    @staticmethod
    def prepare_target(manager: Any, operation: str) -> dict[str, Any]:
        if operation not in _OPERATIONS:
            raise ExecutionGatewayError("Database write operation is unsupported", code="database_write_operation_invalid")
        root, knowledge_db, embedding_db = memory_database_paths(manager)
        if not _no_links(root) or not _no_links(knowledge_db) or not _no_links(embedding_db):
            raise ExecutionGatewayError("Memory database path contains a link", code="database_write_path_linked")
        return {
            "resource": "memory_database",
            "operation": operation,
            "state_root": str(root),
            "knowledge_db": str(knowledge_db),
            "embedding_db": str(embedding_db),
            "session_id": str(getattr(manager, "session_id", "") or ""),
            "workspace_id": str(getattr(manager, "workspace_id", "") or ""),
            "workspace_root": str(getattr(manager, "project_root", "") or ""),
        }

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        authorization = context.services.get("_authorization")
        if manager is None or not isinstance(authorization, dict):
            raise ExecutionGatewayError("database.write requires the active authorized SessionManager", code="database_write_authorization_required")
        if (authorization.get("state") != "consumed"
                or authorization.get("effect_id") != request.effect_id
                or authorization.get("operation_fingerprint") != request.fingerprint
                or authorization.get("session_id") != request.session_id):
            raise ExecutionGatewayError("database.write Permit does not match this operation", code="database_write_authorization_mismatch")
        if str(getattr(manager, "session_id", "") or "") != request.session_id:
            raise ExecutionGatewayError("database.write session identity changed", code="database_write_session_mismatch")
        if request.actor_kind != "user" or request.principal_id != "interactive-local-user":
            raise ExecutionGatewayError("database.write requires a direct user actor", code="database_write_actor_invalid")

        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        operation = str(request.target.get("operation") or "")
        _validate_arguments(operation, arguments)
        if operation in {"knowledge.add", "knowledge.hybrid_add", "embedding.upsert"}:
            if str(arguments.get("source_session") or "") != request.session_id:
                raise ExecutionGatewayError("Memory source session is not the active session", code="database_write_source_session_mismatch")
        expected_target = self.prepare_target(manager, operation)
        if request.target != expected_target:
            raise ExecutionGatewayError("Memory database target changed after approval", code="database_write_target_changed")

        root = Path(expected_target["state_root"])
        root.mkdir(parents=True, exist_ok=True)
        if (not _no_links(root) or not _no_links(Path(expected_target["knowledge_db"]))
                or not _no_links(Path(expected_target["embedding_db"]))):
            raise ExecutionGatewayError("Memory database root changed to a linked path", code="database_write_path_linked")
        knowledge_path = Path(expected_target["knowledge_db"])
        embedding_path = Path(expected_target["embedding_db"])
        needs_knowledge = operation.startswith("knowledge.")
        needs_embedding = operation.startswith("embedding.") or operation == "knowledge.hybrid_add"
        write_lock = _database_lock(root)
        write_lock.acquire()
        knowledge = embedding = None
        try:
            if needs_knowledge:
                knowledge = sqlite3.connect(str(knowledge_path), timeout=30.0)
                knowledge.row_factory = sqlite3.Row
                knowledge.execute("PRAGMA busy_timeout=30000")
                knowledge.execute("PRAGMA journal_mode=WAL")
                knowledge.execute("PRAGMA synchronous=NORMAL")
                _ensure_knowledge_schema(knowledge)
            if needs_embedding:
                embedding = sqlite3.connect(str(embedding_path), timeout=30.0)
                embedding.row_factory = sqlite3.Row
                embedding.execute("PRAGMA busy_timeout=30000")
                embedding.execute("PRAGMA journal_mode=WAL")
                embedding.execute("PRAGMA synchronous=NORMAL")
                _ensure_embedding_schema(embedding)

            result: dict[str, Any]
            if operation in {"knowledge.add", "knowledge.hybrid_add"}:
                cursor = knowledge.execute(
                    "INSERT INTO memories (content, source_session, created_at) VALUES (?, ?, ?)",
                    (arguments["content"], arguments.get("source_session", ""), datetime.now(timezone.utc).isoformat()),
                )
                memory_id = int(cursor.lastrowid)
                try:
                    knowledge.execute(
                        "INSERT INTO memories_fts (rowid, content, source_session) VALUES (?, ?, ?)",
                        (memory_id, arguments["content"], arguments.get("source_session", "")),
                    )
                except sqlite3.OperationalError:
                    pass
                knowledge.commit()
                result = {"memory_id": memory_id}
                if operation == "knowledge.hybrid_add":
                    try:
                        embedding_id = _insert_embedding(embedding, arguments, str(memory_id))
                        embedding.commit()
                    except Exception:
                        embedding.rollback()
                        try:
                            knowledge.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                            try:
                                knowledge.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
                            except sqlite3.OperationalError:
                                pass
                            knowledge.commit()
                        except Exception as rollback_error:
                            raise ExecutionGatewayError(
                                f"Embedding write failed and memory compensation failed: {rollback_error}",
                                code="database_write_compensation_failed",
                            )
                        raise
                    result["embedding_id"] = embedding_id
            elif operation == "knowledge.delete":
                cursor = knowledge.execute("DELETE FROM memories WHERE id = ?", (int(arguments["memory_id"]),))
                try:
                    knowledge.execute("DELETE FROM memories_fts WHERE rowid = ?", (int(arguments["memory_id"]),))
                except sqlite3.OperationalError:
                    pass
                knowledge.commit()
                result = {"deleted": cursor.rowcount > 0}
            elif operation == "knowledge.delete_many":
                memory_ids = [int(item) for item in arguments["memory_ids"]]
                cursor = knowledge.executemany("DELETE FROM memories WHERE id = ?", [(item,) for item in memory_ids])
                try:
                    knowledge.executemany("DELETE FROM memories_fts WHERE rowid = ?", [(item,) for item in memory_ids])
                except sqlite3.OperationalError:
                    pass
                knowledge.commit()
                result = {"deleted_count": cursor.rowcount}
            elif operation == "knowledge.deprecate":
                cursor = knowledge.execute("UPDATE memories SET deprecated = 1 WHERE id = ?", (int(arguments["memory_id"]),))
                knowledge.commit()
                result = {"deprecated": cursor.rowcount > 0}
            elif operation == "knowledge.delete_by_source_prefix":
                rows = knowledge.execute(
                    "SELECT id FROM memories WHERE source_session LIKE ?",
                    (f"{arguments['source_prefix']}%",),
                ).fetchall()
                ids = [int(row[0]) for row in rows]
                if ids:
                    knowledge.executemany("DELETE FROM memories WHERE id = ?", [(item,) for item in ids])
                    try:
                        knowledge.executemany("DELETE FROM memories_fts WHERE rowid = ?", [(item,) for item in ids])
                    except sqlite3.OperationalError:
                        pass
                knowledge.commit()
                result = {"deleted_count": len(ids)}
            elif operation == "embedding.upsert":
                result = {"embedding_id": _insert_embedding(embedding, arguments, arguments["memory_id"])}
                embedding.commit()
            elif operation == "embedding.delete_for_memory":
                cursor = embedding.execute("DELETE FROM embeddings WHERE memory_id = ?", (arguments["memory_id"],))
                embedding.commit()
                result = {"deleted_count": cursor.rowcount}
            else:
                raise ExecutionGatewayError("Database write operation is unsupported", code="database_write_operation_invalid")
            return {
                "ok": True,
                "executed": True,
                "effect_id": request.effect_id,
                "operation": operation,
                **result,
                "receipt_id": f"database-write:{request.fingerprint}",
            }
        except ExecutionGatewayError:
            if knowledge:
                knowledge.rollback()
            if embedding:
                embedding.rollback()
            raise
        except Exception as exc:
            if knowledge:
                knowledge.rollback()
            if embedding:
                embedding.rollback()
            raise ExecutionGatewayError(f"database.write failed: {exc}", code="database_write_failed") from exc
        finally:
            if knowledge:
                knowledge.close()
            if embedding:
                embedding.close()
            write_lock.release()

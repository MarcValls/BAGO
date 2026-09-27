"""Durable operation records for reconciling idempotent desired-state effects."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class ExecutionOperationError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class ExecutionOperationStore(Protocol):
    """Persistence contract for material-operation intent and receipts."""

    def prepare(
        self, operation_id: str, resource_key: str, payload_digest: str, fencing_token: int
    ) -> dict[str, Any]: ...

    def commit(self, operation_id: str, receipt: dict[str, Any]) -> None: ...

    def get(self, operation_id: str) -> dict[str, Any] | None: ...


class SQLiteExecutionOperationStore:
    """SQLite ledger kept beside local claims, with its own table and authority."""

    durability = "durable-local"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS execution_operations (
                    operation_id TEXT PRIMARY KEY,
                    resource_key TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    receipt_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def prepare(
        self, operation_id: str, resource_key: str, payload_digest: str, fencing_token: int
    ) -> dict[str, Any]:
        if not all(str(value).strip() for value in (operation_id, resource_key, payload_digest)):
            raise ValueError("operation_id, resource_key y payload_digest son obligatorios")
        now = self._now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM execution_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if row and (row["resource_key"] != resource_key or row["payload_digest"] != payload_digest):
                raise ExecutionOperationError(
                    "Operation key is bound to another resource or desired content",
                    code="execution_operation_conflict",
                )
            if row is None:
                connection.execute(
                    """INSERT INTO execution_operations
                       (operation_id,resource_key,payload_digest,fencing_token,status,receipt_json,created_at,updated_at)
                       VALUES (?,?,?,?,'PENDING',NULL,?,?)""",
                    (operation_id, resource_key, payload_digest, fencing_token, now, now),
                )
                status, receipt = "PENDING", None
            else:
                status = str(row["status"])
                receipt = json.loads(row["receipt_json"]) if row["receipt_json"] else None
                if status != "COMMITTED":
                    connection.execute(
                        "UPDATE execution_operations SET fencing_token=?,updated_at=? WHERE operation_id=?",
                        (fencing_token, now, operation_id),
                    )
            connection.commit()
            return {"operation_id": operation_id, "resource_key": resource_key,
                    "payload_digest": payload_digest, "fencing_token": fencing_token,
                    "status": status, "receipt": receipt}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def commit(self, operation_id: str, receipt: dict[str, Any]) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE execution_operations SET status='COMMITTED',receipt_json=?,updated_at=?
                   WHERE operation_id=? AND status='PENDING'""",
                (json.dumps(receipt, ensure_ascii=False, sort_keys=True), self._now(), operation_id),
            ).rowcount
            if changed != 1:
                raise ExecutionOperationError(
                    "Operation is not pending", code="execution_operation_missing"
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self, operation_id: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM execution_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if row is None:
                return None
            return {
                "operation_id": str(row["operation_id"]),
                "resource_key": str(row["resource_key"]),
                "payload_digest": str(row["payload_digest"]),
                "fencing_token": int(row["fencing_token"]),
                "status": str(row["status"]),
                "receipt": json.loads(row["receipt_json"]) if row["receipt_json"] else None,
            }
        finally:
            connection.close()


_STORES: dict[str, SQLiteExecutionOperationStore] = {}
_STORES_LOCK = threading.RLock()


def operation_store_for(manager: Any) -> ExecutionOperationStore | None:
    """Resolve the operation ledger only from a trusted canonical state root."""
    root = str(getattr(manager, "state_root", "") or "").strip()
    if not root:
        return None
    db_path = str((Path(root).expanduser().resolve() / "execution_claims.sqlite3"))
    with _STORES_LOCK:
        store = _STORES.get(db_path)
        if store is None:
            store = SQLiteExecutionOperationStore(db_path)
            _STORES[db_path] = store
        return store


__all__ = [
    "ExecutionOperationError",
    "ExecutionOperationStore",
    "SQLiteExecutionOperationStore",
    "operation_store_for",
]

"""session_db.py — SQLite index for BAGO session metadata.

Replaces the O(n) directory scan in ContextStore.list_sessions() with an
O(1) SQLite lookup. The message/timeline/token JSONL files remain unchanged
— SQLite only indexes session-level metadata for fast listing and search.

Schema:
    sessions(
        sid TEXT PRIMARY KEY,
        created_at TEXT,
        last_provider TEXT,
        last_model TEXT,
        switch_count INTEGER DEFAULT 0,
        bago_mode TEXT,
        active_agent TEXT,
        total_tokens INTEGER DEFAULT 0,
        total_calls INTEGER DEFAULT 0,
        last_switch_at TEXT,
        updated_at TEXT
    )

Usage:
    from session_db import SessionDB
    db = SessionDB(state_root)
    db.upsert("abc123", provider="ollama-local", model="llama3.2:3b")
    sessions = db.list_sessions(limit=20)
    meta = db.get("abc123")
    db.delete("abc123")
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    sid            TEXT PRIMARY KEY,
    created_at     TEXT,
    last_provider  TEXT DEFAULT '',
    last_model     TEXT DEFAULT '',
    switch_count   INTEGER DEFAULT 0,
    bago_mode      TEXT DEFAULT 'B',
    active_agent   TEXT DEFAULT 'default',
    total_tokens   INTEGER DEFAULT 0,
    total_calls    INTEGER DEFAULT 0,
    last_switch_at TEXT,
    workspace_state_root TEXT DEFAULT '',
    context_revision TEXT DEFAULT '',
    updated_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated
    ON sessions(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_provider
    ON sessions(last_provider);
"""

# Fields that require a column ADD when upgrading from a prior schema.
# SQLite supports ALTER TABLE ADD COLUMN; we check pragmas to stay safe.
_MIGRATION_COLUMNS = {
    "workspace_state_root": "TEXT DEFAULT ''",
    "context_revision": "TEXT DEFAULT ''",
}


class SessionDB:
    """SQLite-backed session index. Thread-safe via a single lock."""

    def __init__(self, state_root: Path | str | None = None):
        if state_root is None:
            from state_paths import resolve_state_root
            state_root = resolve_state_root(None)
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_root / "sessions.db"
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._conn()
            try:
                conn.executescript(_SCHEMA)
                self._migrate(conn)
                conn.commit()
            finally:
                conn.close()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add columns that may be missing when upgrading from a prior schema."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        for col, col_type in _MIGRATION_COLUMNS.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {col_type}")

    def upsert(self, sid: str, **fields: Any) -> None:
        """Insert or update a session row. Unknown fields are ignored."""
        allowed = {
            "created_at", "last_provider", "last_model", "switch_count",
            "bago_mode", "active_agent", "total_tokens", "total_calls",
            "last_switch_at", "workspace_state_root", "context_revision",
        }
        filtered = {k: v for k, v in fields.items() if k in allowed}
        filtered["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        filtered.setdefault("sid", sid)

        columns = ", ".join(filtered.keys())
        placeholders = ", ".join(["?"] * len(filtered))
        values = list(filtered.values())

        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    f"INSERT OR REPLACE INTO sessions ({columns}) VALUES ({placeholders})",
                    values,
                )
                conn.commit()
            finally:
                conn.close()

    def get(self, sid: str) -> dict | None:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE sid = ?", (sid,)
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def list_sessions(self, limit: int = 50, offset: int = 0, provider: str = "") -> list[dict]:
        """List sessions ordered by last-updated desc."""
        sql = "SELECT * FROM sessions"
        params: list[Any] = []
        if provider:
            sql += " WHERE last_provider = ?"
            params.append(provider)
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def count(self, provider: str = "") -> int:
        sql = "SELECT COUNT(*) FROM sessions"
        params: list[Any] = []
        if provider:
            sql += " WHERE last_provider = ?"
            params.append(provider)
        with self._lock:
            conn = self._conn()
            try:
                return conn.execute(sql, params).fetchone()[0]
            finally:
                conn.close()

    def delete(self, sid: str) -> bool:
        with self._lock:
            conn = self._conn()
            try:
                cur = conn.execute("DELETE FROM sessions WHERE sid = ?", (sid,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Search sessions by provider or model substring."""
        pattern = f"%{query}%"
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE last_provider LIKE ? OR last_model LIKE ? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (pattern, pattern, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def sync_from_flat_files(self) -> int:
        """One-time import: scan existing sessions/ directories and insert rows.

        This is idempotent — existing rows are replaced. Use after migration
        or when the index gets out of sync with flat files.
        """
        sessions_dir = self.state_root / "sessions"
        if not sessions_dir.exists():
            return 0
        imported = 0
        for d in sessions_dir.iterdir():
            if not d.is_dir():
                continue
            sid = d.name
            meta_path = d / "meta.json"
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            session_json_path = sessions_dir / f"{sid}.json"
            session_data = {}
            if session_json_path.exists():
                try:
                    session_data = json.loads(session_json_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            self.upsert(
                sid,
                created_at=meta.get("created_at", ""),
                last_provider=meta.get("last_provider", "") or session_data.get("provider", ""),
                last_model=meta.get("last_model", "") or session_data.get("model", ""),
                switch_count=meta.get("switch_count", 0),
                bago_mode=session_data.get("bago_mode", "B"),
                active_agent=session_data.get("active_agent", "default"),
                total_tokens=session_data.get("total_tokens", 0),
                total_calls=session_data.get("total_calls", 0),
                last_switch_at=session_data.get("last_switch_at"),
                context_revision=session_data.get("context_revision", meta.get("context_revision", "")),
            )
            imported += 1
        return imported

    def close(self) -> None:
        pass  # Connections are opened/closed per-operation


_db: SessionDB | None = None
_db_lock = threading.Lock()


def get_session_db(state_root: Path | str | None = None) -> SessionDB:
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                _db = SessionDB(state_root)
    return _db

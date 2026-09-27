#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
knowledge_base.py — BAGO 4.1.5 Knowledge Base

Almacenamiento persistente de hechos y recuerdos extraídos de las conversaciones.
Usa SQLite (stdlib) para persistencia sin dependencias externas.

Funciones:
  - add(content, source_session="") → guarda un fragmento de conocimiento
  - search(query, limit=5) → búsqueda por palabras clave (LIKE)
  - list_recent(limit=10) → últimos recuerdos añadidos
  - delete(memory_id) → elimina un recuerdo por ID
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import state_root as configured_state_root
from memory_database_schema import KNOWLEDGE_TABLE_SCHEMA

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class KnowledgeBase:
    """Base de conocimiento ligera con SQLite."""

    SCHEMA = KNOWLEDGE_TABLE_SCHEMA

    def __init__(self, base_path: str | None = None, state_root: str | None = None):
        self.base_path = Path(base_path or os.getcwd())
        self.db_dir = Path(state_root).expanduser().resolve() if state_root else Path(configured_state_root()).resolve()
        self.db_path = self.db_dir / "knowledge.db"
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection | None:
        with self._lock:
            if self._conn is None:
                if not self.db_path.is_file():
                    return None
                self._conn = sqlite3.connect(
                    f"{self.db_path.as_uri()}?mode=ro",
                    timeout=30.0,
                    check_same_thread=False,
                    uri=True,
                )
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA busy_timeout=30000")
            return self._conn

    def add(self, content: str, source_session: str = "") -> int:
        raise PermissionError("KnowledgeBase is read-only; use database.write through ExecutionGateway")

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Búsqueda por coincidencia de palabras (LIKE) o FTS si está disponible."""
        with self._lock:
            conn = self._connect()
            results: list[dict[str, Any]] = []
            if conn is None:
                return results
            columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
            if not columns:
                return results
            has_deprecated = "deprecated" in columns

        # Intentar FTS primero
            try:
                if has_deprecated:
                    rows = conn.execute(
                        "SELECT m.id, m.content, m.source_session, m.created_at FROM memories_fts "
                        "JOIN memories m ON m.id = memories_fts.rowid "
                        "WHERE memories_fts MATCH ? AND m.deprecated = 0 LIMIT ?",
                        (query, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT m.id, m.content, m.source_session, m.created_at FROM memories_fts "
                        "JOIN memories m ON m.id = memories_fts.rowid WHERE memories_fts MATCH ? LIMIT ?",
                        (query, limit),
                    ).fetchall()
                for row in rows:
                    results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "source_session": row["source_session"],
                    "created_at": row["created_at"],
                    })
                if results:
                    return results
            except sqlite3.OperationalError:
                pass

        # Fallback a LIKE
            pattern = f"%{query}%"
            if has_deprecated:
                rows = conn.execute(
                    "SELECT id, content, source_session, created_at FROM memories "
                    "WHERE deprecated = 0 AND content LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (pattern, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, content, source_session, created_at FROM memories "
                    "WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (pattern, limit),
                ).fetchall()
            for row in rows:
                results.append({
                "id": row["id"],
                "content": row["content"],
                "source_session": row["source_session"],
                "created_at": row["created_at"],
                })
            return results

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """Devuelve los recuerdos más recientes."""
        with self._lock:
            conn = self._connect()
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT id, content, source_session, created_at FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
            {
                "id": row["id"],
                "content": row["content"],
                "source_session": row["source_session"],
                "created_at": row["created_at"],
            }
            for row in rows
            ]

    def delete(self, memory_id: int) -> bool:
        raise PermissionError("KnowledgeBase is read-only; use database.write through ExecutionGateway")

    def deprecate(self, memory_id: int) -> bool:
        raise PermissionError("KnowledgeBase is read-only; use database.write through ExecutionGateway")

    def delete_by_source_prefix(self, source_prefix: str) -> int:
        raise PermissionError("KnowledgeBase is read-only; use database.write through ExecutionGateway")

    def count(self, include_deprecated: bool = False) -> int:
        """Número total de recuerdos almacenados."""
        with self._lock:
            conn = self._connect()
            if conn is None:
                return 0
            if include_deprecated:
                row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            else:
                columns = {str(item["name"]) for item in conn.execute("PRAGMA table_info(memories)").fetchall()}
                if not columns:
                    return 0
                if "deprecated" in columns:
                    row = conn.execute("SELECT COUNT(*) FROM memories WHERE deprecated = 0").fetchone()
                else:
                    row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            return row[0] if row else 0

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

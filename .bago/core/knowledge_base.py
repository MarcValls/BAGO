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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from state_paths import resolve_state_root

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class KnowledgeBase:
    """Base de conocimiento ligera con SQLite."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        source_session TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, source_session);
    """

    def __init__(self, base_path: str | None = None, state_root: str | None = None):
        self.base_path = Path(base_path or os.getcwd())
        self.db_dir = resolve_state_root(state_root)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "knowledge.db"
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript(self.SCHEMA)
        conn.commit()

    def add(self, content: str, source_session: str = "") -> int:
        """Añade un recuerdo y retorna su ID."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        cursor = conn.execute(
            "INSERT INTO memories (content, source_session, created_at) VALUES (?, ?, ?)",
            (content, source_session, now),
        )
        # Sync FTS table if available; ignore errors if FTS5 not supported
        try:
            conn.execute(
                "INSERT INTO memories_fts (content, source_session) VALUES (?, ?)",
                (content, source_session),
            )
        except sqlite3.OperationalError:
            pass
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Búsqueda por coincidencia de palabras (LIKE) o FTS si está disponible."""
        conn = self._connect()
        results: list[dict[str, Any]] = []

        # Intentar FTS primero
        try:
            rows = conn.execute(
                "SELECT rowid, content, source_session, created_at FROM memories_fts WHERE memories_fts MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
            for row in rows:
                results.append({
                    "id": row["rowid"],
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
        rows = conn.execute(
            "SELECT id, content, source_session, created_at FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
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
        conn = self._connect()
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
        """Elimina un recuerdo por ID."""
        conn = self._connect()
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        try:
            conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
        except sqlite3.OperationalError:
            pass
        conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        """Número total de recuerdos almacenados."""
        conn = self._connect()
        row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def _run_tests() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        state_root = Path(td) / "state"
        old = os.environ.get("BAGO_STATE_ROOT")
        os.environ["BAGO_STATE_ROOT"] = str(state_root)
        kb = KnowledgeBase(base_path=td)

        # Test add
        mid = kb.add("Python es un lenguaje de programación interpretado.", source_session="sess-1")
        assert isinstance(mid, int)
        assert kb.count() == 1

        # Test search
        results = kb.search("Python")
        assert len(results) == 1
        assert results[0]["content"].startswith("Python es")

        # Test multiple memories
        kb.add("El sol es una estrella.", source_session="sess-2")
        kb.add("La luna orbita la Tierra.", source_session="sess-2")
        assert kb.count() == 3

        # Test search with LIKE fallback
        results = kb.search("luna")
        assert len(results) == 1
        assert "luna" in results[0]["content"].lower()

        # Test list_recent
        recent = kb.list_recent(limit=2)
        assert len(recent) == 2

        # Test delete
        ok = kb.delete(mid)
        assert ok
        assert kb.count() == 2

        # Test empty search
        results = kb.search("inexistente")
        assert len(results) == 0

        kb.close()
        print("knowledge_base.py --test: ALL PASS")
        if old is None:
            os.environ.pop("BAGO_STATE_ROOT", None)
        else:
            os.environ["BAGO_STATE_ROOT"] = old
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    print("Uso: python knowledge_base.py --test")

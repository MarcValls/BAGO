#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
embedding_store.py — Almacén ligero de embeddings para memoria híbrida.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    numerator = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return numerator / (norm_a * norm_b)


class EmbeddingStore:
    def __init__(self, base_path: str | None = None, state_root: str | None = None):
        self.base_path = Path(base_path or os.getcwd())
        self.state_dir = resolve_state_root(state_root)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "embeddings.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT,
                content TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                source_session TEXT,
                provider TEXT,
                model TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_memory_id ON embeddings(memory_id)")
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(embeddings)")}
        if "vector_dim" not in columns:
            self.conn.execute("ALTER TABLE embeddings ADD COLUMN vector_dim INTEGER NOT NULL DEFAULT 0")
        if "updated_at" not in columns:
            self.conn.execute("ALTER TABLE embeddings ADD COLUMN updated_at TEXT")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_scope ON embeddings(memory_id, provider, model)")
        self.conn.commit()

    @staticmethod
    def _validate_vector(vector: list[float]) -> list[float]:
        if not vector:
            raise ValueError("El embedding no puede estar vacío")
        normalized = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in normalized):
            raise ValueError("El embedding contiene valores no finitos")
        return normalized

    def add(
        self,
        *,
        memory_id: str,
        content: str,
        vector: list[float],
        source_session: str = "",
        provider: str = "",
        model: str = "",
    ) -> int:
        vector = self._validate_vector(vector)
        existing = self.conn.execute(
            "SELECT id FROM embeddings WHERE memory_id = ? AND provider = ? AND model = ? ORDER BY id DESC LIMIT 1",
            (memory_id, provider, model),
        ).fetchone()
        payload = (content, json.dumps(vector), len(vector), source_session, provider, model)
        if existing:
            self.conn.execute(
                "UPDATE embeddings SET content=?, vector_json=?, vector_dim=?, source_session=?, provider=?, model=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (*payload, int(existing["id"])),
            )
            self.conn.commit()
            return int(existing["id"])
        cur = self.conn.execute(
            """
            INSERT INTO embeddings(memory_id, content, vector_json, vector_dim, source_session, provider, model, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (memory_id, *payload),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def search(self, *, query_vector: list[float], limit: int = 5, provider: str = "", model: str = "") -> list[dict[str, Any]]:
        query_vector = self._validate_vector(query_vector)
        if limit <= 0:
            return []
        where, params = [], []
        if provider:
            where.append("provider = ?")
            params.append(provider)
        if model:
            where.append("model = ?")
            params.append(model)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = self.conn.execute(
            """
            SELECT id, memory_id, content, vector_json, source_session, provider, model, created_at
            FROM embeddings
            """ + clause + " ORDER BY id DESC", params).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                vector = self._validate_vector(json.loads(row["vector_json"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if len(vector) != len(query_vector):
                continue
            score = _cosine_similarity(query_vector, vector)
            results.append({
                "id": int(row["id"]),
                "memory_id": row["memory_id"],
                "content": row["content"],
                "score": score,
                "source_session": row["source_session"],
                "provider": row["provider"],
                "model": row["model"],
                "created_at": row["created_at"],
            })
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def remove_for_memory(self, memory_id: str) -> int:
        cursor = self.conn.execute("DELETE FROM embeddings WHERE memory_id = ?", (memory_id,))
        self.conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self.conn.close()


def _run_tests() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        state_root = Path(td) / "state"
        old = os.environ.get("BAGO_STATE_ROOT")
        os.environ["BAGO_STATE_ROOT"] = str(state_root)
        store = EmbeddingStore(base_path=td)
        try:
            a = [1.0, 0.0, 0.0]
            b = [0.9, 0.1, 0.0]
            c = [0.0, 1.0, 0.0]
            store.add(memory_id="m1", content="alpha", vector=a, provider="ollama-local", model="stub")
            store.add(memory_id="m2", content="beta", vector=c, provider="ollama-local", model="stub")
            results = store.search(query_vector=b, limit=2)
            assert results[0]["memory_id"] == "m1"
            assert results[0]["score"] > results[1]["score"]
            print("embedding_store.py --test: ALL PASS")
        finally:
            store.close()
            if old is None:
                os.environ.pop("BAGO_STATE_ROOT", None)
            else:
                os.environ["BAGO_STATE_ROOT"] = old
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

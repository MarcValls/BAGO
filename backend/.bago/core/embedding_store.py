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
        self.conn.commit()

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
        cur = self.conn.execute(
            """
            INSERT INTO embeddings(memory_id, content, vector_json, source_session, provider, model)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (memory_id, content, json.dumps(vector), source_session, provider, model),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def search(self, *, query_vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT id, memory_id, content, vector_json, source_session, provider, model, created_at
            FROM embeddings
            ORDER BY id DESC
            """
        ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            vector = json.loads(row["vector_json"])
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

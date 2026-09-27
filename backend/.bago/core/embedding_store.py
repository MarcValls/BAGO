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
import threading
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import state_root as configured_state_root

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
        self.state_dir = Path(state_root).expanduser().resolve() if state_root else Path(configured_state_root()).resolve()
        self.db_path = self.state_dir / "embeddings.db"
        self._lock = threading.RLock()
        self.conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection | None:
        with self._lock:
            if self.conn is None:
                if not self.db_path.is_file():
                    return None
                self.conn = sqlite3.connect(
                    f"{self.db_path.as_uri()}?mode=ro",
                    timeout=30.0,
                    check_same_thread=False,
                    uri=True,
                )
                self.conn.row_factory = sqlite3.Row
                self.conn.execute("PRAGMA busy_timeout=30000")
            return self.conn

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
        raise PermissionError("EmbeddingStore is read-only; use database.write through ExecutionGateway")

    def search(self, *, query_vector: list[float], limit: int = 5, provider: str = "", model: str = "") -> list[dict[str, Any]]:
        query_vector = self._validate_vector(query_vector)
        if limit <= 0:
            return []
        with self._lock:
            connection = self._connect()
            if connection is None:
                return []
            if provider and model:
                rows = connection.execute(
                    "SELECT id, memory_id, content, vector_json, source_session, provider, model, created_at "
                    "FROM embeddings WHERE provider = ? AND model = ? ORDER BY id DESC",
                    (provider, model),
                ).fetchall()
            elif provider:
                rows = connection.execute(
                    "SELECT id, memory_id, content, vector_json, source_session, provider, model, created_at "
                    "FROM embeddings WHERE provider = ? ORDER BY id DESC",
                    (provider,),
                ).fetchall()
            elif model:
                rows = connection.execute(
                    "SELECT id, memory_id, content, vector_json, source_session, provider, model, created_at "
                    "FROM embeddings WHERE model = ? ORDER BY id DESC",
                    (model,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT id, memory_id, content, vector_json, source_session, provider, model, created_at "
                    "FROM embeddings ORDER BY id DESC"
                ).fetchall()

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
        raise PermissionError("EmbeddingStore is read-only; use database.write through ExecutionGateway")

    def stats(self) -> dict[str, Any]:
        with self._lock:
            connection = self._connect()
            if connection is None:
                row = None
            else:
                columns = {str(item["name"]) for item in connection.execute("PRAGMA table_info(embeddings)").fetchall()}
                if "vector_dim" in columns:
                    row = connection.execute(
                        "SELECT COUNT(*) AS total, COUNT(DISTINCT memory_id) AS memories, "
                        "COUNT(DISTINCT provider) AS providers, MIN(vector_dim) AS min_dim, MAX(vector_dim) AS max_dim "
                        "FROM embeddings"
                    ).fetchone()
                elif columns:
                    row = connection.execute(
                        "SELECT COUNT(*) AS total, COUNT(DISTINCT memory_id) AS memories, "
                        "COUNT(DISTINCT provider) AS providers FROM embeddings"
                    ).fetchone()
                else:
                    row = None
        return {
            "total": int(row["total"] or 0) if row else 0,
            "memories": int(row["memories"] or 0) if row else 0,
            "providers": int(row["providers"] or 0) if row else 0,
            "min_dim": int(row["min_dim"] or 0) if row and "min_dim" in row.keys() else 0,
            "max_dim": int(row["max_dim"] or 0) if row and "max_dim" in row.keys() else 0,
            "database": str(self.db_path),
        }

    def close(self) -> None:
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None

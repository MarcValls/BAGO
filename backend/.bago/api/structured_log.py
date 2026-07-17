"""structured_log.py — JSON-structured logging with rotation for the BAGO bridge.

Replaces plain print/serve_out.txt with structured JSON lines that can be
parsed by tools, filtered by level/provider, and rotated to avoid disk growth.

Usage:
    from structured_log import get_logger
    log = get_logger()
    log.info("server_started", host="127.0.0.1", port=8091)
    log.error("chat_failed", provider="ollama-local", error="timeout")

Output: JSON lines in ~/.bago/logs/bridge.jsonl (rotated at 5 MB, 3 backups kept).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path


class StructuredLogger:
    """Writes JSON-line log entries with rotation."""

    def __init__(
        self,
        log_dir: Path | str | None = None,
        max_bytes: int = 5 * 1024 * 1024,  # 5 MB
        backup_count: int = 3,
    ):
        if log_dir is None:
            log_dir = Path.home() / ".bago" / "logs"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "bridge.jsonl"
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()

    def _write(self, entry: dict) -> None:
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            try:
                if self.log_path.exists() and self.log_path.stat().st_size >= self.max_bytes:
                    self._rotate()
            except Exception:
                pass
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass  # Logging must never crash the server

    def _rotate(self) -> None:
        """Rotate: bridge.jsonl -> bridge.1.jsonl -> bridge.2.jsonl -> drop oldest."""
        for i in range(self.backup_count - 1, 0, -1):
            src = self.log_dir / f"bridge.{i}.jsonl"
            dst = self.log_dir / f"bridge.{i + 1}.jsonl"
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.rename(dst)
        if self.log_path.exists():
            self.log_path.rename(self.log_dir / "bridge.1.jsonl")

    def _emit(self, level: str, event: str, **fields) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "level": level,
            "event": event,
            **fields,
        }
        self._write(entry)

    def debug(self, event: str, **fields) -> None:
        self._emit("DEBUG", event, **fields)

    def info(self, event: str, **fields) -> None:
        self._emit("INFO", event, **fields)

    def warn(self, event: str, **fields) -> None:
        self._emit("WARN", event, **fields)

    def error(self, event: str, **fields) -> None:
        self._emit("ERROR", event, **fields)


_logger: StructuredLogger | None = None
_logger_lock = threading.Lock()


def get_logger() -> StructuredLogger:
    global _logger
    if _logger is None:
        with _logger_lock:
            if _logger is None:
                _logger = StructuredLogger()
    return _logger
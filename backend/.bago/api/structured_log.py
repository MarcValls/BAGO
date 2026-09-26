"""structured_log.py — JSON-structured logging with rotation for the BAGO bridge.

Replaces plain print/serve_out.txt with structured JSON lines that can be
parsed by tools, filtered by level/provider, and rotated to avoid disk growth.

Usage:
    from structured_log import get_logger
    log = get_logger()
    log.info("server_started", host="127.0.0.1", port=8091)
    log.error("chat_failed", provider="ollama-local", error="timeout")

Output: JSON lines in the canonical user log root (5 MB, 3 backups kept).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from bago_core.user_state_paths import logs_root


class StructuredLogger:
    """Writes JSON-line log entries with rotation."""

    def __init__(
        self,
        log_dir: Path | str | None = None,
        max_bytes: int = 5 * 1024 * 1024,  # 5 MB
        backup_count: int = 3,
    ):
        if log_dir is None:
            log_dir = logs_root()
        self.log_dir = Path(log_dir)
        if self.log_dir.expanduser().resolve() != logs_root().expanduser().resolve():
            raise ValueError("Structured logs must use the canonical BAGO log root")
        self.log_path = self.log_dir / "bridge.jsonl"
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()

    def _write(self, entry: dict) -> None:
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            try:
                from bago_core.server_effects import append_structured_log

                append_structured_log(line, max_bytes=self.max_bytes, backup_count=self.backup_count)
            except Exception:
                pass  # Logging must never crash the server

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

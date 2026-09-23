"""Small, durable JSON-file primitive for mutable BAGO state."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def write_json_atomic(path: Path, payload: Any) -> dict[str, Any]:
    return write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_text_atomic(path: Path, content: str) -> dict[str, Any]:
    from bago_core.server_effects import write_text_atomic as _server_write_text

    return _server_write_text(path, content, trusted_root=path.parent)


def append_text_durable(path: Path, content: str) -> dict[str, Any]:
    from bago_core.server_effects import append_text_durable as _server_append_text

    return _server_append_text(path, content, trusted_root=path.parent)

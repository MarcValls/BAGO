#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    last_error: Exception | None = None
    for delay in (0.02, 0.05, 0.1, 0.2, 0.4):
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay)
    if last_error is not None:
        raise last_error


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2, ensure_ascii: bool = False) -> None:
    atomic_write_text(path, json.dumps(payload, indent=indent, ensure_ascii=ensure_ascii) + "\n")


def read_json_quarantine(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            quarantine = path.with_suffix(path.suffix + ".corrupt")
            path.replace(quarantine)
        except Exception:
            pass
        return default

#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def _read_release_version() -> str:
    root = Path(__file__).resolve().parents[1]
    candidates = (
        root / "release_version.txt",
        root / ".bago" / "release_version.txt",
    )
    for path in candidates:
        if path.is_file():
            try:
                value = path.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if value:
                return value
    return "4.5.0"


CURRENT = _read_release_version()

#!/usr/bin/env python3
from __future__ import annotations

try:
    from paths import app_base_dir
except ImportError:
    from pathlib import Path

    def app_base_dir() -> Path:
        return Path(__file__).resolve().parents[1]


def _read_release_version() -> str:
    root = app_base_dir()
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

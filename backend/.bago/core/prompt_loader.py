#!/usr/bin/env python3
"""Small file-backed prompt loader for BAGO prompt blocks."""
from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str, *, default: str = "") -> str:
    path = _PROMPT_DIR / name
    try:
        return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip()
    except OSError:
        return default

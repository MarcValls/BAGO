#!/usr/bin/env python3
"""_path_helper.py — Centralized sys.path bootstrap for .bago/tools scripts."""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_BAGO_DIR = _TOOLS_DIR.parent


def _ensure(dir_path: Path) -> None:
    """Insert *dir_path* into sys.path exactly once."""
    s = str(dir_path.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)


def ensure_tools_path() -> None:
    """Make the .bago/tools directory importable."""
    _ensure(_TOOLS_DIR)


def ensure_core_path() -> None:
    """Make .bago/core (and tools, for sibling imports) importable."""
    ensure_tools_path()
    _ensure(_BAGO_DIR / "core")


def ensure_path(dir_path: Path | str) -> None:
    """Make an arbitrary directory importable."""
    _ensure(Path(dir_path))


def _self_test() -> int:
    import tempfile

    ensure_tools_path()
    before_len = len(sys.path)
    ensure_tools_path()
    assert len(sys.path) == before_len, "duplicate sys.path insertion"

    with tempfile.TemporaryDirectory() as td:
        d = Path(td).resolve()
        ensure_path(d)
        assert str(d) in sys.path

    print("_path_helper.py --test: OK")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    raise SystemExit(_self_test() if args.test else 0)

#!/usr/bin/env python3
"""
clean_ollama_history.py — Borra history.tmp si tiene el mismo hash que history.

Uso:
    python scripts\\clean_ollama_history.py
    python scripts\\clean_ollama_history.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def _user_ollama_root() -> Path:
    return Path.home() / ".ollama"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-ollama", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.user_ollama or str(_user_ollama_root()))
    history = root / "history"
    history_tmp = root / "history.tmp"
    if not (history.exists() and history_tmp.exists()):
        print("history o history.tmp no existen; nada que limpiar")
        return 0
    if _sha256(history) != _sha256(history_tmp):
        print("hashes distintos; conservo ambos")
        return 0
    if args.dry_run:
        print(f"[dry-run] would remove {history_tmp}")
        return 0
    history_tmp.unlink()
    print(f"removed {history_tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

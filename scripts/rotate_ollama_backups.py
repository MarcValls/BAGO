#!/usr/bin/env python3
"""
rotate_ollama_backups.py — Conserva últimos 3 + 7 días, lo más restrictivo.

Uso:
    python scripts\\rotate_ollama_backups.py
    python scripts\\rotate_ollama_backups.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path


def _user_ollama_root() -> Path:
    return Path.home() / ".ollama" / "backup"


def _list(backup_dir: Path, name_re: str) -> list[Path]:
    rx = re.compile(name_re)
    return sorted(
        [p for p in backup_dir.iterdir() if p.is_file() and rx.search(p.name)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _apply(backups: list[Path], keep_count: int, keep_days: int, dry_run: bool) -> list[Path]:
    cutoff = _dt.datetime.now() - _dt.timedelta(days=keep_days)
    keep: set[Path] = set()
    for i, p in enumerate(backups):
        if i < keep_count:
            keep.add(p)
            continue
        mtime = _dt.datetime.fromtimestamp(p.stat().st_mtime)
        if mtime >= cutoff:
            keep.add(p)
    removed: list[Path] = []
    for p in backups:
        if p in keep:
            continue
        if dry_run:
            print(f"[dry-run] would remove {p}")
        else:
            p.unlink()
            print(f"removed {p}")
        removed.append(p)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-ollama", default=None)
    parser.add_argument("--keep-count", type=int, default=3)
    parser.add_argument("--keep-days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    backup_dir = Path(args.user_ollama or str(_user_ollama_root()))
    if not backup_dir.exists():
        print(f"backup dir missing: {backup_dir}")
        return 0
    removed_total: list[Path] = []
    for name_re, label in ((r"^config\.json\.", "config.json"), (r"^config\.toml\.", "config.toml")):
        backups = _list(backup_dir, name_re)
        print(f"{label}: {len(backups)} backups found")
        removed_total += _apply(backups, args.keep_count, args.keep_days, args.dry_run)
    print(f"total removed: {len(removed_total)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

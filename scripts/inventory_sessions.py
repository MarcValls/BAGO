#!/usr/bin/env python3
"""
inventory_sessions.py — Inventario de sesiones BAGO y Pi en CSV.

Uso:
    python scripts\\inventory_sessions.py --out inventory.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import sys
from pathlib import Path


def _user_bago_root() -> Path:
    return Path.home() / ".bago"


def _user_pi_root() -> Path:
    return Path.home() / ".pi"


def _row(path: Path, kind: str) -> dict:
    stat = path.stat()
    drive = ""
    m = re.search(r"--([A-Z])--", path.as_posix())
    if m:
        drive = m.group(1)
    status = "unknown"
    if path.is_dir():
        meta = path / "meta.json"
        if meta.exists():
            try:
                status = json.loads(meta.read_text(encoding="utf-8")).get("status", "unknown")
            except Exception:
                status = "parse-error"
        else:
            for ext in (".json", ".jsonl"):
                if any(path.glob(f"*{ext}")):
                    status = "active"
                    break
    return {
        "kind": kind,
        "path": str(path),
        "drive": drive,
        "size": stat.st_size,
        "mtime": _dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "status": status,
    }


def _walk(root: Path, kinds: list[str]) -> list[dict]:
    rows: list[dict] = []
    for kind, sub in kinds:
        d = root / sub
        if not d.exists():
            continue
        for child in d.iterdir():
            if child.is_dir() or child.suffix in (".json", ".jsonl"):
                rows.append(_row(child, kind))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-bago", default=None)
    parser.add_argument("--user-pi", default=None)
    parser.add_argument("--out", default="inventory.csv")
    args = parser.parse_args(argv)
    rows: list[dict] = []
    rows += _walk(Path(args.user_bago or str(_user_bago_root())), [("bago", "state/sessions")])
    rows += _walk(Path(args.user_pi or str(_user_pi_root())), [("pi", "agent/sessions")])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["kind", "drive", "status", "size", "mtime", "path"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

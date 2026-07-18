#!/usr/bin/env python3
"""
archive_pi_sessions.py — Comprime y archiva sesiones Pi cerradas (sin meta.json active).

Uso:
    python scripts\\archive_pi_sessions.py --inventory inventory.csv --out C:\\archive
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=7, help="Cutoff: archivar sesiones con mtime > N días (default: 7)")
    args = parser.parse_args(argv)
    import time as _t

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    archived = 0
    skipped_recent = 0
    cutoff = _t.time() - args.days * 86400
    with open(args.inventory, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["kind"] != "pi":
                continue
            if row["status"] in ("active",):
                continue
            if row["status"] in ("unknown",):
                continue
            p = Path(row["path"])
            if not p.exists():
                continue
            mtime = p.stat().st_mtime
            if mtime > cutoff:
                skipped_recent += 1
                if args.dry_run:
                    print(f"[skip-recent] {p} mtime={mtime}")
                continue
            archive = out_root / f"{p.parent.name}_{p.name}.zip"
            if args.dry_run:
                print(f"[dry-run] would archive {p} -> {archive}")
            else:
                with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                    if p.is_dir():
                        for child in p.rglob("*"):
                            if child.is_file():
                                z.write(child, child.relative_to(p.parent))
                    else:
                        z.write(p, p.name)
                print(f"archived {p} -> {archive}")
            archived += 1
    print(f"total archived: {archived} (skipped_recent: {skipped_recent}, cutoff_days: {args.days})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

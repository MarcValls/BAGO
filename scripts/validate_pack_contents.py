#!/usr/bin/env python3
"""validate_pack_contents.py — Validate a BAGO release ZIP against its manifest.

Usage:
    python3 validate_pack_contents.py path/to/bago-vX.Y.Z.zip
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


def validate(zip_path: Path) -> int:
    if not zip_path.exists():
        print(f"GATE-FAIL: ZIP not found: {zip_path}")
        return 1

    manifest_path = Path(str(zip_path) + ".manifest.json")
    if not manifest_path.exists():
        print(f"WARN: no manifest found at {manifest_path} — skipping manifest check")
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        print(f"OK: ZIP has {len(names)} files (no manifest)")
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_count = manifest.get("file_count", 0)
    expected_files = set(manifest.get("files", []))

    with zipfile.ZipFile(zip_path) as zf:
        actual_names = set(zf.namelist())

    if expected_files and actual_names != expected_files:
        extra = actual_names - expected_files
        missing = expected_files - actual_names
        if extra:
            print(f"WARN: {len(extra)} extra files in ZIP")
        if missing:
            print(f"GATE-FAIL: {len(missing)} files missing from ZIP: {sorted(missing)[:5]}")
            return 1

    print(f"OK: ZIP contents valid ({len(actual_names)} files, manifest match)")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_pack_contents.py <zip_path>")
        return 1

    # Support glob expansion (CI passes dist/*.zip)
    import glob
    paths = glob.glob(sys.argv[1])
    if not paths:
        print(f"GATE-FAIL: no ZIP found matching {sys.argv[1]}")
        return 1

    rc = 0
    for p in paths:
        rc = max(rc, validate(Path(p)))
    return rc


if __name__ == "__main__":
    sys.exit(main())

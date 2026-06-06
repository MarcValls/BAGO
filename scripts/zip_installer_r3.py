#!/usr/bin/env python3
"""Zip the BAGO r3 installer folder into a downloadable asset."""
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dist" / "bago-installer-r3"
DST = ROOT / "dist" / "bago-installer-4.1.5-r3-win-x64.zip"

if not SRC.exists():
    print(f"ERROR: {SRC} not found", file=sys.stderr)
    sys.exit(1)

if DST.exists():
    DST.unlink()

with zipfile.ZipFile(DST, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(SRC.rglob("*")):
        if p.is_file():
            zf.write(p, arcname=str(p.relative_to(SRC)))

print(f"wrote: {DST} ({DST.stat().st_size} bytes)")

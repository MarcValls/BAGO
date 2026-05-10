#!/usr/bin/env python3
"""build_pack.py — Reproducible, clean BAGO packaging (PR-05 Kernel Lockdown).

Usage:
    python3 .bago/tools/build_pack.py [--clean] [--out <dir>] [--dry-run]

Creates a distributable zip of BAGO, excluding:
  - .bago/dist/**          (no recursive build artefacts)
  - .bago/state/**         (no runtime session state)
  - **/__pycache__/**      (no bytecode)
  - **/*.pyc               (no compiled bytecode)
  - .git/**                (no version history)
  - .pytest_cache/**
  - .mypy_cache/**
  - .ruff_cache/**
  - **/.DS_Store

Output: <out>/BAGO_<version>_<timestamp>.zip
Also generates: <out>/BAGO_<version>_<timestamp>.sha256
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from datetime import datetime


BAGO_ROOT = Path(__file__).parent.parent.parent  # repo root (parent of .bago/)
BAGO_DIR  = BAGO_ROOT / ".bago"

# Patterns to exclude from the pack (relative to BAGO_ROOT)
EXCLUDE_PREFIXES: list[str] = [
    ".bago/dist",
    ".bago/state",
    ".bago/ImageStudio",   # large bundled binary app — not part of BAGO core
    ".bago/.models",       # LLM model blobs (GBs) — not distributable
    ".bago/bin",           # Ollama/system binaries — platform-specific, not core
    ".bago/snapshots",     # local snapshot zips — runtime artefacts
    ".bago/knowledge",     # project/persona-specific knowledge base (not core contract)
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".Spotlight-V100",     # macOS USB/disk metadata
    ".fseventsd",          # macOS file-system events
    ".Trashes",            # macOS trash
    ".TemporaryItems",     # macOS temporary items
    ".DocumentRevisions-V100",
    "bago.egg-info",       # pip editable install metadata
    "dist",                # output directory — never include in itself
    "System Volume Information",  # Windows volume metadata
]
EXCLUDE_SUFFIXES: list[str] = [
    "__pycache__",
    ".pyc",
    ".pyo",
    ".DS_Store",
    ".gitkeep",
]


def _should_exclude(rel: Path) -> bool:
    # Normalize to forward slashes for cross-platform comparison
    rel_str = str(rel).replace("\\", "/")
    for prefix in EXCLUDE_PREFIXES:
        norm_prefix = prefix.replace("\\", "/")
        if rel_str == norm_prefix or rel_str.startswith(norm_prefix + "/"):
            return True
    for suffix in EXCLUDE_SUFFIXES:
        norm_suffix = suffix.replace("\\", "/")
        if rel_str.endswith(norm_suffix) or ("/" + norm_suffix + "/") in rel_str:
            return True
    return False


def _read_version() -> str:
    pack_json = BAGO_DIR / "pack.json"
    if pack_json.exists():
        try:
            return json.loads(pack_json.read_text())["version"]
        except Exception:
            pass
    return "unknown"


def build(out_dir: Path, clean: bool = False, dry_run: bool = False) -> Path | None:
    version   = _read_version()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pack_name = f"BAGO_{version}_{timestamp}"
    zip_path  = out_dir / f"{pack_name}.zip"
    sha_path  = out_dir / f"{pack_name}.sha256"

    if clean and out_dir.exists():
        if not dry_run:
            shutil.rmtree(out_dir)
        print(f"  🧹 Cleaned: {out_dir}")

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Collect files
    # Dynamically exclude the output directory if it lives inside BAGO_ROOT
    dynamic_excludes: list[str] = []
    try:
        rel_out = out_dir.resolve().relative_to(BAGO_ROOT)
        dynamic_excludes.append(str(rel_out))
    except ValueError:
        pass  # out_dir is outside BAGO_ROOT — no need to exclude

    entries: list[Path] = []
    for path in sorted(BAGO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(BAGO_ROOT)
        if _should_exclude(rel):
            continue
        rel_str = str(rel)
        if any(rel_str == ex or rel_str.startswith(ex + "/") for ex in dynamic_excludes):
            continue
        entries.append(path)

    print(f"  📦 Building {pack_name}.zip")
    print(f"     Files included: {len(entries)}")

    if dry_run:
        for e in entries:
            print(f"     + {e.relative_to(BAGO_ROOT)}")
        print("  ℹ️  Dry-run: no files written.")
        return None

    # Write zip
    skipped = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in entries:
            arcname = str(path.relative_to(BAGO_ROOT))
            try:
                zf.write(path, arcname)
            except (FileNotFoundError, PermissionError) as exc:
                print(f"  ⚠  Skipped (unavailable): {arcname} — {exc}", file=sys.stderr)
                skipped += 1

    if skipped:
        print(f"  ⚠  Skipped {skipped} files (system/unavailable)")

    # Write sha256 manifest
    h = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path.write_text(f"{h}  {zip_path.name}\n")

    size_mb = zip_path.stat().st_size / 1_048_576
    print(f"  ✅ {zip_path}  ({size_mb:.1f} MB)")
    print(f"  🔑 {sha_path}")
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean",   action="store_true", help="Remove out dir before building")
    parser.add_argument("--out",     default="dist",       help="Output directory (default: ./dist)")
    parser.add_argument("--dry-run", action="store_true", help="List files without creating zip")
    args = parser.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = BAGO_ROOT / out_dir

    result = build(out_dir, clean=args.clean, dry_run=args.dry_run)
    if result is None and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()

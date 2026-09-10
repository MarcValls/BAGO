#!/usr/bin/env python3
"""build_pack.py — Build a distributable BAGO source ZIP.

Usage:
    python3 build_pack.py --out dist/ [--clean]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

from package_v4 import build_package

REPO_ROOT = Path(__file__).resolve().parents[1]


_EXCLUDE_DIRS = {
    ".git",
    ".codex",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "coverage",
    "htmlcov",
    "node_modules",
    ".bago",
    "dist",
    "build",
    "output",
    "out",
    "release",
    ".gabo/state",
    ".gabo/logs",
    ".gabo/cache",
    ".gabo/backups",
}
_EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}
_EXCLUDE_FILES = {"NTUSER.DAT"}
_EXCLUDE_GLOBS = {
    "*.sqlite",
    "*.db",
    "*.sqlite-wal",
    "*.sqlite-shm",
    "*.db-wal",
    "*.db-shm",
    "*.bak",
}


def _version() -> str:
    vf = REPO_ROOT / "release_version.txt"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    vj = REPO_ROOT / "versions.json"
    if vj.exists():
        return json.loads(vj.read_text(encoding="utf-8")).get("current", "0.0.0")
    return "0.0.0"


def _should_include(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & _EXCLUDE_DIRS:
        return False
    if rel.suffix in _EXCLUDE_SUFFIXES:
        return False
    if rel.name in _EXCLUDE_FILES:
        return False
    rel_text = rel.as_posix()
    if any(fnmatch.fnmatch(rel_text, pattern) for pattern in _EXCLUDE_GLOBS):
        return False
    return True


def build(out_dir: Path, clean: bool) -> Path:
    version = _version()
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"bago-v{version}.zip"

    if clean:
        for stale in (
            zip_path,
            out_dir / f"{zip_path.name}.manifest.json",
            out_dir / f"{zip_path.name}.sha256",
            out_dir / f"{zip_path.name}.report.md",
        ):
            stale.unlink(missing_ok=True)

    # Keep the legacy entry point, but delegate the package contract to the
    # canonical v4 packager.  The latter writes the provenance payload both
    # into the archive and into the manifest, which the release tests verify.
    result = build_package(REPO_ROOT, out_dir, release_version=version)
    zip_path = Path(result["zip"])
    print(
        f"OK: {zip_path} ({result['file_count']} files, "
        f"sha256={result['zip_sha256'][:16]}...)"
    )
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()
    build(Path(args.out), args.clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())

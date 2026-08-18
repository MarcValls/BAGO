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

    if clean and zip_path.exists():
        zip_path.unlink()

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(REPO_ROOT.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO_ROOT)
            if not _should_include(rel):
                continue
            zf.write(p, rel)
            file_count += 1

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    manifest = {
        "version": version,
        "zip": zip_path.name,
        "zip_sha256": digest,
        "file_count": file_count,
        "files": [str(n) for n in zipfile.ZipFile(zip_path).namelist()],
    }
    (out_dir / f"{zip_path.name}.manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / f"{zip_path.name}.sha256").write_text(
        f"{digest}  {zip_path.name}\n", encoding="utf-8"
    )
    print(f"OK: {zip_path} ({file_count} files, sha256={digest[:16]}...)")
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

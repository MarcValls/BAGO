#!/usr/bin/env python3
"""Check the recorded untracked route baseline without modifying watched files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path(
    "docs/architecture/evidence/untracked-routes-watch-20261005.json"
)


def git_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return Path(result.stdout.strip()).resolve()


def untracked_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {os.fsdecode(item) for item in result.stdout.split(b"\0") if item}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_under(path: str, directory: str) -> bool:
    return path == directory or path.startswith(directory.rstrip("/") + "/")


def safe_relative(root: Path, raw_path: str) -> Path:
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Manifest contiene una ruta no relativa segura: {raw_path}")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"La ruta sale de la raíz del repositorio: {raw_path}")
    return resolved


def check(manifest_path: Path) -> int:
    root = git_root(manifest_path.parent)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = manifest["entries"]
    expected = {entry["path"] for entry in entries}
    excluded = set(manifest.get("excluded_watch_files", []))
    roots = manifest.get("watch_roots", [])

    current_all = untracked_paths(root)
    watched_now = {
        path
        for path in current_all
        if path not in excluded
        and (path in expected or any(is_under(path, watch_root) for watch_root in roots))
    }

    problems: list[str] = []
    for path in sorted(expected - watched_now):
        problems.append(f"MISSING_FROM_UNTRACKED_SET {path}")
    for path in sorted(watched_now - expected):
        problems.append(f"NEW_UNTRACKED_PATH {path}")

    missing = 0
    changed = 0
    for entry in entries:
        relative = entry["path"]
        if entry.get("content_check") == "untracked_presence_only":
            continue
        file_path = safe_relative(root, relative)
        if not file_path.is_file():
            missing += 1
            if not any(line.endswith(" " + relative) for line in problems):
                problems.append(f"MISSING_FILE {relative}")
            continue
        size = file_path.stat().st_size
        digest = sha256_file(file_path)
        if size != entry["size_bytes"] or digest != entry["sha256"]:
            changed += 1
            problems.append(
                f"CONTENT_CHANGED {relative} "
                f"(size {entry['size_bytes']}->{size}, sha256 {entry['sha256']}->{digest})"
            )

    print(
        f"WATCH_RESULT={'PASS' if not problems else 'DRIFT'} "
        f"EXPECTED={len(expected)} UNTRACKED_MATCHES={len(watched_now & expected)} "
        f"MISSING_FILES={missing} CONTENT_CHANGED={changed} "
        f"NEW_PATHS={sum(line.startswith('NEW_UNTRACKED_PATH ') for line in problems)}"
    )
    for problem in sorted(set(problems)):
        print(problem)
    return 0 if not problems else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Ruta del inventario de línea base (relativa a la raíz Git).",
    )
    args = parser.parse_args()
    try:
        manifest_path = args.manifest
        if not manifest_path.is_absolute():
            manifest_path = Path(__file__).resolve().parents[1] / manifest_path
        manifest_path = manifest_path.resolve()
        return check(manifest_path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"WATCH_RESULT=ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

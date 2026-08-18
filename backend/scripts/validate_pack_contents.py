#!/usr/bin/env python3
"""validate_pack_contents.py — Validate a BAGO release ZIP or install tree against its manifest.

Usage:
    python3 validate_pack_contents.py path/to/bago-vX.Y.Z.zip
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


def _collect_tree_names(tree_root: Path) -> list[str]:
    names = []
    for file_path in tree_root.rglob("*"):
        if not file_path.is_file():
            continue
        names.append(file_path.relative_to(tree_root).as_posix())
    return sorted(names)


def _manifest_paths(entries) -> set[str]:
    paths: set[str] = set()
    for entry in entries or []:
        if isinstance(entry, str):
            paths.add(entry)
        elif isinstance(entry, dict):
            path = entry.get("path")
            if path:
                paths.add(str(path))
    return paths


def _resolve_tree_root(path: Path) -> Path | None:
    if not path.exists() or not path.is_dir():
        return None
    direct = path
    if (direct / "install-v4.ps1").exists() and (direct / "bago_core" / "launcher.py").exists():
        return direct
    current = path / "current"
    if (current / "install-v4.ps1").exists() and (current / "bago_core" / "launcher.py").exists():
        return current
    children = [child for child in path.iterdir() if child.is_dir()]
    for child in children:
        if (child / "install-v4.ps1").exists() and (child / "bago_core" / "launcher.py").exists():
            return child
    return None


def validate(zip_path: Path) -> int:
    if not zip_path.exists():
        print(f"GATE-FAIL: path not found: {zip_path}")
        return 1

    if zip_path.is_dir():
        tree_root = _resolve_tree_root(zip_path)
        if tree_root is None:
            print(f"GATE-FAIL: no install tree found in {zip_path}")
            return 1
        manifest_path = Path(str(tree_root) + ".manifest.json")
        if not manifest_path.exists() and tree_root.name == "current":
            manifest_path = tree_root.parent / "current.manifest.json"
        if not manifest_path.exists():
            print(f"WARN: no manifest found at {manifest_path} — skipping manifest check")
            names = _collect_tree_names(tree_root)
            print(f"OK: tree has {len(names)} files (no manifest)")
            return 0
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_files = _manifest_paths(manifest.get("included_files", []))
        actual_names = set(_collect_tree_names(tree_root))
        if expected_files and actual_names != expected_files:
            extra = actual_names - expected_files
            missing = expected_files - actual_names
            if extra:
                print(f"WARN: {len(extra)} extra files in tree")
            if missing:
                print(f"GATE-FAIL: {len(missing)} files missing from tree: {sorted(missing)[:5]}")
                return 1
        print(f"OK: tree contents valid ({len(actual_names)} files, manifest match)")
        return 0

    manifest_path = Path(str(zip_path) + ".manifest.json")
    if not manifest_path.exists():
        print(f"WARN: no manifest found at {manifest_path} — skipping manifest check")
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        print(f"OK: ZIP has {len(names)} files (no manifest)")
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_count = manifest.get("file_count", 0)
    expected_files = _manifest_paths(manifest.get("files", [])) or _manifest_paths(manifest.get("included_files", []))

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

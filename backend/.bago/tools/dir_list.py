#!/usr/bin/env python3
"""dir_list.py — BAGO tool: list directory contents in the workspace.

Usage:
    python dir_list.py --path <relative-path>
    python dir_list.py --path src/components
    python dir_list.py --path . --recursive

Lists files and subdirectories. Forbidden paths are blocked.
Paths must be inside the workspace root.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def _get_workspace_root() -> Path:
    root = os.environ.get("BAGO_WORKSPACE_ROOT", "")
    if root:
        return Path(root).resolve()
    return Path.cwd().resolve()

def _dev_mode() -> bool:
    return os.environ.get("BAGO_DEV_MODE", "").strip() in ("1", "true", "TRUE", "yes", "YES")

FORBIDDEN = (".git", ".env", "state", "dist", "release", "__pycache__", ".bago", "node_modules", ".venv", "venv")

def _is_forbidden(path_str: str) -> bool:
    if _dev_mode():
        return False
    normalized = path_str.replace("\\", "/").lower()
    for seg in FORBIDDEN:
        if seg.lower() in normalized.split("/"):
            return True
    return False

def _safe_rel(child: Path, ws_root: Path) -> str:
    try:
        return str(child.relative_to(ws_root))
    except ValueError:
        return str(child)


def _list_dir(directory: Path, ws_root: Path, recursive: bool = False, max_depth: int = 3, current_depth: int = 0) -> list[dict]:
    entries = []
    try:
        for child in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            rel = _safe_rel(child, ws_root) if str(child) != str(ws_root) else child.name
            entry = {
                "name": child.name,
                "path": rel,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else 0,
            }
            if recursive and child.is_dir() and current_depth < max_depth:
                if not _is_forbidden(child.name):
                    entry["children"] = _list_dir(child, ws_root, recursive, max_depth, current_depth + 1)
                else:
                    entry["children"] = []
            entries.append(entry)
    except PermissionError:
        pass
    return entries

def main() -> int:
    args = sys.argv[1:]
    path_arg = "."
    recursive = False
    max_depth = 3

    i = 0
    while i < len(args):
        if args[i] == "--path" and i + 1 < len(args):
            path_arg = args[i + 1]
            i += 2
        elif args[i] == "--recursive":
            recursive = True
            i += 1
        elif args[i] == "--max-depth" and i + 1 < len(args):
            max_depth = int(args[i + 1])
            i += 2
        else:
            i += 1

    if _is_forbidden(path_arg):
        print(json.dumps({"ok": False, "error": f"Forbidden path: {path_arg}"}, ensure_ascii=False))
        return 1

    ws_root = _get_workspace_root()
    target = Path(path_arg)
    if not target.is_absolute():
        target = ws_root / target
    target = target.resolve()

    try:
        target.relative_to(ws_root)
    except ValueError:
        if not _dev_mode():
            print(json.dumps({"ok": False, "error": f"Path outside workspace: {target}"}, ensure_ascii=False))
            return 1

    if not target.exists():
        print(json.dumps({"ok": False, "error": f"Directory not found: {path_arg}"}, ensure_ascii=False))
        return 1

    if not target.is_dir():
        print(json.dumps({"ok": False, "error": f"Not a directory: {path_arg}"}, ensure_ascii=False))
        return 1

    entries = _list_dir(target, ws_root, recursive, max_depth)

    result = {
        "ok": True,
        "path": _safe_rel(target, ws_root) if str(target) != str(ws_root) else ".",
        "entries": entries,
        "count": len(entries),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""file_write.py — BAGO tool: write or create a file in the workspace.

Usage:
    python file_write.py --path <relative-path> --content <file-content>
    python file_write.py --path src/App.tsx --content "import React ..."

Creates or overwrites a file. Parent directories are created automatically.
Forbidden paths are blocked. Paths must be inside the workspace root.
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

def main() -> int:
    args = sys.argv[1:]
    path_arg = ""
    content_arg = ""

    i = 0
    while i < len(args):
        if args[i] == "--path" and i + 1 < len(args):
            path_arg = args[i + 1]
            i += 2
        elif args[i] == "--content" and i + 1 < len(args):
            content_arg = args[i + 1]
            i += 2
        else:
            i += 1

    if not path_arg:
        print(json.dumps({"ok": False, "error": "Missing --path argument"}, ensure_ascii=False))
        return 1

    if not content_arg:
        print(json.dumps({"ok": False, "error": "Missing --content argument"}, ensure_ascii=False))
        return 1

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

    existed = target.exists()

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content_arg, encoding="utf-8")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"Write error: {exc}"}, ensure_ascii=False))
        return 1

    def _rel(target: Path, ws_root: Path) -> str:
        try:
            return str(target.relative_to(ws_root))
        except ValueError:
            return str(target)

    result = {
        "ok": True,
        "path": _rel(target, ws_root) if str(target) != str(ws_root) else str(target),
        "created": not existed,
        "overwritten": existed,
        "bytes_written": len(content_arg.encode("utf-8")),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
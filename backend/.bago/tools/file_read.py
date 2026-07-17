#!/usr/bin/env python3
"""file_read.py — BAGO tool: read a file from the workspace.

Usage:
    python file_read.py --path <relative-or-absolute-path>
    python file_read.py --path src/App.tsx --offset 0 --limit 100

Reads a file from the workspace root. If the path is relative, it is resolved
against BAGO_WORKSPACE_ROOT env var (set by SessionManager). If absolute, it
must be inside the workspace root.

Forbidden paths (.git, .env, state, .bago, node_modules, venv) are blocked.
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
    offset = 0
    limit = 0

    i = 0
    while i < len(args):
        if args[i] == "--path" and i + 1 < len(args):
            path_arg = args[i + 1]
            i += 2
        elif args[i] == "--offset" and i + 1 < len(args):
            offset = int(args[i + 1])
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    if not path_arg:
        print(json.dumps({"ok": False, "error": "Missing --path argument"}, ensure_ascii=False))
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

    if not target.exists():
        print(json.dumps({"ok": False, "error": f"File not found: {path_arg}"}, ensure_ascii=False))
        return 1

    if not target.is_file():
        print(json.dumps({"ok": False, "error": f"Not a file: {path_arg}"}, ensure_ascii=False))
        return 1

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"Read error: {exc}"}, ensure_ascii=False))
        return 1

    lines = text.splitlines()
    total_lines = len(lines)
    if offset > 0 or limit > 0:
        start = offset
        end = start + limit if limit > 0 else total_lines
        lines = lines[start:end]
        content = "\n".join(lines)
        truncated = end < total_lines
    else:
        content = text
        truncated = False

    def _rel(target: Path, ws_root: Path) -> str:
        try:
            return str(target.relative_to(ws_root))
        except ValueError:
            return str(target)

    result = {
        "ok": True,
        "path": _rel(target, ws_root) if str(target) != str(ws_root) else str(target),
        "content": content,
        "total_lines": total_lines,
        "offset": offset,
        "limit": limit if limit > 0 else total_lines,
        "truncated": truncated,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _workspace_root() -> Path:
    return Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read a bounded line range inside the workspace")
    parser.add_argument("--path", required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=120)
    args = parser.parse_args()
    root = _workspace_root()
    target = Path(args.path)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        rel = target.relative_to(root).as_posix()
    except ValueError:
        print(json.dumps({"ok": False, "error": "path_outside_workspace", "path": str(target)}, ensure_ascii=False))
        return 1
    if not target.is_file():
        print(json.dumps({"ok": False, "error": "file_not_found", "path": rel}, ensure_ascii=False))
        return 1
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, args.start)
    end = min(max(start, args.end), start + 500, len(lines))
    content = "\n".join(lines[start - 1:end])
    print(json.dumps({"ok": True, "path": rel, "start": start, "end": end, "content": content, "total_lines": len(lines)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

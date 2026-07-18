#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate syntax for one workspace file")
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    root = Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()
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
    suffix = target.suffix.lower()
    if suffix in {".py", ".pyw"}:
        cmd = [sys.executable, "-m", "py_compile", str(target)]
    elif suffix in {".js", ".mjs", ".cjs"}:
        cmd = ["node", "--check", str(target)]
    else:
        print(json.dumps({"ok": False, "error": "unsupported_syntax_validator", "path": rel, "suffix": suffix}, ensure_ascii=False))
        return 1
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=30, check=False)
    print(json.dumps({"ok": proc.returncode == 0, "path": rel, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}, ensure_ascii=False))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

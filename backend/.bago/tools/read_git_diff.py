#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Read bounded git diff for the workspace")
    parser.add_argument("--stat", action="store_true")
    parser.add_argument("--limit", type=int, default=20000)
    args = parser.parse_args()
    root = Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()
    cmd = ["git", "diff", "--stat"] if args.stat else ["git", "diff"]
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=20, check=False)
    content = (proc.stdout or proc.stderr or "")[: max(1000, args.limit)]
    print(json.dumps({"ok": proc.returncode == 0, "returncode": proc.returncode, "stat": args.stat, "content": content, "truncated": len(proc.stdout or proc.stderr or "") > len(content)}, ensure_ascii=False))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

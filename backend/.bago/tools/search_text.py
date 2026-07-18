#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from directory_context import DirectoryContextEngine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Hybrid text search over workspace context")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    root = Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()
    fragments, working_set = DirectoryContextEngine(root).retrieve(
        args.query,
        limit_files=max(3, args.limit),
        limit_symbols=max(4, args.limit),
    )
    print(json.dumps({"ok": True, "query": args.query, "fragments": fragments[: args.limit], "working_set": working_set}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from _path_helper import ensure_core_path
ensure_core_path()  # noqa: E402
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

def _self_test() -> int:
    """Minimal R001 self-test: verify this tool compiles."""
    import py_compile
    py_compile.compile(__file__, doraise=True)
    print(f"{__file__}: self-test ok")
    return 0

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())

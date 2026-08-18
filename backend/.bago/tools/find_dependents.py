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
    parser = argparse.ArgumentParser(description="Find files depending on a path")
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    root = Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()
    target = args.path.replace("\\", "/").lstrip("./")
    snapshot = DirectoryContextEngine(root).ensure_snapshot()
    graph = snapshot.get("graph", {})
    print(json.dumps({
        "ok": True,
        "path": target,
        "dependents": graph.get("dependents", {}).get(target, []),
        "tests": graph.get("tests_by_file", {}).get(target, []),
    }, ensure_ascii=False))
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

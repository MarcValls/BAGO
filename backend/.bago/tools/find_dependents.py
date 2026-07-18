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


if __name__ == "__main__":
    raise SystemExit(main())

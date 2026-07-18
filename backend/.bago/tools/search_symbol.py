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
    parser = argparse.ArgumentParser(description="Search symbols in the BAGO directory context index")
    parser.add_argument("--name", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    root = Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()
    snapshot = DirectoryContextEngine(root).ensure_snapshot()
    needle = args.name.lower()
    matches = []
    for symbol in snapshot.get("symbols", []):
        name = str(symbol.get("name", "")).lower()
        qualified = str(symbol.get("qualified_name", "")).lower()
        if needle == name or needle == qualified or needle in name or needle in qualified:
            matches.append(symbol)
    matches.sort(key=lambda item: (str(item.get("qualified_name", "")).lower() != needle, str(item.get("path", ""))))
    print(json.dumps({"ok": True, "query": args.name, "matches": matches[: max(1, args.limit)]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

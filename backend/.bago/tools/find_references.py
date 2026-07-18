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
    parser = argparse.ArgumentParser(description="Find references recorded for a symbol")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    root = Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()
    snapshot = DirectoryContextEngine(root).ensure_snapshot()
    needle = args.symbol.lower()
    matches = []
    for symbol in snapshot.get("symbols", []):
        if needle in str(symbol.get("name", "")).lower() or needle in str(symbol.get("qualified_name", "")).lower():
            matches.append({
                "path": symbol.get("path"),
                "symbol": symbol.get("qualified_name"),
                "kind": symbol.get("kind"),
                "references": symbol.get("references", []),
                "imports": symbol.get("imports", []),
            })
    print(json.dumps({"ok": True, "symbol": args.symbol, "matches": matches[: max(1, args.limit)]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from directory_context import DirectoryContextEngine  # noqa: E402


def workspace_root() -> Path:
    return Path(os.environ.get("BAGO_WORKSPACE_ROOT") or os.getcwd()).resolve()


def main() -> int:
    root = workspace_root()
    engine = DirectoryContextEngine(root)
    snapshot = engine.ensure_snapshot()
    print(json.dumps({"ok": True, "repository_map": snapshot.get("repository_map", {})}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

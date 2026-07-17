#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"
UI_REACT_ROOT = ROOT / "ui-react"
FRONTEND_DIST = FRONTEND_ROOT / "dist"
UI_REACT_DIST = UI_REACT_ROOT / "dist"


def _run(args: list[str]) -> None:
    subprocess.run(args, cwd=FRONTEND_ROOT, check=True)


def main() -> int:
    _run(["npm.cmd", "run", "build"])
    if UI_REACT_DIST.exists():
        shutil.rmtree(UI_REACT_DIST)
    shutil.copytree(FRONTEND_DIST, UI_REACT_DIST)
    print(f"Synced {FRONTEND_DIST} -> {UI_REACT_DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

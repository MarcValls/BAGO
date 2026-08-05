#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"
UI_REACT_ROOT = ROOT / "ui-react"
FRONTEND_DIST = FRONTEND_ROOT / "dist"
UI_REACT_DIST = UI_REACT_ROOT / "dist"

FORBIDDEN_UI_MARKERS = (
    "ses_01JY8K",
    "canon-rc4",
    "Integración React + Manager",
    "Solicitud registrada. El backend deberá validar",
)
REQUIRED_UI_MARKERS = (
    "BAGO Control Plane",
    "/api/v1/ui/bootstrap",
    "/chat",
)


def _run(args: list[str]) -> None:
    subprocess.run(args, cwd=FRONTEND_ROOT, check=True)


def validate_interactive_dist(dist: Path) -> None:
    index = dist / "index.html"
    assets = dist / "assets"
    if not index.is_file():
        raise RuntimeError(f"UI index missing: {index}")

    javascript = sorted(assets.glob("*.js")) if assets.is_dir() else []
    if not javascript:
        raise RuntimeError(f"UI JavaScript bundle missing: {assets}")

    payload = "\n".join(
        [index.read_text(encoding="utf-8", errors="replace")]
        + [path.read_text(encoding="utf-8", errors="replace") for path in javascript]
    )
    forbidden = [marker for marker in FORBIDDEN_UI_MARKERS if marker in payload]
    if forbidden:
        raise RuntimeError(f"Mock UI markers found in {dist}: {', '.join(forbidden)}")

    missing = [marker for marker in REQUIRED_UI_MARKERS if marker not in payload]
    if missing:
        raise RuntimeError(f"Interactive UI markers missing in {dist}: {', '.join(missing)}")


def main() -> int:
    _run(["npm.cmd" if os.name == "nt" else "npm", "run", "build"])
    validate_interactive_dist(FRONTEND_DIST)
    if UI_REACT_DIST.exists():
        shutil.rmtree(UI_REACT_DIST)
    shutil.copytree(FRONTEND_DIST, UI_REACT_DIST)
    validate_interactive_dist(UI_REACT_DIST)
    print(f"Synced {FRONTEND_DIST} -> {UI_REACT_DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_ui_dist.py"
SPEC = importlib.util.spec_from_file_location("build_ui_dist", SCRIPT)
assert SPEC and SPEC.loader
BUILD_UI_DIST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_UI_DIST)


def write_dist(root: Path, javascript: str, title: str = "BAGO Control Plane") -> Path:
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text(f"<title>{title}</title>", encoding="utf-8")
    (assets / "index.js").write_text(javascript, encoding="utf-8")
    return root


def test_interactive_dist_accepts_real_backend_contract(tmp_path: Path) -> None:
    dist = write_dist(tmp_path, 'fetch("/api/v1/ui/bootstrap"); fetch("/chat");')

    BUILD_UI_DIST.validate_interactive_dist(dist)


@pytest.mark.parametrize("marker", BUILD_UI_DIST.FORBIDDEN_UI_MARKERS)
def test_interactive_dist_rejects_mock_markers(tmp_path: Path, marker: str) -> None:
    dist = write_dist(
        tmp_path,
        f'fetch("/api/v1/ui/bootstrap"); fetch("/chat"); const stale = {marker!r};',
    )

    with pytest.raises(RuntimeError, match="Mock UI markers found"):
        BUILD_UI_DIST.validate_interactive_dist(dist)

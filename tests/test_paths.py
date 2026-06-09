from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / ".bago" / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import paths


def test_source_base_dir() -> None:
    assert paths.source_base_dir() == ROOT


def test_app_base_dir_source_mode() -> None:
    assert paths.app_base_dir() == ROOT


def test_bundle_base_dir_and_resource_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(tmp_path / "BAGO.exe"), raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert paths.app_base_dir() == tmp_path
    assert paths.bundle_base_dir() == tmp_path
    assert paths.resource_path("assets", "logo.png") == tmp_path / "assets" / "logo.png"
    assert paths.external_program_path("tool.py", "tool.exe") == tmp_path / "tool.exe"

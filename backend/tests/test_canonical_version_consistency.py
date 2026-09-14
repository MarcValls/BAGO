from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_version_consistency.py"


def _module():
    spec = importlib.util.spec_from_file_location("canonical_version_consistency", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fixture(root: Path, version: str = "4.9.3") -> None:
    (root / "frontend" / "public").mkdir(parents=True)
    (root / "electron-viewer").mkdir()
    (root / "backend").mkdir()
    (root / "release_version.txt").write_text(version + "\n", encoding="utf-8")
    (root / "backend" / "release_version.txt").write_text(version + "\n", encoding="utf-8")
    for path in (root / "package.json", root / "frontend" / "package.json", root / "electron-viewer" / "package.json", root / "frontend" / "public" / "ui_config.json"):
        path.write_text(json.dumps({"version": version}), encoding="utf-8")


def test_canonical_versions_accept_the_root_authority(tmp_path: Path) -> None:
    fixture = tmp_path / "repo"
    _write_fixture(fixture)
    _module().validate(fixture)


def test_canonical_versions_reject_deliberate_root_authority_drift(tmp_path: Path) -> None:
    fixture = tmp_path / "repo"
    _write_fixture(fixture)
    (fixture / "release_version.txt").write_text("4.9.4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="release_version.txt='4.9.4'"):
        _module().validate(fixture)


def test_required_validate_workflow_runs_version_consistency_check() -> None:
    workflow = (ROOT / ".github" / "workflows" / "validate-expected.yml").read_text(encoding="utf-8")
    assert "Validate canonical version consistency" in workflow
    assert "python scripts/verify_version_consistency.py" in workflow


def test_branch_protection_defaults_cover_all_base_branches() -> None:
    script = (ROOT / "backend" / "scripts" / "apply_branch_protection.ps1").read_text(encoding="utf-8")
    assert '@("main", "windows", "android")' in script

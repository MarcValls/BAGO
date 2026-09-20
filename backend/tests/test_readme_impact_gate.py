from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_readme_impact.py"


def _module():
    spec = importlib.util.spec_from_file_location("verify_readme_impact", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_execution_boundary_change_requires_readme_update() -> None:
    module = _module()
    errors = module.validate_impact(["backend/.bago/core/execution_gateway.py"])

    assert errors
    assert "README update required" in errors[0]


def test_installation_change_requires_readme_update() -> None:
    module = _module()
    errors = module.validate_impact(["releases/bago-installer.nsi"])

    assert errors
    assert any("installation, release or lifecycle" in item for item in errors)


def test_readme_in_same_diff_satisfies_impact_gate() -> None:
    module = _module()

    assert module.validate_impact(
        ["backend/.bago/core/execution_gateway.py", "README.md"]
    ) == []


def test_unrelated_internal_test_change_does_not_require_readme() -> None:
    module = _module()

    assert module.validate_impact(["backend/tests/test_example.py"]) == []


def test_windows_paths_are_normalized() -> None:
    module = _module()
    errors = module.validate_impact(
        [r"backend\.bago\core\authorization_boundary.py"]
    )

    assert errors

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_readme_freshness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_readme_freshness", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_readme_matches_canonical_repository_truth():
    module = _load_module()
    assert module.validate_static_truth(REPO_ROOT) == []


def test_readme_impact_gate_requires_readme_for_execution_boundary_changes():
    module = _load_module()
    errors = module.validate_impact(
        ["backend/.bago/core/execution_gateway.py"]
    )
    assert errors
    assert "README update required" in errors[0]


def test_readme_impact_gate_accepts_same_diff_when_readme_is_updated():
    module = _load_module()
    assert module.validate_impact(
        ["backend/.bago/core/execution_gateway.py", "README.md"]
    ) == []


def test_readme_impact_gate_ignores_unrelated_test_change():
    module = _load_module()
    assert module.validate_impact(
        ["backend/tests/test_unrelated_example.py"]
    ) == []

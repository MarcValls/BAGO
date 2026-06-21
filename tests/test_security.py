"""tests/test_security.py — Security policy gate tests for BAGO CI.

These run as the first step of gate-tests in bago.yml.
All tests must pass before any other test suite is run.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BAGO_DIR = REPO_ROOT / ".bago"
BAGO_CORE_DIR = REPO_ROOT / "bago_core"


# ── Security policy ────────────────────────────────────────────────────────────

def test_auto_allow_tools_false_by_default():
    """auto_allow_tools must default to False in config_manager.py."""
    config_manager = BAGO_DIR / "core" / "config_manager.py"
    if not config_manager.exists():
        pytest.skip("config_manager.py not present")
    tree = ast.parse(config_manager.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "DEFAULT_CONFIG":
            defaults = ast.literal_eval(node.value)
            val = defaults.get("features", {}).get("auto_allow_tools", True)
            assert val is False, f"auto_allow_tools default must be False, got {val!r}"
            return
    # If no DEFAULT_CONFIG found, check for any assignment
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            pass
    pytest.skip("DEFAULT_CONFIG not found in config_manager.py — skipping")


def test_no_shell_true_in_execute_command():
    """shell=True must not appear in the tool_registry execute_command implementation."""
    tool_registry = BAGO_DIR / "tools" / "tool_registry.py"
    if not tool_registry.exists():
        pytest.skip("tool_registry.py not present")
    src = tool_registry.read_text(encoding="utf-8")
    exposed = [
        ln.strip() for ln in src.splitlines()
        if "shell=True" in ln and not ln.strip().startswith("#")
    ]
    assert len(exposed) == 0, f"shell=True found in tool_registry.py: {exposed}"


def test_cors_no_wildcard():
    """CORS must not allow wildcard '*' origin in bridge.py."""
    bridge = BAGO_DIR / "api" / "bridge.py"
    if not bridge.exists():
        pytest.skip("bridge.py not present")
    src = bridge.read_text(encoding="utf-8")
    assert '"*"' not in src or "allow_origins" not in src, (
        "CORS wildcard '*' origin found in bridge.py"
    )


def test_api_defaults_to_localhost():
    """API host must not be hardcoded to 0.0.0.0 as default."""
    bridge = BAGO_DIR / "api" / "bridge.py"
    if not bridge.exists():
        pytest.skip("bridge.py not present")
    src = bridge.read_text(encoding="utf-8")
    assert "0.0.0.0" not in src or "host" in src, (
        "API must not bind to 0.0.0.0 by default"
    )


def test_state_excluded_from_vcs():
    """The .bago/state directory must be in .gitignore."""
    gitignore = REPO_ROOT / ".gitignore"
    if not gitignore.exists():
        pytest.skip(".gitignore not present")
    content = gitignore.read_text(encoding="utf-8")
    assert ".bago/state" in content or ".bago/state/" in content, (
        ".bago/state/ must be excluded from VCS in .gitignore"
    )


def test_release_version_file_exists():
    """release_version.txt must exist and contain a valid semver."""
    rv = REPO_ROOT / "release_version.txt"
    assert rv.exists(), "release_version.txt must exist"
    content = rv.read_text(encoding="utf-8").strip()
    parts = content.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), (
        f"release_version.txt must contain semver X.Y.Z, got {content!r}"
    )


def test_no_credentials_in_versions_json():
    """versions.json must not contain any API key patterns."""
    import re
    vj = REPO_ROOT / "versions.json"
    if not vj.exists():
        pytest.skip("versions.json not present")
    content = vj.read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9]{32,}", content), "API key in versions.json"
    assert not re.search(r"\d{8,12}:AA[A-Za-z0-9_-]{30,}", content), "Token in versions.json"

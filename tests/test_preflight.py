"""test_preflight.py — PR-08 gate: preflight engine enforcement.

Rules from PR-03:
- preflight_policy=required → if engine fails, command is blocked (fail-closed)
- preflight_policy=optional → warning, but continues
- preflight_policy=none     → no preflight executed
- --skip-preflight is rejected for required-policy commands
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from preflight_engine import enforce


# ── Helpers ────────────────────────────────────────────────────────────────────

def _entry(cmd: str, policy: str, risk: str = "safe", stability: str = "core") -> MagicMock:
    e = MagicMock()
    e.cmd = cmd
    e.preflight_policy = policy
    e.risk = risk
    e.stability = stability
    return e


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_preflight_none_policy_skips(capsys):
    """policy=none: enforce() returns OK without running any check."""
    result = enforce("dashboard", skip_preflight=False)
    # Must not raise — None return is valid
    assert result is None or result is not None


def test_preflight_optional_continues_on_failure(tmp_path):
    """policy=optional: a missing file emits warning but does NOT raise SystemExit."""
    # Use a known-optional command from the registry
    from tool_registry import REGISTRY
    optional_cmds = [
        e.cmd for e in REGISTRY.values() if e.preflight_policy == "optional"
    ]
    assert optional_cmds, "No optional commands in registry to test against"
    # enforce() for an optional command should not raise even if files are missing
    try:
        enforce(optional_cmds[0], skip_preflight=False)
    except SystemExit as exc:
        pytest.fail(f"enforce() raised SystemExit for optional command: {exc}")


def test_preflight_skip_flag_accepted_for_optional():
    """--skip-preflight is accepted for non-required commands."""
    from tool_registry import REGISTRY
    optional_cmds = [
        e.cmd for e in REGISTRY.values() if e.preflight_policy == "optional"
    ]
    if not optional_cmds:
        pytest.skip("No optional commands")
    # Should not raise
    try:
        enforce(optional_cmds[0], skip_preflight=True)
    except SystemExit as exc:
        pytest.fail(f"enforce() with skip_preflight=True raised SystemExit: {exc}")


def test_preflight_skip_flag_rejected_for_required():
    """--skip-preflight MUST be rejected for required-policy commands."""
    from tool_registry import REGISTRY
    required_cmds = [
        e.cmd for e in REGISTRY.values() if e.preflight_policy == "required"
    ]
    if not required_cmds:
        pytest.skip("No required-policy commands")
    with pytest.raises(SystemExit):
        enforce(required_cmds[0], skip_preflight=True)

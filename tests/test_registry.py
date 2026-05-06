"""test_registry.py — PR-08 gate: registry contract enforcement.

Rules:
- Every entry has a non-empty module
- Every entry has a risk (safe / mutating / dangerous)
- Every entry has a stability (core / experimental / legacy / dangerous / internal)
- Every entry has a preflight_policy (required / optional / none)
- Deprecated entries must have a see_also value
- No duplicate cmd keys
"""
from __future__ import annotations

import pytest
from tool_registry import REGISTRY, ToolEntry

VALID_RISKS        = {"safe", "mutating", "dangerous"}
VALID_STABILITIES  = {"core", "experimental", "legacy", "dangerous", "internal"}
VALID_POLICIES     = {"required", "optional", "none"}


@pytest.fixture(scope="module")
def all_entries() -> list[ToolEntry]:
    return list(REGISTRY.values())


def test_registry_not_empty(all_entries):
    """Registry must have at least one command."""
    assert len(all_entries) > 0, "REGISTRY is empty"


def test_no_duplicate_cmd_keys():
    """CMD keys in REGISTRY must be unique — dict guarantees this, verify directly."""
    keys = list(REGISTRY.keys())
    assert len(keys) == len(set(keys)), "Duplicate keys found in REGISTRY"


def test_all_entries_have_module(all_entries):
    """Every ToolEntry must declare a module."""
    missing = [e.cmd for e in all_entries if not e.module or not e.module.strip()]
    assert not missing, f"Entries with empty module: {missing}"


def test_all_entries_have_risk(all_entries):
    """Every ToolEntry must have a recognised risk level."""
    bad = [
        f"{e.cmd}={e.risk!r}"
        for e in all_entries
        if not e.risk or e.risk not in VALID_RISKS
    ]
    assert not bad, f"Entries with invalid risk: {bad}"


def test_all_entries_have_stability(all_entries):
    """Every ToolEntry must have a recognised stability label."""
    bad = [
        f"{e.cmd}={e.stability!r}"
        for e in all_entries
        if not e.stability or e.stability not in VALID_STABILITIES
    ]
    assert not bad, f"Entries with invalid stability: {bad}"


def test_all_entries_have_preflight_policy(all_entries):
    """Every ToolEntry must declare a preflight_policy."""
    bad = [
        f"{e.cmd}={e.preflight_policy!r}"
        for e in all_entries
        if not e.preflight_policy or e.preflight_policy not in VALID_POLICIES
    ]
    assert not bad, f"Entries with invalid preflight_policy: {bad}"


def test_deprecated_entries_have_see_also(all_entries):
    """Deprecated commands must point to a replacement via see_also."""
    bad = [
        e.cmd
        for e in all_entries
        if e.deprecated and (not e.see_also or not e.see_also.strip())
    ]
    assert not bad, f"Deprecated entries without see_also: {bad}"


def test_core_commands_have_required_preflight(all_entries):
    """Core commands must have preflight_policy=required."""
    bad = [
        f"{e.cmd}(policy={e.preflight_policy!r})"
        for e in all_entries
        if e.stability == "core" and e.preflight_policy != "required"
    ]
    assert not bad, f"Core commands without required preflight: {bad}"


def test_dangerous_commands_have_dangerous_risk(all_entries):
    """Commands with stability=dangerous must have risk=dangerous."""
    bad = [
        f"{e.cmd}(risk={e.risk!r})"
        for e in all_entries
        if e.stability == "dangerous" and e.risk != "dangerous"
    ]
    assert not bad, f"Dangerous-stability commands with non-dangerous risk: {bad}"

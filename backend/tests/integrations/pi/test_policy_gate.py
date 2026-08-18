"""Tests del policy_gate."""
from __future__ import annotations

import pytest

from integrations.pi.contracts import CapabilityClaims
from integrations.pi.policy_gate import (
    check_claims,
    check_phase,
    decide_tool,
    deny_mutation,
    require_no_process,
)


def _claims(**overrides) -> CapabilityClaims:
    base = dict(
        filesystem_read=False,
        filesystem_read_root="",
        filesystem_write=False,
        process_spawn=False,
        network_mode="none",
        tools_allowed=(),
        skills_imported_ids=(),
        extensions_allowed=(),
        packages_allowed=(),
        auth_source="bago_secret_broker",
        session_authority="bago",
        provider_selection_authority="bago",
        completion_authority="bago_validator",
    )
    base.update(overrides)
    return CapabilityClaims(**base)


def test_phase_zero_allows_only_quarantine() -> None:
    decision = check_phase(0, 0)
    assert decision.allowed
    assert decision.reason_code == "PI_PHASE_OK"


def test_phase_above_max_denied() -> None:
    decision = check_phase(1, 0)
    assert not decision.allowed
    assert decision.reason_code == "PI_PHASE_LOCKED"


def test_invalid_phase_rejected() -> None:
    decision = check_phase(5, 4)
    assert not decision.allowed


def test_filesystem_write_always_denied() -> None:
    decision = check_claims(
        _claims(filesystem_write=True), phase=2, max_phase=3
    )
    assert not decision.allowed
    assert decision.reason_code == "PI_MUTATION_PHASE_LOCKED"


def test_process_spawn_denied_in_phase_0() -> None:
    decision = check_claims(
        _claims(process_spawn=True), phase=0, max_phase=3
    )
    assert not decision.allowed
    assert decision.reason_code == "PROCESS_CAPABILITY_DENIED"


def test_process_spawn_allowed_only_from_phase_2() -> None:
    # En Fase 0/1 process_spawn está bloqueado. En Fase 2 podría estar
    # permitido en el futuro, pero hoy siempre lo denegamos a través
    # de require_no_process.
    assert not require_no_process(_claims(process_spawn=True)).allowed
    assert require_no_process(_claims()).allowed


def test_skills_imported_ids_rejected() -> None:
    decision = check_claims(
        _claims(skills_imported_ids=("x",)), phase=2, max_phase=3
    )
    assert not decision.allowed
    assert decision.reason_code == "PI_AUTOLOAD_SOURCE_DETECTED"


def test_extensions_rejected() -> None:
    decision = check_claims(
        _claims(extensions_allowed=("y",)), phase=2, max_phase=3
    )
    assert not decision.allowed
    assert decision.reason_code == "PI_EXTENSION_DENIED"


def test_packages_rejected() -> None:
    decision = check_claims(
        _claims(packages_allowed=("z",)), phase=2, max_phase=3
    )
    assert not decision.allowed
    assert decision.reason_code == "PI_EXTENSION_DENIED"


def test_completion_authority_must_be_bago() -> None:
    decision = check_claims(
        _claims(completion_authority="self"), phase=2, max_phase=3
    )
    assert not decision.allowed


def test_network_mode_rejected_when_invalid() -> None:
    decision = check_claims(
        _claims(network_mode="wildcard"), phase=2, max_phase=3
    )
    assert not decision.allowed
    assert decision.reason_code == "PI_NETWORK_MODE_DENIED"


def test_tools_require_phase_2_or_higher() -> None:
    claims = _claims(
        tools_allowed=("read",),
        filesystem_read=True,
        filesystem_read_root="/tmp/x",
    )
    decision = check_claims(claims, phase=1, max_phase=3)
    assert not decision.allowed


def test_tools_allowlisted() -> None:
    claims = _claims(
        tools_allowed=("read", "unknown_tool"),
        filesystem_read=True,
        filesystem_read_root="/tmp/x",
    )
    decision = check_claims(claims, phase=2, max_phase=3)
    assert not decision.allowed
    assert decision.reason_code == "TOOL_NOT_ALLOWED"


def test_decide_tool_without_claim_denied() -> None:
    claims = _claims()
    decision = decide_tool(claims, "read")
    assert not decision.allowed


def test_decide_tool_with_claim_allowed() -> None:
    claims = _claims(
        tools_allowed=("read",),
        filesystem_read=True,
        filesystem_read_root="/tmp/x",
    )
    decision = decide_tool(claims, "read")
    assert decision.allowed


def test_deny_mutation_returns_denial() -> None:
    decision = deny_mutation("write attempted")
    assert not decision.allowed
    assert decision.reason_code == "PI_MUTATION_PHASE_LOCKED"
    assert decision.details.get("reason") == "write attempted"

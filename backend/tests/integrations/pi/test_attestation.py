"""Fase 1 — tests de attestation.

Verifica que el comparador requested vs effective rechaza:
    - drift de provider/modelo
    - drift de credential_ref
    - bridge_version incompatible
    - sidecar_artifact_hash o pi_lockfile_hash no coincidentes
    - fallback_used=true o auto_selection_used=true no permitidos
    - result != MATCH cuando fail_on_provider_drift
"""
from __future__ import annotations

import pytest

from integrations.pi.attestation import AttestationPolicy, verify, _coerce_attestation
from integrations.pi.errors import (
    BridgeError,
    BridgeIntegrityMismatch,
    ProviderAttestationMismatch,
    ProviderFallbackDenied,
)


def _payload(**overrides) -> dict:
    base = {
        "requested_provider": "bago-pi-mock",
        "effective_provider": "bago-pi-mock",
        "requested_model": "mock-1",
        "effective_model": "mock-1",
        "endpoint_normalized": "mock://bago-pi-bridge/bago-pi-mock",
        "adapter": "mock",
        "bridge_version": "0.1.0",
        "pi_package_version": "0.0.0-mock",
        "pi_lockfile_hash": "abcdef0123456789",
        "sidecar_artifact_hash": "1234567890abcdef",
        "credential_ref": "ref-bago-mock",
        "fallback_used": False,
        "auto_selection_used": False,
        "config_effective": {"network_mode": "none"},
        "result": "MATCH",
    }
    base.update(overrides)
    return base


def test_attestation_match_returns_attestation() -> None:
    policy = AttestationPolicy()
    out = verify(_payload(), expected_credential_ref="ref-bago-mock", policy=policy)
    assert out.result == "MATCH"
    assert out.is_match()


def test_attestation_rejects_provider_drift() -> None:
    policy = AttestationPolicy()
    with pytest.raises(ProviderAttestationMismatch):
        verify(
            _payload(effective_provider="rogue-provider"),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )


def test_attestation_rejects_model_drift() -> None:
    policy = AttestationPolicy()
    with pytest.raises(ProviderAttestationMismatch):
        verify(
            _payload(effective_model="rogue-model"),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )


def test_attestation_rejects_credential_ref_drift() -> None:
    policy = AttestationPolicy()
    with pytest.raises(BridgeError) as exc:
        verify(
            _payload(credential_ref="rogue-ref"),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )
    assert "credential_ref drift" in str(exc.value.reason)


def test_attestation_rejects_bridge_version_drift() -> None:
    policy = AttestationPolicy()
    with pytest.raises(BridgeError) as exc:
        verify(
            _payload(bridge_version="0.2.0"),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )
    assert "bridge_version mismatch" in str(exc.value.reason)


def test_attestation_rejects_sidecar_hash_drift() -> None:
    policy = AttestationPolicy(expected_sidecar_hash="expected-hash")
    with pytest.raises(BridgeIntegrityMismatch):
        verify(
            _payload(sidecar_artifact_hash="rogue-hash"),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )


def test_attestation_rejects_lockfile_hash_drift() -> None:
    policy = AttestationPolicy(expected_lockfile_hash="expected-lockfile")
    with pytest.raises(BridgeIntegrityMismatch):
        verify(
            _payload(pi_lockfile_hash="rogue-lockfile"),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )


def test_attestation_rejects_fallback() -> None:
    policy = AttestationPolicy(allow_fallback=False)
    with pytest.raises(ProviderFallbackDenied):
        verify(
            _payload(fallback_used=True),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )


def test_attestation_rejects_auto_selection() -> None:
    policy = AttestationPolicy(allow_auto_selection=False)
    with pytest.raises(ProviderFallbackDenied):
        verify(
            _payload(auto_selection_used=True),
            expected_credential_ref="ref-bago-mock",
            policy=policy,
        )


def test_attestation_allow_fallback_when_policy_permits() -> None:
    policy = AttestationPolicy(allow_fallback=True, allow_auto_selection=True)
    # Para que pase la verificación de drift, debemos hacer que effective
    # coincida con requested (sigue siendo MATCH).
    out = verify(
        _payload(fallback_used=True, auto_selection_used=True),
        expected_credential_ref="ref-bago-mock",
        policy=policy,
    )
    assert out.fallback_used is True
    assert out.auto_selection_used is True


def test_attestation_rejects_result_mismatch_when_drift_disabled() -> None:
    # fail_on_provider_drift=False desactiva la verificación estricta.
    policy = AttestationPolicy(fail_on_provider_drift=False)
    out = verify(
        _payload(effective_provider="rogue", result="MISMATCH"),
        expected_credential_ref="ref-bago-mock",
        policy=policy,
    )
    assert out.result == "MISMATCH"
    assert not out.is_match()


def test_attestation_rejects_invalid_result_value() -> None:
    with pytest.raises(BridgeError):
        _coerce_attestation(_payload(result="UNKNOWN"))


def test_attestation_rejects_missing_fields() -> None:
    payload = _payload()
    payload.pop("adapter")
    with pytest.raises(BridgeError):
        _coerce_attestation(payload)

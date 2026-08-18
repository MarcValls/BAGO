"""Fase 1 — tests de receipt_factory.

Verifica que el bundle emitido:
    1. Reutiliza el `ContextReceipt` canónico de BAGO.
    2. Estado final como máximo `EXECUTION_COMPLETED_UNVERIFIED`.
    3. La attestation efectiva se almacena en metadata.
    4. La respuesta consolidada se extrae de los deltas.
    5. Los hashes del log se preservan en bridge_metadata.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from integrations.pi.attestation import AttestationPolicy
from integrations.pi.contracts import (
    BridgeExecutionRequest,
    CapabilityClaims,
    ProviderAttestation,
    make_event,
)
from integrations.pi.event_capture import EventLog
from integrations.pi.receipt_factory import build_receipt


def _att() -> ProviderAttestation:
    return ProviderAttestation(
        requested_provider="bago-pi-mock",
        effective_provider="bago-pi-mock",
        requested_model="mock-1",
        effective_model="mock-1",
        endpoint_normalized="mock://bago-pi-bridge/bago-pi-mock",
        adapter="mock",
        bridge_version="0.1.0",
        pi_package_version="0.0.0-mock",
        pi_lockfile_hash="abc123",
        sidecar_artifact_hash="def456",
        credential_ref="ref-bago-mock",
        fallback_used=False,
        auto_selection_used=False,
        config_effective={"network_mode": "none"},
        result="MATCH",
    )


def _request() -> BridgeExecutionRequest:
    now = datetime.now(timezone.utc)
    return BridgeExecutionRequest(
        protocol_version="0.1.0",
        bridge_request_id="br-1",
        execution_id="exec-1",
        correlation_id="c-1",
        request_nonce=f"nonce-{time.time_ns()}",
        issued_at=now.isoformat(),
        deadline=(now + timedelta(seconds=60)).isoformat(),
        session_id="sess-1",
        session_revision="rev-1",
        workspace_id="ws-1",
        project_root=".",
        workspace_root=".",
        workspace_scope_root=".",
        context_envelope_id="env-1",
        context_envelope_digest="env-1",
        policy_profile="provider_only",
        policy_digest="phase-1",
        capability_claims=CapabilityClaims(),
        requested_provider="bago-pi-mock",
        requested_model="mock-1",
        credential_ref="ref-bago-mock",
        input={"system": "you are bago", "messages": [{"role": "user", "content": "hi"}]},
        output_limits={"max_tokens": 10},
    )


def _log_with_provider_only() -> tuple[EventLog, list]:
    log = EventLog(execution_id="exec-1")
    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log.append(e1)
    e2 = make_event(
        execution_id="exec-1", sequence_number=2, event_id="e2",
        event_type="provider_attested", payload={}, previous_event_hash=e1.event_hash,
    )
    log.append(e2)
    e3 = make_event(
        execution_id="exec-1", sequence_number=3, event_id="e3",
        event_type="model_output_delta", payload={"delta": "hello "},
        previous_event_hash=e2.event_hash,
    )
    log.append(e3)
    e4 = make_event(
        execution_id="exec-1", sequence_number=4, event_id="e4",
        event_type="model_output_delta", payload={"delta": "world"},
        previous_event_hash=e3.event_hash,
    )
    log.append(e4)
    e5 = make_event(
        execution_id="exec-1", sequence_number=5, event_id="e5",
        event_type="usage_reported", payload={"input_tokens": 2, "output_tokens": 2, "total_tokens": 4},
        previous_event_hash=e4.event_hash,
    )
    log.append(e5)
    e6 = make_event(
        execution_id="exec-1", sequence_number=6, event_id="e6",
        event_type="pi_finished", payload={"finish_reason": "stop"},
        previous_event_hash=e5.event_hash,
    )
    log.append(e6)
    return log, [e1, e2, e3, e4, e5, e6]


def test_receipt_uses_canonical_context_receipt() -> None:
    log, _ = _log_with_provider_only()
    bundle = build_receipt(
        _request(),
        log,
        attestation=_att(),
        attestation_policy=AttestationPolicy(),
    )
    cr = bundle.context_receipt
    # Debe tener los campos del ContextReceipt canónico.
    assert hasattr(cr, "envelope_id")
    assert hasattr(cr, "model_used")
    assert hasattr(cr, "finish_reason")
    assert hasattr(cr, "usage")
    assert cr.model_used == "mock-1"
    assert cr.finish_reason == "pi_finished"
    assert cr.usage["total_tokens"] == 4


def test_receipt_final_status_is_unverified_at_most() -> None:
    log, _ = _log_with_provider_only()
    bundle = build_receipt(
        _request(),
        log,
        attestation=_att(),
        attestation_policy=AttestationPolicy(),
    )
    assert bundle.final_status == "EXECUTION_COMPLETED_UNVERIFIED"
    # El estado nunca es done/verified/certified.
    assert "done" not in bundle.final_status
    assert "verified" not in bundle.final_status or "unverified" in bundle.final_status
    assert "certified" not in bundle.final_status


def test_receipt_without_attestation_is_rejected() -> None:
    log, _ = _log_with_provider_only()
    bundle = build_receipt(
        _request(),
        log,
        attestation=None,
        attestation_policy=AttestationPolicy(),
        rejection_reasons=["missing_attestation"],
    )
    assert bundle.final_status == "REJECTED"
    assert "missing_attestation" in bundle.rejection_reasons


def test_receipt_response_content_is_concatenated_deltas() -> None:
    log, _ = _log_with_provider_only()
    bundle = build_receipt(
        _request(),
        log,
        attestation=_att(),
        attestation_policy=AttestationPolicy(),
    )
    cr = bundle.context_receipt
    assert cr.response_content == "hello world"


def test_receipt_bridge_metadata_preserves_chain_hashes() -> None:
    log, _ = _log_with_provider_only()
    bundle = build_receipt(
        _request(),
        log,
        attestation=_att(),
        attestation_policy=AttestationPolicy(),
    )
    assert bundle.bridge_metadata["first_event_hash"] == log.first_hash()
    assert bundle.bridge_metadata["last_event_hash"] == log.last_hash()
    assert bundle.bridge_metadata["attestation"]["present"] is True
    assert bundle.bridge_metadata["attestation"]["result"] == "MATCH"


def test_receipt_to_dict_is_json_serializable() -> None:
    import json
    log, _ = _log_with_provider_only()
    bundle = build_receipt(
        _request(),
        log,
        attestation=_att(),
        attestation_policy=AttestationPolicy(),
    )
    payload = bundle.to_dict()
    # No debe lanzar TypeError.
    json.dumps(payload, default=str)
    assert "context_receipt" in payload
    assert "tool_receipts" in payload
    assert "final_status" in payload


def test_receipt_keeps_attestation_in_evidence_metadata() -> None:
    log, _ = _log_with_provider_only()
    bundle = build_receipt(
        _request(),
        log,
        attestation=_att(),
        attestation_policy=AttestationPolicy(),
    )
    cr = bundle.context_receipt
    bridge_meta = cr.metadata.get("bridge", {})
    assert bridge_meta["attestation"]["result"] == "MATCH"
    assert bridge_meta["attestation"]["effective_provider"] == "bago-pi-mock"
    assert bridge_meta["verification_state"] == "execution_completed_unverified"

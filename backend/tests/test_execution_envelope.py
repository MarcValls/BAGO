from __future__ import annotations

import pytest

from execution_envelope import (
    ExecutionEnvelopeError,
    build_execution_envelope,
)
from execution_request import build_execution_request


def _request():
    return build_execution_request(
        effect_id="filesystem.read",
        actor_kind="user",
        principal_id="test-user",
        session_id="session-envelope",
        source_surface="test",
        target={"path": "notes/example.txt"},
        arguments={},
    )


def test_envelope_binds_request_target_and_semantic_digest():
    envelope = build_execution_envelope(
        request=_request(),
        permit_token="permit-token",
        idempotency_key="idem-1",
        reversibility="reversible",
        evidence_parent="claim:parent",
    )
    assert envelope.effect_id == "filesystem.read"
    assert envelope.target_digest == envelope.request.target_digest
    assert envelope.public_descriptor()["request"]["operation_fingerprint"] == envelope.request.fingerprint
    assert envelope.semantic_digest == envelope.semantic_digest
    assert "permit_token" not in envelope.public_descriptor()


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("permit_token", "", "execution_envelope_permit_required"),
        ("idempotency_key", "", "execution_envelope_idempotency_required"),
        ("reversibility", "unknown", "execution_envelope_reversibility_invalid"),
    ],
)
def test_envelope_rejects_incomplete_handoff(field, value, code):
    values = {
        "request": _request(),
        "permit_token": "permit-token",
        "idempotency_key": "idem-1",
        "reversibility": "reversible",
    }
    values[field] = value
    with pytest.raises(ExecutionEnvelopeError) as error:
        build_execution_envelope(**values)
    assert error.value.code == code


def test_envelope_does_not_accept_a_live_claim_as_authority():
    envelope = build_execution_envelope(
        request=_request(),
        permit_token="permit-token",
        idempotency_key="idem-2",
        reversibility="reversible",
        claim_id="claim-observation-only",
    )
    assert envelope.claim_id == "claim-observation-only"
    assert "claim_id" in envelope.public_descriptor()


def test_gateway_executes_envelope_and_keeps_claim_ownership_inside_gateway():
    from execution_adapter_contract import ExecutionContext
    from execution_gateway import EffectAdapterRegistry, ExecutionGateway

    class Boundary:
        def consume_permit(self, *, permit_token, request):
            return {"state": "consumed", "permit_id": permit_token, "effect_id": request.effect_id}

    class Adapter:
        effect_ids = frozenset({"filesystem.read"})

        def execute(self, request, context):
            assert "_execution_claim" not in context.services
            assert context.services["_authorization"]["state"] == "consumed"
            return {"executed": request.fingerprint}

    registry = EffectAdapterRegistry()
    registry.register(Adapter())
    envelope = build_execution_envelope(
        request=_request(),
        permit_token="permit-envelope",
        idempotency_key="idem-gateway",
        reversibility="reversible",
    )
    result, authorization = ExecutionGateway(Boundary(), adapters=registry).execute_envelope(
        envelope=envelope,
        context=ExecutionContext(),
    )
    assert result == {"executed": envelope.request.fingerprint}
    assert authorization["permit_id"] == "permit-envelope"

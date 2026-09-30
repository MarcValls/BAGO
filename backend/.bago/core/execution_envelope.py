"""Canonical envelope crossing the authorization/effect boundary.

The envelope carries transport-bound execution metadata around an immutable
``ExecutionRequest``.  It does not mint authority and it never accepts a
caller-supplied claim object; the gateway remains the owner of claim issuance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from effect_registry import REGISTRY
from execution_request import ExecutionRequest, stable_digest


EXECUTION_ENVELOPE_CONTRACT = "bago.execution-envelope/v1"


class ExecutionEnvelopeError(ValueError):
    def __init__(self, message: str, *, code: str = "execution_envelope_invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExecutionEnvelope:
    """Validated material execution handoff.

    ``permit_token`` is transport material and is excluded from the semantic
    fingerprint.  ``claim_id`` is informational only; a live claim is always
    resolved by ``ExecutionGateway`` after Permit consumption.
    """

    request: ExecutionRequest
    permit_token: str
    idempotency_key: str
    reversibility: str
    evidence_parent: str = ""
    claim_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.request, ExecutionRequest):
            raise ExecutionEnvelopeError("request must be an ExecutionRequest", code="execution_envelope_request_invalid")
        if not str(self.permit_token or "").strip():
            raise ExecutionEnvelopeError("permit_token is required", code="execution_envelope_permit_required")
        if not str(self.idempotency_key or "").strip():
            raise ExecutionEnvelopeError("idempotency_key is required", code="execution_envelope_idempotency_required")
        if self.reversibility not in {"reversible", "compensatable", "irreversible"}:
            raise ExecutionEnvelopeError(
                "reversibility must be reversible, compensatable, or irreversible",
                code="execution_envelope_reversibility_invalid",
            )
        if not isinstance(self.metadata, dict):
            raise ExecutionEnvelopeError("metadata must be an object", code="execution_envelope_metadata_invalid")
        if not REGISTRY.contains(self.request.effect_id):
            raise ExecutionEnvelopeError("request effect is not registered", code="execution_envelope_effect_invalid")

    @property
    def effect_id(self) -> str:
        return self.request.effect_id

    @property
    def target_digest(self) -> str:
        return self.request.target_digest

    @property
    def world_state_digest(self) -> str:
        return self.request.world_state_digest

    @property
    def semantic_payload(self) -> dict[str, Any]:
        return {
            "contract": EXECUTION_ENVELOPE_CONTRACT,
            "request_fingerprint": self.request.fingerprint,
            "effect_id": self.request.effect_id,
            "target_digest": self.request.target_digest,
            "world_state_digest": self.request.world_state_digest,
            "idempotency_key": self.idempotency_key,
            "reversibility": self.reversibility,
            "evidence_parent": self.evidence_parent,
            "metadata": self.metadata,
        }

    @property
    def semantic_digest(self) -> str:
        return stable_digest(self.semantic_payload)

    def public_descriptor(self) -> dict[str, Any]:
        return {
            **self.semantic_payload,
            "request": self.request.public_descriptor(),
            "claim_id": self.claim_id,
        }


def build_execution_envelope(
    *,
    request: ExecutionRequest,
    permit_token: str,
    idempotency_key: str,
    reversibility: str,
    evidence_parent: str = "",
    claim_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        request=request,
        permit_token=str(permit_token or "").strip(),
        idempotency_key=str(idempotency_key or "").strip(),
        reversibility=str(reversibility or "").strip().lower(),
        evidence_parent=str(evidence_parent or "").strip(),
        claim_id=str(claim_id or "").strip(),
        metadata=dict(metadata or {}),
    )


__all__ = [
    "EXECUTION_ENVELOPE_CONTRACT",
    "ExecutionEnvelope",
    "ExecutionEnvelopeError",
    "build_execution_envelope",
]

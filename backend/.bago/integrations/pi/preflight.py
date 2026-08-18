"""preflight.py — validación de una petición antes de invocar al sidecar.

`preflight()` aplica todos los gates que el PLAN exige ejecutar antes
de cualquier llamada al provider o al sidecar:
    1. Carga de `PiBridgeConfig` con defaults fail-closed.
    2. Validación del `ContextEnvelope` (digest, session revision,
       nonce freshness).
    3. Validación de `CapabilityClaims` con `policy_gate.check_claims`.
    4. Verificación de scope y de fuentes implícitas PI.
    5. Verificación de integridad del lockfile del sidecar (si existe).

Devuelve un `PreflightResult` con la decisión y los datos que el bridge
necesita para continuar.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PiBridgeConfig, load_config
from .contracts import BridgeExecutionRequest, CapabilityClaims
from .errors import (
    BridgeError,
    BridgeIntegrityMismatch,
    ContextEnvelopeRequired,
    DigestMismatch,
    NonceReplayDenied,
    PiAutoloadSourceDetected,
    SessionRevisionObsolete,
)
from .policy_gate import PolicyDecision, check_claims, check_phase
from .scope_validator import assert_within_scope, deny_implicit_pi_sources


@dataclass
class _NonceStore:
    _seen: dict[str, float] = field(default_factory=dict)
    _ttl_seconds: float = 3600.0

    def check_and_record(self, nonce: str) -> None:
        now = time.time()
        # Purga expirados.
        for key in [k for k, t in self._seen.items() if now - t > self._ttl_seconds]:
            del self._seen[key]
        if nonce in self._seen:
            raise NonceReplayDenied(
                "nonce already used",
                details={"nonce_prefix": nonce[:8]},
            )
        self._seen[nonce] = now


_NONCE_STORE = _NonceStore()


def _now_epoch() -> float:
    return time.time()


def _parse_iso(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _digest_envelope_id(envelope_id: str, observed: str) -> None:
    if envelope_id != observed:
        raise DigestMismatch(
            "context_envelope_digest mismatch",
            details={"envelope_id_prefix": envelope_id[:8]},
        )


@dataclass(frozen=True)
class PreflightResult:
    config: PiBridgeConfig
    request: BridgeExecutionRequest
    policy: PolicyDecision
    scope_root: str
    nonce_recorded: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.to_dict(),
            "scope_root": self.scope_root,
            "nonce_recorded": self.nonce_recorded,
            "protocol_version": self.request.protocol_version,
        }


def preflight(
    request_data: dict[str, Any],
    *,
    observed_envelope_digest: str,
    active_session_revision: str,
    phase: int = 0,
    config: PiBridgeConfig | None = None,
    integrations_dir: Path | None = None,
) -> PreflightResult:
    """Aplica todos los gates. Lanza `BridgeError` ante cualquier violación."""
    cfg = config or load_config()
    if not cfg.quarantine_mode:
        # Aunque la quarantine_mode esté apagada, Fase 0 no permite Fase 1+.
        pass

    # 1. Parseo y validación estructural.
    try:
        request = BridgeExecutionRequest.from_dict(request_data)
    except BridgeError:
        raise

    if not request.context_envelope_id:
        raise ContextEnvelopeRequired("envelope id missing")
    _digest_envelope_id(
        request.context_envelope_id, observed_envelope_digest
    )

    # 2. Vigencia temporal.
    issued = _parse_iso(request.issued_at)
    deadline = _parse_iso(request.deadline)
    now = _now_epoch()
    if now < issued - 1.0:
        raise BridgeError("request issued in the future", details={"issued_at": request.issued_at})
    if now > deadline:
        raise BridgeError("request past deadline", details={"deadline": request.deadline})
    if deadline - issued > 3600:
        raise BridgeError("request window too large", details={"seconds": deadline - issued})

    # 3. Revisión de sesión.
    if active_session_revision and active_session_revision != request.session_revision:
        raise SessionRevisionObsolete(
            "session revision drift",
            details={
                "active_prefix": active_session_revision[:8],
                "request_prefix": request.session_revision[:8],
            },
        )

    # 4. Nonce freshness.
    _NONCE_STORE.check_and_record(request.request_nonce)

    # 5. Capability claims.
    claims: CapabilityClaims = request.capability_claims
    policy = check_claims(claims, phase=phase, max_phase=cfg.max_phase)
    if not policy.allowed:
        raise BridgeError(policy.reason_code, details=policy.details)

    # Fase debe ser válida también.
    phase_decision = check_phase(phase, cfg.max_phase)
    if not phase_decision.allowed:
        raise BridgeError(phase_decision.reason_code, details=phase_decision.details)

    # 6. Scope y fuentes implícitas.
    scope_root = request.workspace_scope_root
    if claims.filesystem_read:
        # Verificamos que la raíz declarada efectivamente es la del scope
        # y que ningún ancestro escapa.
        try:
            assert_within_scope(claims.filesystem_read_root, scope_root)
        except BridgeError:
            raise
    detected = deny_implicit_pi_sources(scope_root)
    if detected:
        raise PiAutoloadSourceDetected(
            "implicit pi sources found in scope",
            details={"sources": detected},
        )

    # 7. Integridad de lockfile (opcional, sólo si existe).
    if integrations_dir is not None:
        lock = integrations_dir / "sidecar" / "package-lock.json"
        if lock.exists():
            actual = hashlib.sha256(lock.read_bytes()).hexdigest()
            expected = (cfg.raw or {}).get("sidecar_lockfile_hash")
            if expected and expected != actual:
                raise BridgeIntegrityMismatch(
                    "sidecar lockfile hash mismatch",
                    details={"expected": expected, "effective": actual},
                )

    return PreflightResult(
        config=cfg,
        request=request,
        policy=policy,
        scope_root=scope_root,
        nonce_recorded=True,
    )


__all__ = ["PreflightResult", "preflight"]

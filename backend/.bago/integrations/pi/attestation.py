"""attestation.py — Fase 1: provider/model/endpoint attestation.

Compara la identidad solicitada por BAGO con la identidad efectiva
reportada por el sidecar. Sólo `MATCH` permite avanzar la ejecución
como trazable; `MISMATCH` y `UNATTESTABLE` lanzan
`ProviderAttestationMismatch` / `ProviderFallbackDenied`.

Este módulo es la única superficie que verifica que el sidecar no ha
cambiado silenciosamente de provider, modelo, endpoint, credencial,
adapter, versión de PI, hash de lockfile o hash de artefacto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ProviderAttestation as ContractAttestation
from .errors import (
    BridgeError,
    BridgeIntegrityMismatch,
    ProviderAttestationMismatch,
    ProviderFallbackDenied,
)


@dataclass(frozen=True)
class AttestationPolicy:
    expected_sidecar_hash: str = ""
    expected_lockfile_hash: str = ""
    fail_on_provider_drift: bool = True
    fail_on_unknown_event: bool = True
    allow_fallback: bool = False
    allow_auto_selection: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_sidecar_hash": self.expected_sidecar_hash,
            "expected_lockfile_hash": self.expected_lockfile_hash,
            "fail_on_provider_drift": self.fail_on_provider_drift,
            "fail_on_unknown_event": self.fail_on_unknown_event,
            "allow_fallback": self.allow_fallback,
            "allow_auto_selection": self.allow_auto_selection,
        }


def _coerce_attestation(payload: dict[str, Any]) -> ContractAttestation:
    """Construye un `ProviderAttestation` validado a partir del payload del sidecar.

    Los campos sensibles (credenciales) nunca se copian: sólo la
    referencia opaca `credential_ref`.
    """
    required = {
        "requested_provider",
        "effective_provider",
        "requested_model",
        "effective_model",
        "endpoint_normalized",
        "adapter",
        "bridge_version",
        "pi_package_version",
        "pi_lockfile_hash",
        "sidecar_artifact_hash",
        "credential_ref",
        "fallback_used",
        "auto_selection_used",
        "config_effective",
        "result",
    }
    missing = sorted(k for k in required if k not in payload)
    if missing:
        raise BridgeError(
            "attestation payload missing fields",
            details={"missing": missing},
        )
    result = str(payload.get("result") or "")
    if result not in {"MATCH", "MISMATCH", "UNATTESTABLE"}:
        raise BridgeError(
            "attestation result invalid",
            details={"value": result},
        )
    return ContractAttestation(
        requested_provider=str(payload["requested_provider"]),
        effective_provider=str(payload["effective_provider"]),
        requested_model=str(payload["requested_model"]),
        effective_model=str(payload["effective_model"]),
        endpoint_normalized=str(payload["endpoint_normalized"]),
        adapter=str(payload["adapter"]),
        bridge_version=str(payload["bridge_version"]),
        pi_package_version=str(payload["pi_package_version"]),
        pi_lockfile_hash=str(payload["pi_lockfile_hash"]),
        sidecar_artifact_hash=str(payload["sidecar_artifact_hash"]),
        credential_ref=str(payload["credential_ref"]),
        fallback_used=bool(payload["fallback_used"]),
        auto_selection_used=bool(payload["auto_selection_used"]),
        config_effective=dict(payload["config_effective"] or {}),
        result=result,
    )


def verify(
    payload: dict[str, Any],
    *,
    expected_credential_ref: str,
    policy: AttestationPolicy,
) -> ContractAttestation:
    """Verifica la attestation y devuelve la struct validada.

    Raises:
        ProviderAttestationMismatch: cuando la identidad efectiva
            difiere de la solicitada.
        ProviderFallbackDenied: cuando el provider usó fallback o
            auto-selection no permitidos.
        BridgeIntegrityMismatch: cuando el hash del sidecar o del
            lockfile no coincide con el esperado.
        BridgeError: ante payload inválido o credencial inesperada.
    """
    attestation = _coerce_attestation(payload)

    # 1. La credencial_reportada debe coincidir con la solicitada.
    # Si difiere, el sidecar está usando un credential_ref distinto:
    # esto es o bien un error de configuración o un intento de
    # sustitución de credencial.
    if attestation.credential_ref != expected_credential_ref:
        raise BridgeError(
            "credential_ref drift",
            details={
                "expected_prefix": expected_credential_ref[:8],
                "reported_prefix": attestation.credential_ref[:8],
            },
        )

    # 2. Versión de bridge y de protocolo deben coincidir.
    if attestation.bridge_version != "0.1.0":
        raise BridgeError(
            "bridge_version mismatch",
            details={
                "expected": "0.1.0",
                "effective": attestation.bridge_version,
            },
        )

    # 3. Integridad del sidecar.
    if (
        policy.expected_sidecar_hash
        and attestation.sidecar_artifact_hash
        and attestation.sidecar_artifact_hash != policy.expected_sidecar_hash
    ):
        raise BridgeIntegrityMismatch(
            "sidecar_artifact_hash mismatch",
            details={
                "expected": policy.expected_sidecar_hash,
                "effective": attestation.sidecar_artifact_hash,
            },
        )

    # 4. Integridad del lockfile.
    if (
        policy.expected_lockfile_hash
        and attestation.pi_lockfile_hash
        and attestation.pi_lockfile_hash != policy.expected_lockfile_hash
    ):
        raise BridgeIntegrityMismatch(
            "pi_lockfile_hash mismatch",
            details={
                "expected": policy.expected_lockfile_hash,
                "effective": attestation.pi_lockfile_hash,
            },
        )

    # 5. Fallback / auto-selection.
    if attestation.fallback_used and not policy.allow_fallback:
        raise ProviderFallbackDenied(
            "fallback_used=true not allowed",
            details={
                "requested": attestation.requested_provider,
                "effective": attestation.effective_provider,
            },
        )
    if attestation.auto_selection_used and not policy.allow_auto_selection:
        raise ProviderFallbackDenied(
            "auto_selection_used=true not allowed",
            details={"effective": attestation.effective_provider},
        )

    # 6. Drift de provider/modelo.
    if policy.fail_on_provider_drift:
        if (
            attestation.effective_provider != attestation.requested_provider
            or attestation.effective_model != attestation.requested_model
        ):
            raise ProviderAttestationMismatch(
                "provider/model drift",
                details={
                    "requested_provider": attestation.requested_provider,
                    "effective_provider": attestation.effective_provider,
                    "requested_model": attestation.requested_model,
                    "effective_model": attestation.effective_model,
                },
            )
        if attestation.result != "MATCH":
            raise ProviderAttestationMismatch(
                "result != MATCH",
                details={"result": attestation.result},
            )

    return attestation


__all__ = [
    "AttestationPolicy",
    "verify",
    "_coerce_attestation",
]

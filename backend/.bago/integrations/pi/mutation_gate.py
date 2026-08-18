"""mutation_gate.py — denegador explícito de mutaciones.

Fase 4 (mutaciones) está bloqueada por el PLAN BagoPiBridge v0.1. Este
módulo expone una sola función: `deny()`. Si en el futuro Fase 4 se
desbloquea, debe reemplazarse por un módulo nuevo con una versión de
protocolo mayor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import MutationPhaseLocked


@dataclass(frozen=True)
class MutationDenial:
    decision: str = "DENY"
    reason_code: str = "PI_MUTATION_PHASE_LOCKED"
    mutation_receipt: str = "not_issued"
    execution_continuation: str = "cancel"
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "mutation_receipt": self.mutation_receipt,
            "execution_continuation": self.execution_continuation,
            "details": dict(self.details or {}),
        }


def deny(details: dict[str, Any] | None = None) -> MutationDenial:
    """Devuelve la denegación canónica y registra la regla.

    Este módulo no debe modificarse para "abrir un poco" mutaciones: la
    política vigente es fail-closed.
    """
    return MutationDenial(details=details or {})


def raise_if_mutated(operation: str, payload: dict[str, Any] | None = None) -> None:
    """Helper que lanza `MutationPhaseLocked` si la operación es de
    mutación. Útil como decorador/guardia explícita."""
    write_keys = {"write", "edit", "create", "delete", "rename", "patch", "atomic_patch"}
    if any(op in operation.lower() for op in write_keys):
        raise MutationPhaseLocked(
            "mutation blocked",
            details={"operation": operation, "payload_keys": list((payload or {}).keys())},
        )


__all__ = ["MutationDenial", "deny", "raise_if_mutated"]

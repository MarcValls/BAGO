"""Operational-intent value object.

This is an additive bridge between a user utterance and BAGO's existing
intent, plan, execution, and evidence layers. It is deliberately descriptive:
it does not authorize execution or replace the canonical router.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


VALID_LIFECYCLE_STATES = (
    "PROPOSED",
    "PREPARED",
    "EXECUTED",
    "VERIFIED",
    "VALIDATED",
    "BLOCKED",
    "FAILED",
)


def _clean_items(values: Iterable[Any] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(
        item.strip()
        for item in (str(value) for value in values)
        if item.strip()
    )


@dataclass(frozen=True)
class OperationalIntent:
    """Structured description of why, what, and how a request is handled."""

    source: str
    intent: str
    operation: str
    product: str = ""
    context: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    acceptance: tuple[str, ...] = field(default_factory=tuple)
    lifecycle_state: str = "PROPOSED"

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source is required")
        if not self.intent.strip():
            raise ValueError("intent is required")
        if not self.operation.strip():
            raise ValueError("operation is required")
        if self.lifecycle_state not in VALID_LIFECYCLE_STATES:
            raise ValueError(f"invalid lifecycle state: {self.lifecycle_state}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationalIntent":
        return cls(
            source=str(data.get("source") or ""),
            intent=str(data.get("intent") or ""),
            operation=str(data.get("operation") or ""),
            product=str(data.get("product") or ""),
            context=_clean_items(data.get("context")),
            constraints=_clean_items(data.get("constraints")),
            acceptance=_clean_items(data.get("acceptance")),
            lifecycle_state=str(data.get("lifecycle_state") or "PROPOSED").upper(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "intent": self.intent,
            "operation": self.operation,
            "product": self.product,
            "context": list(self.context),
            "constraints": list(self.constraints),
            "acceptance": list(self.acceptance),
            "lifecycle_state": self.lifecycle_state,
        }


def derive_operational_intent(
    source: str,
    *,
    interpreted_intent: str,
    operation: str = "",
    product: str = "",
    context: Iterable[str] | None = None,
    constraints: Iterable[str] | None = None,
    acceptance: Iterable[str] | None = None,
) -> OperationalIntent:
    """Derive a conservative operational description from an existing intent."""
    intent = interpreted_intent.strip() or "general"
    defaults = {
        "chat": ("conversar", "respuesta conversacional"),
        "review": ("revisar", "hallazgos y evidencia de revisión"),
        "execute": ("ejecutar", "resultado de ejecución"),
        "work": ("transformar", "cambio materializado"),
        "create_resource": ("crear", "recurso creado"),
        "delete_resource": ("eliminar", "estado actualizado"),
        "update_resource": ("actualizar", "recurso actualizado"),
        "query_resource": ("consultar", "resultado de consulta"),
        "explanation": ("explicar", "explicación"),
        "execution": ("ejecutar", "resultado de ejecución"),
        "general": ("interpretar", "resultado de interpretación"),
    }
    default_operation, default_product = defaults.get(intent, defaults["general"])
    return OperationalIntent(
        source=source,
        intent=intent,
        operation=operation.strip() or default_operation,
        product=product.strip() or default_product,
        context=_clean_items(context),
        constraints=_clean_items(constraints),
        acceptance=_clean_items(acceptance),
    )

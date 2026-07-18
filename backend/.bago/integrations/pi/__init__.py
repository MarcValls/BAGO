"""BagoPiBridge — paquete en cuarentena (Sprint 1 / Fase 0).

El bridge existe únicamente como superficie subordinada al backend BAGO.
PI no se importa, no se ejecuta ni se descubre como dependencia en esta
fase. Toda capacidad no declarada, toda discrepancia de identidad, todo
contexto incompleto y todo intento de acceder a estado PI autónomo
provocan rechazo (fail-closed).

Reglas de Fase 0:
    - No se importa PI ni su SDK.
    - No se carga ningún módulo de `integrations.pi.*` por reflexión
      automática.
    - No se modifica estado de sesión, workspace ni de provider.
    - Toda capacidad debe estar declarada explícitamente en
      `CapabilityClaims`; la lista vacía es el default.
"""
from __future__ import annotations

__all__: list[str] = [
    "BRIDGE_PROTOCOL_VERSION",
    "QUARANTINE_PHASE",
    "is_quarantined",
]

BRIDGE_PROTOCOL_VERSION: str = "0.1.0"
QUARANTINE_PHASE: int = 0
PI_STATUS: str = "DRAFT"


def is_quarantined() -> bool:
    """Devuelve `True` mientras el bridge esté en cuarentena."""
    return PI_STATUS == "DRAFT"

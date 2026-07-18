"""policy_gate.py — matriz de capacidades del BagoPiBridge.

Decide qué está permitido por fase, con fail-closed: cualquier
capacidad no declarada o no soportada por la fase actual se deniega.

Fases:
    0  Contención: nada de inferencia, nada de filesystem, nada de
       proceso, nada de network.
    1  Provider adapter: inferencia sin tools, sin skills, sin
       extensiones.
    2  Tool proxy de solo lectura: read/ls/grep/find dentro de scope.
    3  Agent runner con captura completa.
    4  Bloqueada (mutaciones).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ALLOWED_TOOLS, CapabilityClaims
from .errors import (
    CapabilityDenied,
    MutationPhaseLocked,
    ProcessCapabilityDenied,
    ToolNotAllowed,
)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, **self.details}


def _deny(code: str, **details: Any) -> PolicyDecision:
    return PolicyDecision(False, code, {"reason_code": code, **details})


def _allow(code: str, **details: Any) -> PolicyDecision:
    return PolicyDecision(True, code, {"reason_code": code, **details})


def check_phase(phase: int, max_phase: int) -> PolicyDecision:
    if phase < 0 or phase > 3:
        return _deny("PI_INVALID_PHASE", phase=phase)
    if phase > max_phase:
        return _deny("PI_PHASE_LOCKED", phase=phase, max_phase=max_phase)
    return _allow("PI_PHASE_OK", phase=phase, max_phase=max_phase)


def check_claims(
    claims: CapabilityClaims, *, phase: int, max_phase: int
) -> PolicyDecision:
    """Evalúa la coherencia de `CapabilityClaims` con la fase actual."""
    phase_check = check_phase(phase, max_phase)
    if not phase_check.allowed:
        return phase_check

    # Fases 0-3: filesystem.write siempre denegado.
    if claims.filesystem_write:
        return _deny("PI_MUTATION_PHASE_LOCKED", field="filesystem_write")

    # process.spawn: bloqueado en Fase 0.
    if claims.process_spawn and phase < 2:
        return _deny(
            "PROCESS_CAPABILITY_DENIED", field="process_spawn", phase=phase
        )

    # network.mode: sólo provider_endpoints_only o none.
    if claims.network_mode not in {"none", "provider_endpoints_only"}:
        return _deny(
            "PI_NETWORK_MODE_DENIED", value=claims.network_mode
        )
    if claims.network_mode == "provider_endpoints_only" and phase == 0:
        return _deny("PI_NETWORK_MODE_DENIED", value=claims.network_mode, phase=phase)

    # Tools: sólo las 4 allowlisted y sólo a partir de Fase 2.
    if claims.tools_allowed and phase < 2:
        return _deny(
            "TOOL_NOT_ALLOWED",
            tools=list(claims.tools_allowed),
            reason="tools require phase>=2",
        )
    for tool in claims.tools_allowed:
        if tool not in ALLOWED_TOOLS:
            return _deny("TOOL_NOT_ALLOWED", tool=tool)

    # Skills, extensions, packages: prohibidos en Fases 0-3.
    if claims.skills_imported_ids:
        return _deny(
            "PI_AUTOLOAD_SOURCE_DETECTED", field="skills_imported_ids"
        )
    if claims.extensions_allowed:
        return _deny("PI_EXTENSION_DENIED", field="extensions_allowed")
    if claims.packages_allowed:
        return _deny("PI_EXTENSION_DENIED", field="packages_allowed")

    # Completion authority debe ser BAGO.
    if claims.completion_authority != "bago_validator":
        return _deny(
            "PI_COMPLETION_AUTHORITY_DENIED",
            value=claims.completion_authority,
        )

    return _allow("PI_CLAIMS_OK", phase=phase, max_phase=max_phase)


def decide_tool(claims: CapabilityClaims, tool: str) -> PolicyDecision:
    """Decide si una tool concreta es invocable en esta fase."""
    if tool not in ALLOWED_TOOLS:
        return _deny("TOOL_NOT_ALLOWED", tool=tool)
    if tool not in claims.tools_allowed:
        return _deny("TOOL_NOT_ALLOWED", tool=tool, reason="not in claim")
    if not claims.filesystem_read:
        return _deny("PI_CAPABILITY_DENIED", reason="filesystem_read disabled")
    if not claims.filesystem_read_root:
        return _deny("PI_CAPABILITY_DENIED", reason="read root missing")
    return _allow("PI_TOOL_OK", tool=tool)


def deny_mutation(reason: str = "phase<4 blocks mutations") -> PolicyDecision:
    """Decisión explícita: cualquier mutación es DENEGADA en Fases 0-3."""
    return _deny("PI_MUTATION_PHASE_LOCKED", reason=reason)


def require_no_process(claims: CapabilityClaims) -> PolicyDecision:
    if claims.process_spawn:
        return _deny("PROCESS_CAPABILITY_DENIED", field="process_spawn")
    return _allow("PI_PROCESS_OK")


__all__ = [
    "PolicyDecision",
    "check_phase",
    "check_claims",
    "decide_tool",
    "deny_mutation",
    "require_no_process",
]

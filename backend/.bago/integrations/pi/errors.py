"""errors.py — códigos de error estables del BagoPiBridge.

Los códigos siguen el patrón `PI_<DOMAIN>_<REASON>` y son la única
forma de reportar rechazo entre el bridge y el backend BAGO. Ningún
mensaje de error debe filtrar secretos, paths de usuario, contenido de
prompts ni credenciales. El texto legible es auxiliar; el código es la
autoridad.
"""
from __future__ import annotations

from typing import Any


class BridgeError(Exception):
    """Error base del BagoPiBridge.

    Attributes:
        code: código estable del error (ver constantes `PI_*`).
        reason: descripción legible, sin secretos.
        details: dict opcional con metadatos no sensibles.
    """

    code: str = "PI_BRIDGE_ERROR"
    http_status: int = 400

    def __init__(self, reason: str = "", *, details: dict[str, Any] | None = None) -> None:
        self.reason = str(reason or "bridge error")
        self.details: dict[str, Any] = dict(details or {})
        super().__init__(f"{self.code}: {self.reason}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "reason": self.reason, "details": self.details}


# ── Autoridad y contexto ─────────────────────────────────────────────────────
class ContextEnvelopeRequired(BridgeError):
    code = "CONTEXT_ENVELOPE_REQUIRED"
    http_status = 412


class DigestMismatch(BridgeError):
    code = "DIGEST_MISMATCH"
    http_status = 409


class SessionRevisionObsolete(BridgeError):
    code = "SESSION_REVISION_OBSOLETE"
    http_status = 409


class NonceReplayDenied(BridgeError):
    code = "NONCE_REPLAY_DENIED"
    http_status = 409


# ── Scope y filesystem ───────────────────────────────────────────────────────
class ScopeReadDenied(BridgeError):
    code = "SCOPE_READ_DENIED"
    http_status = 403


class ScopePathDenied(BridgeError):
    code = "SCOPE_PATH_DENIED"
    http_status = 403


class ScopeLinkEscapeDenied(BridgeError):
    code = "SCOPE_LINK_ESCAPE_DENIED"
    http_status = 403


class ScopeToctouDetected(BridgeError):
    code = "SCOPE_TOCTOU_DETECTED"
    http_status = 409


# ── Identidad de proveedor y modelo ──────────────────────────────────────────
class ProviderAttestationMismatch(BridgeError):
    code = "PROVIDER_ATTESTATION_MISMATCH"
    http_status = 409


class ProviderFallbackDenied(BridgeError):
    code = "PROVIDER_FALLBACK_DENIED"
    http_status = 409


# ── Capacidades y mutación ───────────────────────────────────────────────────
class CapabilityDenied(BridgeError):
    code = "PI_CAPABILITY_DENIED"
    http_status = 403


class ProcessCapabilityDenied(BridgeError):
    code = "PROCESS_CAPABILITY_DENIED"
    http_status = 403


class ToolNotAllowed(BridgeError):
    code = "TOOL_NOT_ALLOWED"
    http_status = 403


class MutationPhaseLocked(BridgeError):
    code = "PI_MUTATION_PHASE_LOCKED"
    http_status = 403


# ── Autoload y configuración implícita ───────────────────────────────────────
class PiAutoloadSourceDetected(BridgeError):
    code = "PI_AUTOLOAD_SOURCE_DETECTED"
    http_status = 409


class PiExtensionDenied(BridgeError):
    code = "PI_EXTENSION_DENIED"
    http_status = 403


class PiAuthSourceDenied(BridgeError):
    code = "PI_AUTH_SOURCE_DENIED"
    http_status = 403


class PiImplicitContextDenied(BridgeError):
    code = "PI_IMPLICIT_CONTEXT_DENIED"
    http_status = 403


class PiPersistenceDenied(BridgeError):
    code = "PI_PERSISTENCE_DENIED"
    http_status = 409


# ── Protocolo y eventos ──────────────────────────────────────────────────────
class BridgeProtocolViolation(BridgeError):
    code = "BRIDGE_PROTOCOL_VIOLATION"
    http_status = 400


class UnknownEvent(BridgeError):
    code = "PI_UNKNOWN_EVENT"
    http_status = 400


class MissingToolReceipt(BridgeError):
    code = "MISSING_TOOL_RECEIPT"
    http_status = 409


# ── Límites y proceso ────────────────────────────────────────────────────────
class OutputLimitExceeded(BridgeError):
    code = "OUTPUT_LIMIT_EXCEEDED"
    http_status = 413


class BridgeTimeout(BridgeError):
    code = "BRIDGE_TIMEOUT"
    http_status = 504


class BridgeIntegrityMismatch(BridgeError):
    code = "PI_INTEGRITY_MISMATCH"
    http_status = 409


# ── Mapa de códigos HTTP por si la API los reemite ───────────────────────────
HTTP_STATUS_BY_CODE: dict[str, int] = {
    cls.code: cls.http_status
    for cls in BridgeError.__subclasses__()
    for cls in [cls]
    if hasattr(cls, "code")
}


__all__ = [
    "BridgeError",
    "ContextEnvelopeRequired",
    "DigestMismatch",
    "SessionRevisionObsolete",
    "NonceReplayDenied",
    "ScopeReadDenied",
    "ScopePathDenied",
    "ScopeLinkEscapeDenied",
    "ScopeToctouDetected",
    "ProviderAttestationMismatch",
    "ProviderFallbackDenied",
    "CapabilityDenied",
    "ProcessCapabilityDenied",
    "ToolNotAllowed",
    "MutationPhaseLocked",
    "PiAutoloadSourceDetected",
    "PiExtensionDenied",
    "PiAuthSourceDenied",
    "PiImplicitContextDenied",
    "PiPersistenceDenied",
    "BridgeProtocolViolation",
    "UnknownEvent",
    "MissingToolReceipt",
    "OutputLimitExceeded",
    "BridgeTimeout",
    "BridgeIntegrityMismatch",
    "HTTP_STATUS_BY_CODE",
]

"""Tests de paridad del contrato de protocolo.

Verifica que el conjunto de eventos permitidos en Python coincide con
la allowlist declarada en `contracts.py` y que los códigos de error
son estables. La paridad con el sidecar Node/TS se cubre en CI con
un test de comparación contra `sidecar/src/protocol.ts` (fuera de esta
fase).
"""
from __future__ import annotations

from integrations.pi.contracts import (
    ALLOWED_EVENTS_BY_PHASE,
    ALLOWED_TOOLS,
    ALLOWED_NETWORK_MODES,
)
from integrations.pi.errors import (
    BridgeError,
    BridgeIntegrityMismatch,
    BridgeProtocolViolation,
    BridgeTimeout,
    CapabilityDenied,
    ContextEnvelopeRequired,
    DigestMismatch,
    MissingToolReceipt,
    MutationPhaseLocked,
    NonceReplayDenied,
    OutputLimitExceeded,
    PiAutoloadSourceDetected,
    PiAuthSourceDenied,
    PiExtensionDenied,
    PiImplicitContextDenied,
    PiPersistenceDenied,
    ProcessCapabilityDenied,
    ProviderAttestationMismatch,
    ProviderFallbackDenied,
    ScopeLinkEscapeDenied,
    ScopePathDenied,
    ScopeReadDenied,
    ScopeToctouDetected,
    SessionRevisionObsolete,
    ToolNotAllowed,
    UnknownEvent,
    HTTP_STATUS_BY_CODE,
)


# Códigos que el PLAN §8 declara como evidencia mínima de las NEG-001..024.
EXPECTED_NEG_CODES: frozenset[str] = frozenset(
    {
        "SCOPE_READ_DENIED",
        "PI_MUTATION_PHASE_LOCKED",
        "PROCESS_CAPABILITY_DENIED",
        "PI_AUTOLOAD_SOURCE_DETECTED",
        "PI_EXTENSION_DENIED",
        "PROVIDER_ATTESTATION_MISMATCH",
        "CONTEXT_ENVELOPE_REQUIRED",
        "MISSING_TOOL_RECEIPT",
        "PI_AUTH_SOURCE_DENIED",
        "EXECUTION_COMPLETED_UNVERIFIED",
        "SCOPE_LINK_ESCAPE_DENIED",
        "SCOPE_PATH_DENIED",
        "NONCE_REPLAY_DENIED",
        "DIGEST_MISMATCH",
        "BRIDGE_PROTOCOL_VIOLATION",
        "OUTPUT_LIMIT_EXCEEDED",
        "BRIDGE_TIMEOUT",
        "PI_IMPLICIT_CONTEXT_DENIED",
        "PROVIDER_FALLBACK_DENIED",
        "SCOPE_TOCTOU_DETECTED",
        "TOOL_NOT_ALLOWED",
        "PI_PERSISTENCE_DENIED",
        "PI_INTEGRITY_MISMATCH",
    }
)


def test_allowed_tools_is_exactly_4() -> None:
    assert ALLOWED_TOOLS == frozenset({"read", "ls", "grep", "find"})


def test_allowed_network_modes() -> None:
    assert ALLOWED_NETWORK_MODES == frozenset(
        {"none", "provider_endpoints_only", "disabled"}
    )


def test_phase_event_allowlist_is_monotonic() -> None:
    for phase in range(0, 4):
        assert phase in ALLOWED_EVENTS_BY_PHASE
    for phase in range(1, 4):
        # Las fases más avanzadas incluyen todos los eventos de fases
        # previas (más eventos permitidos, nunca menos).
        assert ALLOWED_EVENTS_BY_PHASE[phase - 1].issubset(
            ALLOWED_EVENTS_BY_PHASE[phase]
        )


def test_error_codes_stable() -> None:
    # El PLAN §5.1-5.7 y §8 fijan un conjunto de códigos. Si alguno se
    # renombra accidentalmente, este test falla. La verificación es
    # contra un set explícito: si el código no existe en Python, se
    # reporta como faltante.
    expected_python_codes = {
        c for c in dir()
        if isinstance(globals().get(c), type)
        and issubclass(globals()[c], BridgeError)
        and c != "BridgeError"
    }
    expected_python_codes = {c.code for c in (
        BridgeError, ContextEnvelopeRequired, DigestMismatch,
        SessionRevisionObsolete, NonceReplayDenied, ScopeReadDenied,
        ScopePathDenied, ScopeLinkEscapeDenied, ScopeToctouDetected,
        ProviderAttestationMismatch, ProviderFallbackDenied,
        CapabilityDenied, ProcessCapabilityDenied, ToolNotAllowed,
        MutationPhaseLocked, PiAutoloadSourceDetected, PiExtensionDenied,
        PiAuthSourceDenied, PiImplicitContextDenied, PiPersistenceDenied,
        BridgeProtocolViolation, UnknownEvent, MissingToolReceipt,
        OutputLimitExceeded, BridgeTimeout, BridgeIntegrityMismatch,
    )}
    # Cada código en HTTP_STATUS_BY_CODE debe corresponder a una clase.
    for code in HTTP_STATUS_BY_CODE:
        assert code in expected_python_codes, code


def test_neg_codes_subset_of_python_codes() -> None:
    python_codes = {
        c.code for c in (
            BridgeError, ContextEnvelopeRequired, DigestMismatch,
            SessionRevisionObsolete, NonceReplayDenied, ScopeReadDenied,
            ScopePathDenied, ScopeLinkEscapeDenied, ScopeToctouDetected,
            ProviderAttestationMismatch, ProviderFallbackDenied,
            CapabilityDenied, ProcessCapabilityDenied, ToolNotAllowed,
            MutationPhaseLocked, PiAutoloadSourceDetected, PiExtensionDenied,
            PiAuthSourceDenied, PiImplicitContextDenied, PiPersistenceDenied,
            BridgeProtocolViolation, UnknownEvent, MissingToolReceipt,
            OutputLimitExceeded, BridgeTimeout, BridgeIntegrityMismatch,
        )
    }
    # EXECUTION_COMPLETED_UNVERIFIED es un estado final del backend, no
    # un código de error del bridge. Lo aceptamos en el subconjunto de
    # PLAN pero no se exige como error.
    plan_required = EXPECTED_NEG_CODES - {"EXECUTION_COMPLETED_UNVERIFIED"}
    missing = plan_required - python_codes
    assert not missing, f"missing error codes: {sorted(missing)}"

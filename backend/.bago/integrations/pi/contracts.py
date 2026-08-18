"""contracts.py — modelos validados del protocolo BagoPiBridge.

Estos dataclasses son la superficie de intercambio entre el backend
BAGO y el sidecar. El bridge no acepta campos extra en
`BridgeExecutionRequest`; cualquier campo nuevo debe pasar por revisión
CRIT y por una nueva versión de protocolo.

El módulo **no** crea una segunda clase de `ContextReceipt` ni de
`ToolReceipt` cross-cutting: emite un `ToolReceipt` local del bridge
(para Fases 2-3) y reutiliza el `ContextReceipt` canónico del backend
BAGO cuando se necesite.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from . import BRIDGE_PROTOCOL_VERSION
from .errors import BridgeError, ContextEnvelopeRequired


# ── Constantes de allowlist ──────────────────────────────────────────────────

ALLOWED_TOOLS: frozenset[str] = frozenset({"read", "ls", "grep", "find"})
ALLOWED_EVENTS_F0: frozenset[str] = frozenset(
    {
        "runtime_attested",
        "provider_attested",
        "model_output_delta",
        "usage_reported",
        "pi_finished",
    }
)
ALLOWED_EVENTS_F1: frozenset[str] = ALLOWED_EVENTS_F0
ALLOWED_EVENTS_F2: frozenset[str] = ALLOWED_EVENTS_F0 | {
    "tool_requested",
    "tool_policy_decided",
    "tool_result_attached",
}
ALLOWED_EVENTS_F3: frozenset[str] = ALLOWED_EVENTS_F2 | {
    "agent_step_started",
    "agent_step_finished",
}
ALLOWED_EVENTS_BY_PHASE: dict[int, frozenset[str]] = {
    0: ALLOWED_EVENTS_F0,
    1: ALLOWED_EVENTS_F1,
    2: ALLOWED_EVENTS_F2,
    3: ALLOWED_EVENTS_F3,
}

ALLOWED_NETWORK_MODES: frozenset[str] = frozenset(
    {"none", "provider_endpoints_only", "disabled"}
)

# v0.3 (D2) — vocabulario controlado para adapter y runtime del bridge.
# `provider` NUNCA aparece aquí; los providers viven en backend/.bago/core.
ALLOWED_ADAPTERS: frozenset[str] = frozenset({"pi-ai", "bago-native", "litellm"})
ALLOWED_RUNTIMES: frozenset[str] = frozenset({"node-sidecar", "python-inproc", "wasm"})
# Backwards-compat alias internos (los importaban tests antes de v0.3).
_ALLOWED_ADAPTERS: frozenset[str] = ALLOWED_ADAPTERS
_ALLOWED_RUNTIMES: frozenset[str] = ALLOWED_RUNTIMES


# ── Utilidades ───────────────────────────────────────────────────────────────

_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")


def _is_id(value: str) -> bool:
    return isinstance(value, str) and bool(_ID_PATTERN.match(value))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise BridgeError(
            f"{field_name} must be bool",
            details={"value": type(value).__name__},
        )
    return value


# ── CapabilityClaims ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CapabilityClaims:
    """Capacidades explícitas solicitadas. Lista vacía = nada permitido."""

    filesystem_read: bool = False
    filesystem_read_root: str = ""
    filesystem_write: bool = False
    process_spawn: bool = False
    network_mode: str = "none"
    tools_allowed: tuple[str, ...] = ()
    skills_imported_ids: tuple[str, ...] = ()
    extensions_allowed: tuple[str, ...] = ()
    packages_allowed: tuple[str, ...] = ()
    auth_source: str = "bago_secret_broker"
    session_authority: str = "bago"
    provider_selection_authority: str = "bago"
    completion_authority: str = "bago_validator"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityClaims":
        if not isinstance(data, dict):
            raise BridgeError("capability_claims must be an object")
        unknown = sorted(
            key
            for key in data
            if key
            not in {
                "filesystem_read",
                "filesystem_read_root",
                "filesystem_write",
                "process_spawn",
                "network_mode",
                "tools_allowed",
                "skills_imported_ids",
                "extensions_allowed",
                "packages_allowed",
                "auth_source",
                "session_authority",
                "provider_selection_authority",
                "completion_authority",
            }
        )
        if unknown:
            raise BridgeError(
                "capability_claims has unknown keys",
                details={"keys": unknown},
            )

        tools = tuple(data.get("tools_allowed") or ())
        if any(t not in ALLOWED_TOOLS for t in tools):
            raise BridgeError(
                "tools_allowed contains non-allowlisted tool",
                details={"tools": list(tools)},
            )
        network_mode = str(data.get("network_mode") or "none")
        if network_mode not in ALLOWED_NETWORK_MODES:
            raise BridgeError(
                "network_mode not allowed",
                details={"value": network_mode},
            )
        fs_read = _as_bool(data.get("filesystem_read", False), field_name="filesystem_read")
        fs_read_root = str(data.get("filesystem_read_root") or "")
        if fs_read and not fs_read_root:
            raise BridgeError(
                "filesystem_read requires filesystem_read_root",
            )
        if fs_read_root and not fs_read:
            raise BridgeError(
                "filesystem_read_root requires filesystem_read",
            )

        return cls(
            filesystem_read=fs_read,
            filesystem_read_root=fs_read_root,
            filesystem_write=_as_bool(
                data.get("filesystem_write", False), field_name="filesystem_write"
            ),
            process_spawn=_as_bool(
                data.get("process_spawn", False), field_name="process_spawn"
            ),
            network_mode=network_mode,
            tools_allowed=tools,
            skills_imported_ids=tuple(data.get("skills_imported_ids") or ()),
            extensions_allowed=tuple(data.get("extensions_allowed") or ()),
            packages_allowed=tuple(data.get("packages_allowed") or ()),
            auth_source=str(data.get("auth_source") or "bago_secret_broker"),
            session_authority=str(data.get("session_authority") or "bago"),
            provider_selection_authority=str(
                data.get("provider_selection_authority") or "bago"
            ),
            completion_authority=str(data.get("completion_authority") or "bago_validator"),
        )


# ── BridgeExecutionRequest ───────────────────────────────────────────────────


@dataclass(frozen=True)
class BridgeExecutionRequest:
    """Petición BAGO → sidecar.

    No se admiten campos extra. Esto se valida en `from_dict`.
    """

    protocol_version: str
    bridge_request_id: str
    execution_id: str
    correlation_id: str
    request_nonce: str
    issued_at: str
    deadline: str
    session_id: str
    session_revision: str
    workspace_id: str
    project_root: str
    workspace_root: str
    workspace_scope_root: str
    context_envelope_id: str
    context_envelope_digest: str
    policy_profile: str
    policy_digest: str
    capability_claims: CapabilityClaims
    requested_provider: str
    requested_model: str
    credential_ref: str
    input: dict[str, Any]
    output_limits: dict[str, int]
    # v0.3 — cuádruplo provider/adapter/runtime/model (D2 del CRIT).
    # Defaults para backward compat con v0.1/v0.2; el schema JSON los declara required.
    requested_adapter: str = "pi-ai"
    requested_runtime: str = "node-sidecar"

    def __post_init__(self) -> None:
        # Invariante canon: provider NUNCA es "pi" (PI es adapter, no provider).
        if self.requested_provider == "pi":
            raise BridgeError(
                "requested_provider must not be 'pi'; PI is an adapter, not a provider",
                details={"requested_provider": self.requested_provider},
            )
        # Adapter y runtime deben estar en sus vocabularios controlados.
        if self.requested_adapter not in ALLOWED_ADAPTERS:
            raise BridgeError(
                "requested_adapter not in allowed set",
                details={"requested_adapter": self.requested_adapter, "allowed": sorted(ALLOWED_ADAPTERS)},
            )
        if self.requested_runtime not in ALLOWED_RUNTIMES:
            raise BridgeError(
                "requested_runtime not in allowed set",
                details={"requested_runtime": self.requested_runtime, "allowed": sorted(ALLOWED_RUNTIMES)},
            )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capability_claims"] = self.capability_claims.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BridgeExecutionRequest":
        if not isinstance(data, dict):
            raise BridgeError("request must be an object")

        required = {
            "protocol_version",
            "bridge_request_id",
            "execution_id",
            "correlation_id",
            "request_nonce",
            "issued_at",
            "deadline",
            "session_id",
            "session_revision",
            "workspace_id",
            "project_root",
            "workspace_root",
            "workspace_scope_root",
            "context_envelope_id",
            "context_envelope_digest",
            "policy_profile",
            "policy_digest",
            "capability_claims",
            "requested_provider",
            "requested_model",
            "credential_ref",
            "input",
            "output_limits",
            # v0.3: requested_adapter y requested_runtime son opcionales
            # (default en el dataclass) para backward compat con código
            # v0.1/v0.2 que no los conoce. Si están presentes, se validan.
        }
        # v0.3: campos opcionales que se aceptan con default.
        optional_v03 = {"requested_adapter", "requested_runtime"}
        unknown = sorted(key for key in data if key not in required and key not in optional_v03)
        if unknown:
            raise BridgeError(
                "request has unknown fields",
                details={"fields": unknown},
            )
        missing = sorted(key for key in required if key not in data)
        if missing:
            raise BridgeError(
                "request missing required fields",
                details={"fields": missing},
            )

        if str(data["protocol_version"]) != BRIDGE_PROTOCOL_VERSION:
            raise BridgeError(
                "protocol_version mismatch",
                details={
                    "expected": BRIDGE_PROTOCOL_VERSION,
                    "received": str(data["protocol_version"]),
                },
            )
        for id_field in (
            "bridge_request_id",
            "execution_id",
            "correlation_id",
            "request_nonce",
            "session_id",
            "session_revision",
            "workspace_id",
            "context_envelope_id",
        ):
            value = str(data[id_field])
            if not value:
                if id_field == "context_envelope_id":
                    raise ContextEnvelopeRequired(
                        "context_envelope_id missing",
                    )
                raise BridgeError(
                    "field has invalid id format",
                    details={"field": id_field},
                )
            if not _is_id(value):
                raise BridgeError(
                    "field has invalid id format",
                    details={"field": id_field},
                )

        issued_at = str(data["issued_at"])
        deadline = str(data["deadline"])
        try:
            datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
            datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BridgeError(
                "issued_at/deadline must be ISO-8601",
                details={"error": str(exc)},
            ) from exc

        output_limits = data["output_limits"]
        if not isinstance(output_limits, dict):
            raise BridgeError("output_limits must be an object")
        for key, value in output_limits.items():
            if not isinstance(value, int) or value < 0:
                raise BridgeError(
                    "output_limits must be non-negative int",
                    details={"field": key},
                )

        input_payload = data["input"]
        if not isinstance(input_payload, dict):
            raise BridgeError("input must be an object")

        claims = CapabilityClaims.from_dict(data["capability_claims"])

        return cls(
            protocol_version=str(data["protocol_version"]),
            bridge_request_id=str(data["bridge_request_id"]),
            execution_id=str(data["execution_id"]),
            correlation_id=str(data["correlation_id"]),
            request_nonce=str(data["request_nonce"]),
            issued_at=issued_at,
            deadline=deadline,
            session_id=str(data["session_id"]),
            session_revision=str(data["session_revision"]),
            workspace_id=str(data["workspace_id"]),
            project_root=str(data["project_root"]),
            workspace_root=str(data["workspace_root"]),
            workspace_scope_root=str(data["workspace_scope_root"]),
            context_envelope_id=str(data["context_envelope_id"]),
            context_envelope_digest=str(data["context_envelope_digest"]),
            policy_profile=str(data["policy_profile"]),
            policy_digest=str(data["policy_digest"]),
            capability_claims=claims,
            requested_provider=str(data["requested_provider"]),
            requested_model=str(data["requested_model"]),
            # v0.3 (D2): opcionales en from_dict para backward compat con sidecars
            # v0.1/v0.2; el schema JSON los declara required para tráfico nuevo.
            requested_adapter=str(data.get("requested_adapter", "pi-ai")),
            requested_runtime=str(data.get("requested_runtime", "node-sidecar")),
            credential_ref=str(data["credential_ref"]),
            input=input_payload,
            output_limits=dict(output_limits),
        )


# ── ProviderAttestation ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderAttestation:
    requested_provider: str
    effective_provider: str
    requested_model: str
    effective_model: str
    endpoint_normalized: str
    adapter: str
    bridge_version: str
    pi_package_version: str
    pi_lockfile_hash: str
    sidecar_artifact_hash: str
    credential_ref: str
    fallback_used: bool
    auto_selection_used: bool
    config_effective: dict[str, Any]
    result: str  # "MATCH" | "MISMATCH" | "UNATTESTABLE"

    def is_match(self) -> bool:
        return self.result == "MATCH"


# ── BridgeEvent ──────────────────────────────────────────────────────────────


@dataclass
class BridgeEvent:
    execution_id: str
    sequence_number: int
    event_id: str
    event_type: str
    timestamp: str
    payload: dict[str, Any]
    previous_event_hash: str
    event_hash: str
    redaction_applied: bool
    source: str = "pi_sidecar"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(
    *,
    execution_id: str,
    sequence_number: int,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    previous_event_hash: str,
    redaction_applied: bool = False,
) -> BridgeEvent:
    timestamp = _now_iso()
    pre_hash = _stable_hash(
        {
            "execution_id": execution_id,
            "sequence_number": sequence_number,
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "payload": payload,
            "previous_event_hash": previous_event_hash,
            "redaction_applied": redaction_applied,
            "source": "pi_sidecar",
        }
    )
    return BridgeEvent(
        execution_id=execution_id,
        sequence_number=sequence_number,
        event_id=event_id,
        event_type=event_type,
        timestamp=timestamp,
        payload=dict(payload),
        previous_event_hash=previous_event_hash,
        event_hash=pre_hash,
        redaction_applied=redaction_applied,
    )


# ── ToolReceipt (canónico desde Sprint 4 / Fase 2) ─────────────────────
# El dataclass local se sustituye por el tipo canónico de
# `backend/.bago/core/tool_receipt.py::ToolReceipt`. El bridge lo
# importa lazy para no introducir dependencia dura en tiempo de
# carga. Si Fase 0/1 lo importaba desde aquí, sigue funcionando:
# `contracts.ToolReceipt` es el mismo objeto que `core.tool_receipt.ToolReceipt`.

_TOOL_RECEIPT_CACHE: dict[str, type] = {}


def _canonical_tool_receipt() -> type:
    if "ToolReceipt" in _TOOL_RECEIPT_CACHE:
        return _TOOL_RECEIPT_CACHE["ToolReceipt"]
    import importlib.util as _ilu
    import sys as _sys
    from pathlib import Path as _P

    here = _P(__file__).resolve().parent
    path = here.parent.parent / "core" / "tool_receipt.py"
    if not path.exists():
        # fallback: en test con CWD alterado
        path = _P.cwd() / ".bago" / "core" / "tool_receipt.py"
    if not path.exists():
        path = _P.cwd() / "backend" / ".bago" / "core" / "tool_receipt.py"
    spec = _ilu.spec_from_file_location(
        "_bago_canonical_tool_receipt", str(path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load canonical ToolReceipt from {path}")
    mod = _ilu.module_from_spec(spec)
    _sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _TOOL_RECEIPT_CACHE["ToolReceipt"] = mod.ToolReceipt
    return mod.ToolReceipt


ToolReceipt = _canonical_tool_receipt()  # type: ignore[misc]


__all__ = [
    "ALLOWED_TOOLS",
    "ALLOWED_EVENTS_BY_PHASE",
    "ALLOWED_EVENTS_F0",
    "ALLOWED_NETWORK_MODES",
    "CapabilityClaims",
    "BridgeExecutionRequest",
    "ProviderAttestation",
    "BridgeEvent",
    "ToolReceipt",
    "make_event",
    "_now_iso",
    "_stable_hash",
]

"""receipt_factory.py — emite `ContextReceipt` canónico y `ToolReceipt` local.

El bridge **no** crea una segunda clase de `ContextReceipt`. Reutiliza
`backend/.bago/core/context_envelope.py::ContextReceipt` y le añade
metadatos específicos de PI como parte de `metadata` y `warnings`.

El `ToolReceipt` del bridge vive en `contracts.py` y se construye
desde los eventos `tool_requested` / `tool_policy_decided` /
`tool_result_attached`. En Fase 1 no se emiten tool events; este
módulo expone el constructor para uso futuro y un sumidero de
`tool_receipts` para que `ContextReceipt.to_dict()` los pueda incluir
en la lista `tools_executed`.

Estado final garantizado: como máximo `EXECUTION_COMPLETED_UNVERIFIED`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .attestation import AttestationPolicy
from .contracts import (
    BridgeEvent,
    BridgeExecutionRequest,
    ProviderAttestation,
    ToolReceipt,
    _now_iso,
)
from .event_capture import EventLog


# Reutilizamos el ContextReceipt canónico sin modificar su dataclass.
# El import se hace en runtime para evitar acoplamiento en tiempo de
# carga de los tests de Fase 0.
def _resolve_canonical_path() -> Path:
    from pathlib import Path

    here = Path(__file__).resolve().parent
    # El bridge vive en `backend/.bago/integrations/pi/`. El envelope
    # canónico vive en `backend/.bago/core/context_envelope.py`.
    candidates = [
        here.parent.parent / "core" / "context_envelope.py",
        Path.cwd() / ".bago" / "core" / "context_envelope.py",
        Path.cwd() / "backend" / ".bago" / "core" / "context_envelope.py",
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            continue
    raise FileNotFoundError("canonical context_envelope.py not found")


def _import_canonical_receipt() -> type:
    import importlib.util
    import sys

    path = _resolve_canonical_path()
    spec = importlib.util.spec_from_file_location(
        "_bago_context_envelope_canonical", str(path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load canonical context_envelope from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.ContextReceipt


@dataclass
class BridgeReceiptBundle:
    """Bundle emitido al cerrar una ejecución del bridge."""

    context_receipt: Any
    tool_receipts: list[ToolReceipt] = field(default_factory=list)
    bridge_metadata: dict[str, Any] = field(default_factory=dict)
    final_status: str = "REJECTED"
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_receipt": self.context_receipt.to_dict()
            if hasattr(self.context_receipt, "to_dict")
            else dict(self.context_receipt),
            "tool_receipts": [r.to_dict() for r in self.tool_receipts],
            "bridge_metadata": dict(self.bridge_metadata),
            "final_status": self.final_status,
            "rejection_reasons": list(self.rejection_reasons),
        }


def _safe_final_status(log: EventLog) -> str:
    return log.final_status()


def _summarise_events(log: EventLog) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    for event in log.iter():
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
    return {
        "total": len(log),
        "by_type": by_type,
        "first_event_hash": log.first_hash(),
        "last_event_hash": log.last_hash(),
    }


def _attestation_summary(att: ProviderAttestation | None) -> dict[str, Any]:
    if att is None:
        return {"present": False}
    return {
        "present": True,
        "result": att.result,
        "effective_provider": att.effective_provider,
        "effective_model": att.effective_model,
        "endpoint_normalized": att.endpoint_normalized,
        "fallback_used": att.fallback_used,
        "auto_selection_used": att.auto_selection_used,
        "bridge_version": att.bridge_version,
        "pi_package_version": att.pi_package_version,
        "pi_lockfile_hash": att.pi_lockfile_hash,
        "sidecar_artifact_hash": att.sidecar_artifact_hash,
    }


def _extract_model_output(events: list[BridgeEvent]) -> str:
    parts: list[str] = []
    for event in events:
        if event.event_type == "model_output_delta":
            delta = event.payload.get("delta")
            if isinstance(delta, str):
                parts.append(delta)
    return "".join(parts)


def _extract_usage(events: list[BridgeEvent]) -> dict[str, int]:
    for event in events:
        if event.event_type == "usage_reported":
            payload = event.payload
            return {
                "input_tokens": int(payload.get("input_tokens", 0) or 0),
                "output_tokens": int(payload.get("output_tokens", 0) or 0),
                "total_tokens": int(payload.get("total_tokens", 0) or 0),
            }
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _latency_ms(events: list[BridgeEvent]) -> float:
    if len(events) < 2:
        return 0.0
    try:
        start = datetime.fromisoformat(events[0].timestamp.replace("Z", "+00:00"))
        end = datetime.fromisoformat(events[-1].timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max(0.0, (end - start).total_seconds() * 1000.0)


def build_receipt(
    request: BridgeExecutionRequest,
    log: EventLog,
    *,
    attestation: ProviderAttestation | None,
    attestation_policy: AttestationPolicy,
    tool_receipts: list[ToolReceipt] | None = None,
    rejection_reasons: list[str] | None = None,
) -> BridgeReceiptBundle:
    """Construye el bundle de receipts a partir del log de eventos.

    Reutiliza el `ContextReceipt` canónico de BAGO. Le pasa el
    `envelope` que el bridge construyó a partir del request; los
    campos PI-specific viven en `metadata`.
    """
    ContextReceipt = _import_canonical_receipt()

    # Construimos un ContextEnvelope mínimo para satisfacer la API
    # `ContextReceipt.from_response`. Reutilizamos los campos del
    # request del bridge; el envelope canónico exige system_prompt y
    # messages, así que los derivamos del `input`.
    system_prompt = ""
    messages: list[dict[str, Any]] = []
    if isinstance(request.input, dict):
        if isinstance(request.input.get("system"), str):
            system_prompt = request.input["system"]
        if isinstance(request.input.get("messages"), list):
            messages = list(request.input["messages"])

    try:
        import importlib.util as _ilu
        import sys as _sys

        envelope_path = _resolve_canonical_path()
        spec = _ilu.spec_from_file_location(
            "_bago_context_envelope_for_receipt", str(envelope_path)
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load context_envelope")
        mod = _ilu.module_from_spec(spec)
        _sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        ContextEnvelope = mod.ContextEnvelope
    except Exception as exc:  # pragma: no cover - only on import error
        raise ImportError(
            f"could not import canonical ContextEnvelope: {exc}"
        ) from exc

    envelope = ContextEnvelope(
        system_prompt=system_prompt,
        messages=messages,
        tools=None,
        metadata={
            "bridge_request_id": request.bridge_request_id,
            "policy_profile": request.policy_profile,
            "policy_digest": request.policy_digest,
            "capability_claims": request.capability_claims.to_dict(),
            "context_envelope_id": request.context_envelope_id,
            "context_envelope_digest": request.context_envelope_digest,
        },
        session_id=request.session_id,
        framework_root=request.project_root,
        project_root=request.project_root,
        workspace_id=request.workspace_id,
        workspace_state_root=request.workspace_root,
        workspace_scope_root=request.workspace_scope_root,
        source_of_truth_version="gabo-workspace-v1",
        context_revision=request.session_revision,
        authorized_root=request.workspace_scope_root,
        restrictions=list(
            _restrictions_for_phase(attestation_policy)
        ),
        provider=request.requested_provider,
        adapter=attestation.adapter if attestation else "",
        runtime="bago-pi-bridge",
        model=request.requested_model,
        mode="bridge",
        request_id=request.bridge_request_id,
        workspace=request.workspace_root,
        repository=request.project_root,
        branch="",
        revision="",
    )

    events = log.events()
    usage = _extract_usage(events)
    latency = _latency_ms(events)
    model_used = (
        attestation.effective_model
        if attestation
        else request.requested_model
    )
    response_content = _extract_model_output(events)
    final_status = _safe_final_status(log)
    rejection_reasons = list(rejection_reasons or [])

    if attestation is None:
        final_status = "REJECTED"
        if "missing_attestation" not in rejection_reasons:
            rejection_reasons.append("missing_attestation")

    # ANOTACIÓN A1 (CRIT v0.2):
    # `verification_state` es **propuesta del bridge, no certificación
    # final**. El bridge NUNCA escribe "done" / "verified" /
    # "certified". La promoción a esos estados es **exclusiva del
    # validador BAGO**, que opera fuera de este módulo. El campo
    # viaja como metadato informativo; el validador puede
    # sobrescribirlo o ignorarlo. Esta separación es la base del
    # principio de autoridad: el bridge observa y reporta, el
    # validador decide.
    verification_state = "execution_completed_unverified"
    if final_status == "REJECTED":
        verification_state = "rejected"
    elif final_status == "EXECUTION_COMPLETED_UNVERIFIED":
        verification_state = "execution_completed_unverified"

    # CANON[CTX-003]: receipts must store effective values, not just
    # requested ones. The provider_used and model_used below are the
    # *effective* ones from the attestation (or the requested ones if
    # no attestation was emitted, which results in REJECTED).
    receipt = ContextReceipt.from_response(
        envelope=envelope,
        response_content=response_content,
        model_used=model_used,
        finish_reason="pi_finished" if final_status != "REJECTED" else "rejected",
        usage_input=usage["input_tokens"],
        usage_output=usage["output_tokens"],
        usage_total=usage["total_tokens"],
        latency_ms=latency,
        extra_metadata={
            "bridge": {
                "protocol_version": "0.1.0",
                "phase": 1,
                "final_status": final_status,
                "verification_state": verification_state,
                "rejection_reasons": rejection_reasons,
                "events_summary": _summarise_events(log),
                "attestation": _attestation_summary(attestation),
            },
            "capability_claims": request.capability_claims.to_dict(),
        },
        context_details={
            "request_id": request.bridge_request_id,
            "session_id": request.session_id,
            "framework_root": request.project_root,
            "project_root": request.project_root,
            "workspace_id": request.workspace_id,
            "workspace_state_root": request.workspace_root,
            "workspace_scope_root": request.workspace_scope_root,
            "context_revision": request.session_revision,
            "provider_used": attestation.effective_provider
            if attestation
            else request.requested_provider,
            "adapter_used": attestation.adapter if attestation else "",
            "runtime_used": "bago-pi-bridge",
            "warnings": [
                "PI execution only; BAGO validator must promote state.",
            ]
            + [f"rejection:{r}" for r in rejection_reasons],
            "result": {
                "final_status": final_status,
                "verification_state": verification_state,
            },
            "verification_state": verification_state,
        },
    )

    return BridgeReceiptBundle(
        context_receipt=receipt,
        tool_receipts=list(tool_receipts or []),
        bridge_metadata={
            "first_event_hash": log.first_hash(),
            "last_event_hash": log.last_hash(),
            "attestation": _attestation_summary(attestation),
            "policy": attestation_policy.to_dict(),
        },
        final_status=final_status,
        rejection_reasons=rejection_reasons,
    )


def _restrictions_for_phase(policy: AttestationPolicy) -> list[str]:
    out = [
        "no_mutations_phase_1",
        "no_skills_phase_1",
        "no_extensions_phase_1",
        "no_packages_phase_1",
        "no_native_tools_phase_1",
    ]
    if policy.fail_on_provider_drift:
        out.append("fail_on_provider_drift")
    if policy.fail_on_unknown_event:
        out.append("fail_on_unknown_event")
    return out


__all__ = ["BridgeReceiptBundle", "build_receipt"]

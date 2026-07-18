"""provider_adapter.py — `BagoPiProviderAdapter`.

Implementación del contrato `ProviderAdapter` (canónico) que delega
en el sidecar BagoPiBridge. **Fase 1: sin tools, sin skills, sin
extensiones, sin mutaciones, sin red fuera del mock local**.

Reglas de Fase 1:
    - `chat()` envía el request al sidecar y devuelve un
      `ProviderResponse` con la respuesta consolidada.
    - `list_models()` consulta el catálogo canónico de BAGO
      (provider registry); NUNCA el catálogo del SDK PI.
    - `supports_tools()` siempre devuelve `False` en Fase 1.
    - `supports_streaming()` siempre devuelve `False` en Fase 1.
    - El adapter **no** instancia ni importa el SDK de PI; sólo
      ejecuta el sidecar Node como proceso aislado.

Este adapter está **desactivado por defecto**. Para activarlo:
    1. `BAGO_PI_BRIDGE_ENABLED=true` en env
    2. `BAGO_PI_MAX_PHASE=1` en env o `max_phase: 1` en config
    3. `integrations.pi.enabled: true` en `backend/.bago/config.json`
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .attestation import AttestationPolicy, verify as verify_attestation
from .config import PiBridgeConfig, load_config
from .contracts import (
    BridgeExecutionRequest,
    CapabilityClaims,
    ProviderAttestation,
    _now_iso,
)
from .errors import (
    BridgeError,
    CapabilityDenied,
    MutationPhaseLocked,
    ProcessCapabilityDenied,
    ProviderAttestationMismatch,
    ProviderFallbackDenied,
    ToolNotAllowed,
)
from .event_capture import EventLog
from .preflight import preflight
from .process_boundary import build_boundary, run_sidecar
from .receipt_factory import build_receipt


SIDECAR_RELATIVE_PATH = ("sidecar", "src", "main.js")


def _sidecar_path(integrations_dir: Path) -> Path:
    candidate = integrations_dir.joinpath(*SIDECAR_RELATIVE_PATH)
    if not candidate.exists():
        raise ProcessCapabilityDenied(
            "sidecar not found",
            details={"path": str(candidate)},
        )
    return candidate


def _node_binary() -> str:
    node = shutil.which("node")
    if not node:
        raise ProcessCapabilityDenied("node binary not found in PATH")
    return node


def _build_request(
    *,
    provider: str,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int | None,
    config: PiBridgeConfig,
    envelope_id: str,
    envelope_digest: str,
    session_id: str,
    session_revision: str,
    workspace_id: str,
    project_root: str,
    workspace_root: str,
    workspace_scope_root: str,
    credential_ref: str,
) -> BridgeExecutionRequest:
    now = _now_iso()
    from datetime import datetime, timedelta, timezone

    future = (
        datetime.now(timezone.utc) + timedelta(seconds=60)
    ).isoformat()
    claims = CapabilityClaims(
        filesystem_read=False,
        filesystem_write=False,
        process_spawn=False,
        network_mode="provider_endpoints_only",
        tools_allowed=(),
        skills_imported_ids=(),
        extensions_allowed=(),
        packages_allowed=(),
    )
    return BridgeExecutionRequest(
        protocol_version="0.1.0",
        bridge_request_id=f"br-{envelope_id}",
        execution_id=f"exec-{envelope_id}",
        correlation_id=session_id,
        request_nonce=f"nonce-{envelope_id}",
        issued_at=now,
        deadline=future,
        session_id=session_id,
        session_revision=session_revision,
        workspace_id=workspace_id,
        project_root=project_root,
        workspace_root=workspace_root,
        workspace_scope_root=workspace_scope_root,
        context_envelope_id=envelope_id,
        context_envelope_digest=envelope_digest,
        policy_profile="provider_only",
        policy_digest="phase-1",
        capability_claims=claims,
        requested_provider=provider,
        requested_model=model,
        credential_ref=credential_ref,
        input={"system": system, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        output_limits={
            "max_tokens": int(max_tokens or 0),
            "max_bytes_per_event": 256 * 1024,
            "max_events": 4096,
            "max_seconds": int(config.raw.get("max_phase", 0) and 30 or 30),
        },
    )


def _attestation_policy(config: PiBridgeConfig) -> AttestationPolicy:
    raw = config.raw or {}
    return AttestationPolicy(
        expected_sidecar_hash=str(raw.get("sidecar_artifact_hash") or ""),
        expected_lockfile_hash=str(raw.get("sidecar_lockfile_hash") or ""),
        fail_on_provider_drift=bool(config.fail_on_provider_drift),
        fail_on_unknown_event=bool(config.fail_on_unknown_event),
        allow_fallback=False,
        allow_auto_selection=False,
    )


def _import_provider_adapter_base() -> type:
    """Carga la clase base canónica de BAGO y la registra en
    `sys.modules['provider_adapter']` para que el router BAGO
    (`from provider_adapter import ProviderAdapter`) la encuentre.

    B1 (CRIT v0.2): la resolución de `provider_adapter` resuelve
    en orden de sys.path. Si el bridge importa el canónico bajo el
    nombre `provider_adapter`, el router obtiene la misma clase que
    el bridge, y `isinstance(adapter, ProviderAdapter)` devuelve
    `True`.

    El módulo canónico se carga una sola vez por proceso. Si ya está
    en `sys.modules`, se reutiliza.
    """
    import importlib.util
    import sys
    from pathlib import Path

    existing = sys.modules.get("provider_adapter")
    if existing is not None and hasattr(existing, "ProviderAdapter"):
        return existing.ProviderAdapter  # type: ignore[attr-defined]

    here = Path(__file__).resolve().parent
    candidates = [
        here.parent.parent / "core" / "provider_adapter.py",
        Path.cwd() / ".bago" / "core" / "provider_adapter.py",
        Path.cwd() / "backend" / ".bago" / "core" / "provider_adapter.py",
    ]
    for cand in candidates:
        try:
            if not cand.exists():
                continue
        except OSError:
            continue
        spec = importlib.util.spec_from_file_location(
            "provider_adapter", str(cand)
        )
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules["provider_adapter"] = module
        spec.loader.exec_module(module)
        return module.ProviderAdapter
    raise ImportError("canonical ProviderAdapter not found")


@dataclass
class AdapterResponse:
    content: str
    attestation: ProviderAttestation | None
    log: EventLog
    rejection_reasons: list[str]


# B1 (CRIT v0.2): el adapter del bridge se registra como
# subclase virtual del canónico `ProviderAdapter` usando
# `ProviderAdapter.register()`. Esto permite que el router BAGO use
# `isinstance(adapter, ProviderAdapter)` para descubrir el adapter
# SIN requerir herencia formal (que exigiría adaptar las firmas
# de `chat` para coincidir exactamente con el canónico).
#
# Esto preserva la API dict-returning del bridge (Fase 1+) y
# simultáneamente cumple el contrato de descubrimiento del router.
# El canónico se carga una sola vez al importarse este módulo.
_BaseProviderAdapter = object  # type: ignore[misc, assignment]
try:
    _BaseProviderAdapter = _import_provider_adapter_base()
except ImportError:
    pass


class BagoPiProviderAdapter:
    """Adapter que delega en el sidecar BagoPiBridge.

    B1 (CRIT v0.2): registrado como subclase virtual del canónico
    `ProviderAdapter` mediante `ProviderAdapter.register()`. Esto
    permite que el router BAGO detecte el adapter con
    `isinstance(adapter, ProviderAdapter)` sin necesidad de herencia
    formal. La API expuesta es la misma que el canónico: `chat`,
    `list_models`, `health_check`, `is_configured`,
    `supports_tools`, `supports_streaming`. La firma de `chat`
    retorna `dict` (no `ProviderResponse`) por compatibilidad con
    los consumidores existentes del bridge; el router debe usar
    `isinstance` para discovery, no para coerción de tipos.
    """

    provider_name = "bago-pi-bridge"

    def __init__(
        self,
        config: PiBridgeConfig | None = None,
        *,
        integrations_dir: Path | None = None,
        session_id: str = "session-1",
        session_revision: str = "rev-1",
        workspace_id: str = "ws-1",
        workspace_root: str = ".",
        workspace_scope_root: str = ".",
        project_root: str = ".",
        credential_ref: str = "ref-bago-mock",
    ) -> None:
        self._config = config or load_config()
        self._integrations_dir = (
            integrations_dir
            or Path(__file__).resolve().parent
        )
        self._session_id = session_id
        self._session_revision = session_revision
        self._workspace_id = workspace_id
        self._workspace_root = str(workspace_root)
        self._workspace_scope_root = str(workspace_scope_root)
        self._project_root = str(project_root)
        self._credential_ref = credential_ref

        # Si el adapter está activo, valida que el contrato canónico
        # existe. Si no, no fallamos al instanciar (queda en modo
        # experimental), pero `chat` lo exigirá.
        try:
            self._base_class = _import_provider_adapter_base()
            self._implements_canonical = True
        except ImportError:
            self._base_class = object
            self._implements_canonical = False

    # ── API compatible con ProviderAdapter ──────────────────────────────

    def is_configured(self) -> bool:
        return bool(self._config.enabled) and self._config.max_phase >= 1

    def health_check(self, timeout: float = 5.0) -> dict[str, Any]:
        if not self._config.enabled:
            return {
                "ok": False,
                "provider": self.provider_name,
                "detail": "bridge disabled (quarantine)",
                "latency_ms": 0.0,
                "models_available": 0,
            }
        return {
            "ok": True,
            "provider": self.provider_name,
            "detail": "ok",
            "latency_ms": 0.0,
            "models_available": 0,
        }

    def supports_tools(self) -> bool:
        return False  # Fase 1: no tools

    def supports_streaming(self) -> bool:
        return False  # Fase 1: no streaming

    def list_models(self) -> list[dict[str, Any]]:
        # En Fase 1 el adapter no añade modelos al catálogo; el router
        # BAGO sigue usando el catálogo canónico.
        return []

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        provider_key: str = "bago-pi-bridge",
        envelope_id: str = "env-1",
        envelope_digest: str = "env-1",
    ) -> dict[str, Any]:
        """Ejecuta una llamada de inferencia a través del sidecar.

        Devuelve un dict con la respuesta consolidada. La forma es
        compatible con la salida del canónico: `content`, `model`,
        `provider`, `finish_reason`, `usage`, `metadata`, `attestation`,
        `event_log`, `rejection_reasons`.
        """
        if stream:
            raise CapabilityDenied(
                "streaming not supported in phase 1",
            )
        if tools:
            raise ToolNotAllowed(
                "tools not allowed in phase 1",
                details={"tools": list(tools)},
            )
        if not self._config.enabled:
            raise CapabilityDenied(
                "bridge disabled by config",
                details={"enabled": self._config.enabled},
            )
        if self._config.max_phase < 1:
            raise CapabilityDenied(
                "max_phase < 1",
                details={"max_phase": self._config.max_phase},
            )

        # Fase 3+: delegar al AgentRunner para captura completa y
        # persistencia.
        if self._config.max_phase >= 3:
            return self._chat_via_runner(
                messages=messages,
                model=model,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_key=provider_key,
                envelope_id=envelope_id,
                envelope_digest=envelope_digest,
            )

        request = _build_request(
            provider=provider_key,
            model=model,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            config=self._config,
            envelope_id=envelope_id,
            envelope_digest=envelope_digest,
            session_id=self._session_id,
            session_revision=self._session_revision,
            workspace_id=self._workspace_id,
            project_root=self._project_root,
            workspace_root=self._workspace_root,
            workspace_scope_root=self._workspace_scope_root,
            credential_ref=self._credential_ref,
        )

        # Preflight
        preflight(
            request.to_dict(),
            observed_envelope_digest=envelope_digest,
            active_session_revision=self._session_revision,
            phase=1,
            config=self._config,
            integrations_dir=self._integrations_dir,
        )

        # 2. Ejecutar sidecar
        sidecar = _sidecar_path(self._integrations_dir)
        node = _node_binary()
        # El HOME efímero se monta FUERA del workspace del proyecto
        # para evitar cualquier fuga de artefactos en
        # `workspace_scope_root`.
        from tempfile import gettempdir
        spec = build_boundary(
            argv=[node, str(sidecar)],
            cwd=self._workspace_scope_root,
            timeout_seconds=30.0,
            correlation_id=request.correlation_id,
            execution_id=request.execution_id,
            parent_home=Path(gettempdir()),
        )
        import json

        result = run_sidecar(
            spec,
            stdin_payload=json.dumps(request.to_dict()) + "\n",
        )
        if result.returncode != 0:
            raise BridgeError(
                "sidecar non-zero exit",
                details={
                    "returncode": result.returncode,
                    "stderr_tail": result.stderr[-512:],
                },
            )

        # 3. Capturar eventos
        log = EventLog(execution_id=request.execution_id)
        log.extend(result.stdout.splitlines())

        # 4. Attestation
        attestation_events = log.by_type("provider_attested")
        if not attestation_events:
            raise BridgeError(
                "missing provider_attested event",
                details={"event_types": list(log.by_type.keys())},
            )
        attestation = verify_attestation(
            attestation_events[0].payload,
            expected_credential_ref=self._credential_ref,
            policy=_attestation_policy(self._config),
        )

        # 5. Extraer respuesta
        content_parts = [
            e.payload.get("delta", "")
            for e in log.by_type("model_output_delta")
            if isinstance(e.payload.get("delta"), str)
        ]
        content = "".join(content_parts)

        usage_events = log.by_type("usage_reported")
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        if usage_events:
            u = usage_events[0].payload
            usage = {
                "input_tokens": int(u.get("input_tokens", 0) or 0),
                "output_tokens": int(u.get("output_tokens", 0) or 0),
                "total_tokens": int(u.get("total_tokens", 0) or 0),
            }

        # 6. Receipt
        bundle = build_receipt(
            request,
            log,
            attestation=attestation,
            attestation_policy=_attestation_policy(self._config),
            rejection_reasons=[],
        )

        return {
            "content": content,
            "model": attestation.effective_model,
            "provider": attestation.effective_provider,
            "finish_reason": "stop",
            "usage": usage,
            "metadata": {
                "attestation": attestation,
                "event_log": log,
                "bridge_version": attestation.bridge_version,
                "pi_package_version": attestation.pi_package_version,
            },
            "attestation": {
                "result": attestation.result,
                "endpoint_normalized": attestation.endpoint_normalized,
                "fallback_used": attestation.fallback_used,
                "auto_selection_used": attestation.auto_selection_used,
            },
            "receipt_bundle": bundle,
            "rejection_reasons": [],
        }

    def _chat_via_runner(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        system: str,
        temperature: float,
        max_tokens: int | None,
        provider_key: str,
        envelope_id: str,
        envelope_digest: str,
    ) -> dict[str, Any]:
        """Fase 3: delega en AgentRunner con captura completa."""
        from .agent_runner import AgentRunner, RunnerConfig
        from .contracts import CapabilityClaims
        from tempfile import gettempdir
        from pathlib import Path as _P

        # Construir el request_data (dict) que el runner espera.
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        now = _dt.now(_tz.utc)
        future = now + _td(seconds=60)
        request_data = {
            "protocol_version": "0.1.0",
            "bridge_request_id": f"br-{envelope_id}",
            "execution_id": f"exec-{envelope_id}",
            "correlation_id": self._session_id,
            "request_nonce": f"nonce-{envelope_id}",
            "issued_at": now.isoformat(),
            "deadline": future.isoformat(),
            "session_id": self._session_id,
            "session_revision": self._session_revision,
            "workspace_id": self._workspace_id,
            "project_root": self._project_root,
            "workspace_root": self._workspace_root,
            "workspace_scope_root": self._workspace_scope_root,
            "context_envelope_id": envelope_id,
            "context_envelope_digest": envelope_digest,
            "policy_profile": "agent_capture",
            "policy_digest": "phase-3",
            "capability_claims": {
                "filesystem_read": False,
                "filesystem_write": False,
                "process_spawn": False,
                "network_mode": "provider_endpoints_only",
                "tools_allowed": [],
                "skills_imported_ids": [],
                "extensions_allowed": [],
                "packages_allowed": [],
            },
            "requested_provider": provider_key,
            "requested_model": model,
            "credential_ref": self._credential_ref,
            "input": {"system": system, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
            "output_limits": {
                "max_tokens": int(max_tokens or 0),
                "max_bytes_per_event": 262144,
                "max_events": 4096,
                "max_seconds": 30,
            },
        }

        sidecar = _sidecar_path(self._integrations_dir)
        node = _node_binary()
        runner_config = RunnerConfig(
            enabled=True,
            max_phase=self._config.max_phase,
            workspace_root=self._workspace_root,
            workspace_scope_root=self._workspace_scope_root,
            project_root=self._project_root,
            session_id=self._session_id,
            session_revision=self._session_revision,
            workspace_id=self._workspace_id,
            credential_ref=self._credential_ref,
            sidecar_path=str(sidecar),
            node_path=node,
            timeout_seconds=30.0,
        )
        runner = AgentRunner(runner_config)
        claims = CapabilityClaims(
            filesystem_read=False,
            filesystem_write=False,
            process_spawn=False,
            network_mode="provider_endpoints_only",
            tools_allowed=(),
            skills_imported_ids=(),
            extensions_allowed=(),
            packages_allowed=(),
        )
        result = runner.run(
            request_data,
            observed_envelope_digest=envelope_digest,
            claims=claims,
        )
        if result.state.value == "rejected":
            raise BridgeError(
                "runner rejected",
                details={"reasons": result.rejection_reasons},
            )
        # Extraer respuesta consolidada del bundle.
        bundle = result.bundle
        att = bundle.bridge_metadata.get("attestation", {})
        # Reconstruir el formato compatible con el resto del adapter.
        return {
            "content": bundle.context_receipt.response_content,
            "model": att.get("effective_model", model),
            "provider": att.get("effective_provider", provider_key),
            "finish_reason": "stop",
            "usage": bundle.context_receipt.usage,
            "metadata": {
                "attestation": bundle.bridge_metadata.get("attestation", {}),
                "event_log": result.log,
                "bridge_version": att.get("bridge_version", "0.1.0"),
                "pi_package_version": att.get("pi_package_version", ""),
            },
            "attestation": bundle.bridge_metadata.get("attestation", {}),
            "receipt_bundle": bundle,
            "rejection_reasons": result.rejection_reasons,
        }


def make_adapter(
    **kwargs: Any,
) -> BagoPiProviderAdapter:
    """Factory para crear el adapter. Usado por tests y por el router."""
    return BagoPiProviderAdapter(**kwargs)


# B1 (CRIT v0.2): registro como subclase virtual del canónico
# `ProviderAdapter`. Esto hace que `isinstance(adapter, ProviderAdapter)`
# devuelva `True` para cualquier instancia de `BagoPiProviderAdapter`,
# satisfaciendo el contrato de descubrimiento del router BAGO.
if _BaseProviderAdapter is not object:
    try:
        _BaseProviderAdapter.register(BagoPiProviderAdapter)
    except (AttributeError, TypeError):
        # El canónico no acepta registro (versiones futuras podrían
        # cambiar). En ese caso, el bridge funciona por duck typing
        # pero el router debe usar otra estrategia de discovery.
        pass


__all__ = [
    "BagoPiProviderAdapter",
    "make_adapter",
    "AdapterResponse",
]

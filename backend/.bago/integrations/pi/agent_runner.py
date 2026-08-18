"""agent_runner.py — Fase 3: agent runner con captura completa.

Orquesta el ciclo de vida de una ejecución de Fase 3:

    Preflight → Running → Capturing → ExecutedUnverified
                │          │
                └─ Rejected (drift, receipt ausente, evento desconocido)

Reglas no negociables:
    - El `ContextEnvelope` debe estar firmado/digerido y la session
      revision vigente; sin esto, la ejecución se rechaza.
    - Cada paso (petición, respuesta, uso, tool call) se captura como
      evento en el `EventLog` con hash chain.
    - Cada `ToolReceipt` se asocia a su `tool_result_attached`.
    - `pi_finished` se traduce a `EXECUTION_COMPLETED_UNVERIFIED`. El
      runner **nunca** transita a `done`/`verified`/`certified`.
    - La cancelación se propaga desde BAGO: si `cancel()` se invoca,
      el sidecar se mata y el log se cierra con `BRIDGE_TIMEOUT` o
      `BRIDGE_CANCELLED`.
    - Los eventos y receipts se persisten en
      `project_root/.gabo/integrations/pi/receipts/<execution_id>/`
      con `fsync` por evento.

El runner no instancia el SDK de PI: delega en el sidecar Node que
se ejecuta como proceso aislado. La autoridad de cada decisión
(ejecutar tool, denegar, abortar) vive en el código BAGO.
"""
from __future__ import annotations

import enum
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .contracts import (
    ALLOWED_EVENTS_F3,
    BridgeEvent,
    BridgeExecutionRequest,
    CapabilityClaims,
    make_event,
)
from .errors import (
    BridgeError,
    BridgeProtocolViolation,
    BridgeTimeout,
    ContextEnvelopeRequired,
    DigestMismatch,
    MissingToolReceipt,
    SessionRevisionObsolete,
    ToolNotAllowed,
)
from .event_capture import EventLog
from .preflight import preflight
from .process_boundary import build_boundary, run_sidecar
from .protocol import MAX_EVENT_BYTES, MAX_EVENTS_TOTAL, decode_event
from .readonly_tool_proxy import invoke_tool, build_tool_receipt, ToolDecision
from .tool_event_flow import process_tool_events, require_receipts
from .wal import WALStore


# ── Estados de la máquina ──────────────────────────────────────────────────


class RunnerState(str, enum.Enum):
    """Estados permitidos para la máquina del runner.

    La máquina es lineal: Preflight → Running → Capturing →
    ExecutedUnverified. La única bifurcación es a Rejected desde
    cualquier estado. No existe transición directa a
    `done`/`verified`/`certified`."""

    PREFLIGHT = "preflight"
    RUNNING = "running"
    CAPTURING = "capturing"
    EXECUTED_UNVERIFIED = "executed_unverified"
    REJECTED = "rejected"

    def is_terminal(self) -> bool:
        return self in (
            RunnerState.EXECUTED_UNVERIFIED,
            RunnerState.REJECTED,
        )


# Estados terminales alcanzables. `done`/`verified`/`certified` NO
# son estados válidos del runner: pertenecen al validador BAGO.
TERMINAL_STATES: frozenset[RunnerState] = frozenset(
    {RunnerState.EXECUTED_UNVERIFIED, RunnerState.REJECTED}
)


# ── Cancelación ────────────────────────────────────────────────────────────


@dataclass
class CancelToken:
    """Token de cancelación cooperativo. Thread-safe."""

    cancelled: bool = False
    reason: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def cancel(self, reason: str = "cancelled by BAGO") -> None:
        with self._lock:
            if not self.cancelled:
                self.cancelled = True
                self.reason = reason

    def is_cancelled(self) -> bool:
        with self._lock:
            return self.cancelled

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"cancelled": self.cancelled, "reason": self.reason}


# ── Persistencia append-only ─────────────────────────────────────────────


def _receipts_dir(workspace_root: str, execution_id: str) -> Path:
    safe_id = "".join(c for c in execution_id if c.isalnum() or c in "-_")
    return Path(workspace_root) / ".gabo" / "integrations" / "pi" / "receipts" / safe_id


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Escribe JSON de forma atómica con fsync.

    Garantiza que un crash a mitad de escritura no corrompe el receipt.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, sort_keys=True, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _persist_event(workspace_root: str, execution_id: str, event: BridgeEvent) -> None:
    base = _receipts_dir(workspace_root, execution_id)
    seq = event.sequence_number
    fname = f"event_{seq:06d}.json"
    _atomic_write_json(base / fname, event.to_dict())


def _persist_receipt(workspace_root: str, execution_id: str, receipt: Any) -> None:
    base = _receipts_dir(workspace_root, execution_id)
    receipt_id = getattr(receipt, "tool_call_id", "unknown")
    safe = "".join(c for c in receipt_id if c.isalnum() or c in "-_")
    _atomic_write_json(base / f"tool_receipt_{safe}.json", receipt.to_dict())


def _persist_burned_bundle(workspace_root: str, execution_id: str, bundle: Any) -> None:
    base = _receipts_dir(workspace_root, execution_id)
    payload = bundle.to_dict() if hasattr(bundle, "to_dict") else dict(bundle)
    _atomic_write_json(base / "context_receipt.json", payload)


# ── Máquina del runner ────────────────────────────────────────────────────


@dataclass
class RunnerConfig:
    enabled: bool
    max_phase: int
    workspace_root: str
    workspace_scope_root: str
    project_root: str
    session_id: str
    session_revision: str
    workspace_id: str
    credential_ref: str
    sidecar_path: str
    node_path: str
    timeout_seconds: float = 30.0
    sidecar_artifact_hash: str = ""
    pi_lockfile_hash: str = ""

    @classmethod
    def from_args(cls, **kwargs: Any) -> "RunnerConfig":
        return cls(**kwargs)


@dataclass
class RunnerResult:
    """Resultado final del runner."""

    state: RunnerState
    final_status: str
    bundle: Any | None = None
    log: EventLog | None = None
    receipts: list[Any] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    events_persisted: int = 0
    receipts_persisted: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "final_status": self.final_status,
            "rejection_reasons": list(self.rejection_reasons),
            "events_persisted": self.events_persisted,
            "receipts_persisted": self.receipts_persisted,
        }


# ── El runner en sí ───────────────────────────────────────────────────────


class AgentRunner:
    """Runner de Fase 3 con máquina de estados explícita.

    Esta clase NO instancia el SDK de PI. Delega en el sidecar Node
    y procesa el stream JSONL resultante. La autoridad de cada gate
    vive en módulos del bridge (`preflight`, `policy_gate`,
    `scope_validator`, `readonly_tool_proxy`, `tool_event_flow`,
    `attestation`).
    """

    def __init__(
        self,
        config: RunnerConfig,
        *,
        cancel_token: CancelToken | None = None,
        on_event: Callable[[BridgeEvent], None] | None = None,
    ) -> None:
        self._config = config
        self._cancel = cancel_token or CancelToken()
        self._on_event = on_event
        # _process se llena al iniciar; se mata en cancel.
        self._process: subprocess.Popen | None = None
        # A2 (CRIT v0.2): WAL se inicializa al entrar a Capturing.
        self._wal: WALStore | None = None

    def cancel(self, reason: str = "cancelled by BAGO") -> None:
        """Cancela la ejecución. Idempotente."""
        self._cancel.cancel(reason)
        proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except (OSError, ProcessLookupError):
                pass
            try:
                proc.kill()
            except (OSError, ProcessLookupError):
                pass

    def run(
        self,
        request_data: dict[str, Any],
        *,
        observed_envelope_digest: str,
        claims: CapabilityClaims | None = None,
    ) -> RunnerResult:
        """Ejecuta la cadena completa.

        1. Preflight (envelope digest, session revision, nonce, claims,
           scope, integridad lockfile).
        2. Lanza el sidecar y consume el stream JSONL.
        3. Captura eventos en `EventLog` con hash chain.
        4. Procesa `tool_requested` emitiendo `tool_policy_decided` +
           `tool_result_attached` + `ToolReceipt`.
        5. Al recibir `pi_finished`, transita a
           `EXECUTED_UNVERIFIED`. Nunca a `done`/`verified`/`certified`.
        6. Persiste eventos y receipts.
        7. Entrega el bundle al validador BAGO (no se promueve estado).
        """
        reasons: list[str] = []

        # ── Estado 1: Preflight ──
        try:
            preflight(
                request_data,
                observed_envelope_digest=observed_envelope_digest,
                active_session_revision=self._config.session_revision,
                phase=3,
                integrations_dir=Path(self._config.sidecar_path).parent.parent
                if self._config.sidecar_path
                else None,
            )
        except (BridgeError, ContextEnvelopeRequired, DigestMismatch, SessionRevisionObsolete) as exc:
            return self._reject([exc.code], str(exc))

        if self._cancel.is_cancelled():
            return self._reject(["BRIDGE_CANCELLED"], self._cancel.reason)

        if claims is None:
            claims = CapabilityClaims()

        # ── Estado 2: Running ──
        try:
            spec = build_boundary(
                argv=[self._config.node_path, self._config.sidecar_path],
                cwd=self._config.workspace_scope_root,
                timeout_seconds=self._config.timeout_seconds,
                correlation_id=str(request_data.get("correlation_id") or ""),
                execution_id=str(request_data.get("execution_id") or ""),
                parent_home=Path(os.environ.get("TEMP", "/tmp")),
                extra_env={"BAGO_BRIDGE_PHASE": "3"},
            )
        except BridgeError as exc:
            return self._reject([exc.code], str(exc))

        if not spec.argv:
            return self._reject(["PI_PROCESS_SPAWN_DENIED"], "empty argv")

        # Construir el request y lanzar el sidecar.
        try:
            req_obj = BridgeExecutionRequest.from_dict(request_data)
        except BridgeError as exc:
            return self._reject([exc.code], str(exc))

        # Validar event allowlist por fase.
        if 3 not in ALLOWED_EVENTS_F3 and not ALLOWED_EVENTS_F3:
            return self._reject(["PI_PHASE_LOCKED"], "phase 3 events not allowed")

        # ── Lanzar el sidecar ──
        try:
            self._process = subprocess.Popen(
                list(spec.argv),
                cwd=spec.cwd,
                env=spec.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
        except FileNotFoundError as exc:
            return self._reject(["PI_PROCESS_SPAWN_DENIED"], str(exc))
        except OSError as exc:
            return self._reject(["PI_PROCESS_SPAWN_DENIED"], str(exc))

        try:
            stdout, _ = self._process.communicate(
                input=json.dumps(request_data) + "\n",
                timeout=self._config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            try:
                self._process.kill()
            except (OSError, ProcessLookupError):
                pass
            return self._reject(["BRIDGE_TIMEOUT"], str(exc))

        if self._cancel.is_cancelled():
            return self._reject(["BRIDGE_CANCELLED"], self._cancel.reason)

        returncode = self._process.returncode
        if returncode != 0:
            reasons.append(f"sidecar_exit_{returncode}")
            return self._reject(reasons, f"sidecar exit code {returncode}")

        # ── Estado 3: Capturing ──
        execution_id = req_obj.execution_id
        # A2 (CRIT v0.2): el WAL se inicializa aquí. Vive hasta el
        # final del run, exitoso o rechazado. Garantiza que
        # cualquier evento aceptado está en disco.
        wal = WALStore(self._config.workspace_root)
        self._wal = wal
        log = EventLog(execution_id=execution_id)
        events_persisted = 0
        try:
            for line in (stdout or "").splitlines():
                if not line.strip():
                    continue
                # Validar tamaño de línea antes de parsear.
                if len(line.encode("utf-8")) > MAX_EVENT_BYTES:
                    return self._reject(
                        ["BRIDGE_PROTOCOL_VIOLATION"],
                        f"event line > {MAX_EVENT_BYTES} bytes",
                    )
                # El log respeta MAX_EVENTS_TOTAL internamente.
                if len(log) >= MAX_EVENTS_TOTAL:
                    return self._reject(
                        ["BRIDGE_PROTOCOL_VIOLATION"],
                        f"too many events (> {MAX_EVENTS_TOTAL})",
                    )
                try:
                    event = decode_event(line, phase=3)
                except (BridgeProtocolViolation, BridgeError) as exc:
                    return self._reject([exc.code], str(exc))
                # A2 (CRIT v0.2): WAL append ANTES de aceptar el evento
                # en memoria. Si WAL falla, el evento se rechaza y la
                # ejecución pasa a REJECTED. Si WAL tiene éxito, el
                # evento está en disco antes de que el log lo
                # registre, garantizando la invariante "si el bridge
                # afirma EXECUTED_UNVERIFIED, los eventos están en
                # disco".
                try:
                    wal.append(execution_id, event.to_dict())
                except BridgeError as exc:
                    return self._reject([exc.code], str(exc))
                log.append(event)
                # Persistir inmediatamente (atomic write en
                # .gabo/integrations/pi/receipts/<id>/event_*.json).
                try:
                    _persist_event(self._config.workspace_root, execution_id, event)
                    events_persisted += 1
                except OSError:
                    # Si la persistencia falla, la ejecución se rechaza.
                    return self._reject(
                        ["BRIDGE_PERSISTENCE_FAILED"],
                        "could not persist event",
                    )
                if self._on_event is not None:
                    self._on_event(event)
        except BridgeProtocolViolation as exc:
            return self._reject([exc.code], str(exc))

        if self._cancel.is_cancelled():
            return self._reject(["BRIDGE_CANCELLED"], self._cancel.reason)

        if self._cancel.is_cancelled():
            return self._reject(["BRIDGE_CANCELLED"], self._cancel.reason)

        # ── Validación intermedia: el sidecar debe haber emitido
        # `pi_finished` para que la ejecución se considere terminada.
        # Esta comprobación se hace ANTES de procesar tool events,
        # porque los tool events sintéticos del bridge se anexan
        # después.
        sidecar_events = list(log.events())
        if not any(e.event_type == "pi_finished" for e in sidecar_events):
            return self._reject(
                ["PI_MISSING_PI_FINISHED"],
                "no pi_finished event from sidecar",
            )

        # ── Drift detection: ¿hay drift de provider/modelo en la
        # attestation?
        att_events = log.by_type("provider_attested")
        if not att_events:
            return self._reject(
                ["PI_MISSING_ATTESTATION"],
                "no provider_attested event",
            )
        att_payload = att_events[0].payload
        if att_payload.get("result") != "MATCH":
            return self._reject(
                ["PROVIDER_ATTESTATION_MISMATCH"],
                f"result={att_payload.get('result')}",
            )
        requested_provider = str(request_data.get("requested_provider") or "")
        requested_model = str(request_data.get("requested_model") or "")
        if (
            att_payload.get("effective_provider") != requested_provider
            or att_payload.get("effective_model") != requested_model
        ):
            return self._reject(
                ["PROVIDER_ATTESTATION_MISMATCH"],
                "effective != requested",
            )

        # ── Tool flow ──
        requested = log.by_type("tool_requested")
        receipts: list[Any] = []
        receipts_persisted = 0
        if requested:
            flow = process_tool_events(
                log=log,
                claims=claims,
                scope_root=self._config.workspace_scope_root,
                execution_id=execution_id,
                start_sequence=len(log) + 1,
                last_event_hash=log.last_hash(),
            )
            # Validar que cada tool_requested tenga receipt.
            try:
                require_receipts(flow.decisions, flow.receipts, requested)
            except MissingToolReceipt as exc:
                return self._reject([exc.code], str(exc))
            receipts = flow.receipts
            # Anexar los nuevos eventos al log (con chain correcto).
            # A2 (CRIT v0.2): WAL append ANTES de aceptar en memoria.
            for ev in flow.new_events:
                try:
                    wal.append(execution_id, ev.to_dict())
                except BridgeError as exc:
                    return self._reject([exc.code], str(exc))
                log.append(ev)
                try:
                    _persist_event(self._config.workspace_root, execution_id, ev)
                    events_persisted += 1
                except OSError:
                    return self._reject(
                        ["BRIDGE_PERSISTENCE_FAILED"],
                        "could not persist tool event",
                    )
            for r in receipts:
                try:
                    _persist_receipt(self._config.workspace_root, execution_id, r)
                    receipts_persisted += 1
                except OSError:
                    return self._reject(
                        ["BRIDGE_PERSISTENCE_FAILED"],
                        "could not persist tool receipt",
                    )

        # ── Construir bundle ──
        try:
            from .receipt_factory import build_receipt
            from .attestation import AttestationPolicy

            # Construir un ProviderAttestation mínimo desde el payload
            # del sidecar para que build_receipt pueda incluirlo.
            from .contracts import ProviderAttestation

            att = ProviderAttestation(
                requested_provider=str(att_payload.get("requested_provider") or ""),
                effective_provider=str(att_payload.get("effective_provider") or ""),
                requested_model=str(att_payload.get("requested_model") or ""),
                effective_model=str(att_payload.get("effective_model") or ""),
                endpoint_normalized=str(att_payload.get("endpoint_normalized") or ""),
                adapter=str(att_payload.get("adapter") or ""),
                bridge_version=str(att_payload.get("bridge_version") or "0.1.0"),
                pi_package_version=str(att_payload.get("pi_package_version") or ""),
                pi_lockfile_hash=str(att_payload.get("pi_lockfile_hash") or ""),
                sidecar_artifact_hash=str(att_payload.get("sidecar_artifact_hash") or ""),
                credential_ref=str(att_payload.get("credential_ref") or ""),
                fallback_used=bool(att_payload.get("fallback_used") or False),
                auto_selection_used=bool(att_payload.get("auto_selection_used") or False),
                config_effective=dict(att_payload.get("config_effective") or {}),
                result=str(att_payload.get("result") or "MATCH"),
            )
            bundle = build_receipt(
                req_obj,
                log,
                attestation=att,
                attestation_policy=AttestationPolicy(),
                tool_receipts=receipts,
                rejection_reasons=[],
            )
        except Exception as exc:  # noqa: BLE001
            return self._reject(["BRIDGE_BUNDLE_BUILD_FAILED"], str(exc))

        # ── Persistir bundle ──
        try:
            _persist_burned_bundle(self._config.workspace_root, execution_id, bundle)
        except OSError:
            return self._reject(
                ["BRIDGE_PERSISTENCE_FAILED"],
                "could not persist context receipt",
            )

        # ── Transición a EXECUTED_UNVERIFIED (nunca a done/verified) ──
        # A2 (CRIT v0.2): cerrar el WAL antes de retornar.
        if self._wal is not None:
            self._wal.close_all()
            self._wal = None
        return RunnerResult(
            state=RunnerState.EXECUTED_UNVERIFIED,
            final_status="EXECUTION_COMPLETED_UNVERIFIED",
            bundle=bundle,
            log=log,
            receipts=receipts,
            rejection_reasons=[],
            events_persisted=events_persisted,
            receipts_persisted=receipts_persisted,
        )

    def _reject(
        self, codes: list[str], detail: str
    ) -> RunnerResult:
        """Cierra la ejecución en estado REJECTED.

        A2 (CRIT v0.2): cierra el WAL si está abierto. El WAL persiste
        los eventos aceptados antes de este punto; los rechazados
        nunca llegaron a él.
        """
        if self._wal is not None:
            self._wal.close_all()
            self._wal = None
        return RunnerResult(
            state=RunnerState.REJECTED,
            final_status="REJECTED",
            rejection_reasons=[*codes, detail],
        )


__all__ = [
    "AgentRunner",
    "RunnerConfig",
    "RunnerResult",
    "RunnerState",
    "CancelToken",
    "TERMINAL_STATES",
]

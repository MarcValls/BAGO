"""Fase 3 — tests del agent_runner.

Cubre:
    - Máquina de estados: preflight, running, capturing, executed_unverified
    - Cancelación cooperativa
    - Persistencia atómica de eventos y receipts
    - Traducción de `pi_finished` a `EXECUTION_COMPLETED_UNVERIFIED`
    - Ausencia de transiciones a `done`/`verified`/`certified`
    - Rechazo cuando falta pi_finished, cuando hay drift, cuando no
      hay provider_attested, etc.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INTEGRATIONS_DIR = REPO_ROOT / ".bago" / "integrations" / "pi"
SIDECAR_JS = INTEGRATIONS_DIR / "sidecar" / "src" / "main.js"


def _node_available() -> bool:
    return shutil.which("node") is not None


def _sidecar_present() -> bool:
    return SIDECAR_JS.exists()


def _request_payload(
    *,
    execution_id: str = "exec-1",
    correlation_id: str = "corr-1",
    envelope_id: str = "env-1",
    session_revision: str = "rev-1",
    scope_root: str = ".",
    project_root: str = ".",
    workspace_root: str = ".",
    session_id: str = "sess-1",
    workspace_id: str = "ws-1",
    provider: str = "bago-pi-mock",
    model: str = "mock-1",
    credential_ref: str = "ref-bago-mock",
    issued_at: str | None = None,
    deadline: str | None = None,
    extra: dict | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "protocol_version": "0.1.0",
        "bridge_request_id": f"br-{execution_id}",
        "execution_id": execution_id,
        "correlation_id": correlation_id,
        "request_nonce": f"nonce-{time.time_ns()}",
        "issued_at": issued_at or now.isoformat(),
        "deadline": deadline or (now + timedelta(seconds=60)).isoformat(),
        "session_id": session_id,
        "session_revision": session_revision,
        "workspace_id": workspace_id,
        "project_root": project_root,
        "workspace_root": workspace_root,
        "workspace_scope_root": scope_root,
        "context_envelope_id": envelope_id,
        "context_envelope_digest": envelope_id,
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
        "requested_provider": provider,
        "requested_model": model,
        "credential_ref": credential_ref,
        "input": {"messages": [{"role": "user", "content": "hi"}], "system": ""},
        "output_limits": {
            "max_tokens": 10,
            "max_bytes_per_event": 262144,
            "max_events": 4096,
            "max_seconds": 30,
        },
        **({"extra": extra} if extra else {}),
    }


def _config(
    workspace_root: str,
    workspace_scope_root: str,
    session_revision: str = "rev-1",
) -> "RunnerConfig":
    from integrations.pi.agent_runner import RunnerConfig

    return RunnerConfig(
        enabled=True,
        max_phase=3,
        workspace_root=workspace_root,
        workspace_scope_root=workspace_scope_root,
        project_root=workspace_root,
        session_id="sess-1",
        session_revision=session_revision,
        workspace_id="ws-1",
        credential_ref="ref-bago-mock",
        sidecar_path=str(SIDECAR_JS),
        node_path=shutil.which("node") or "node",
        timeout_seconds=15.0,
    )


def _override_max_phase_to_3() -> None:
    """Override the default `max_phase=0` from the real config.json.

    In Fase 0 the real `backend/.bago/config.json` has `max_phase: 0`
    (quarantine). The runner needs `max_phase >= 3` to operate. This
    helper forces the env var that `load_config` respects.
    """
    os.environ["BAGO_PI_MAX_PHASE"] = "3"


pytestmark = pytest.mark.skipif(
    not _node_available() or not _sidecar_present(),
    reason="node or sidecar not available",
)


@pytest.fixture(autouse=True)
def _force_max_phase_3(monkeypatch: pytest.MonkeyPatch) -> None:
    """En Fase 3 el runner necesita `max_phase >= 3`. La configuración
    canónica del backend fija `max_phase: 0` en cuarentena; forzamos
    el env para los tests sin tocar el `config.json` real."""
    monkeypatch.setenv("BAGO_PI_MAX_PHASE", "3")


# ── Estado 1: Preflight ──────────────────────────────────────────────────


def test_runner_rejects_when_envelope_digest_mismatch(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest="WRONG-DIGEST",
    )
    assert result.state == RunnerState.REJECTED
    assert "DIGEST_MISMATCH" in result.rejection_reasons


def test_runner_rejects_when_session_revision_obsolete(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path), str(tmp_path), session_revision="rev-2")
    runner = AgentRunner(cfg)
    req = _request_payload(
        scope_root=str(tmp_path),
        workspace_root=str(tmp_path),
        session_revision="rev-1",
    )
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.REJECTED
    assert "SESSION_REVISION_OBSOLETE" in result.rejection_reasons


def test_runner_rejects_when_envelope_id_missing(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    req["context_envelope_id"] = ""
    req["context_envelope_digest"] = ""
    result = runner.run(
        req,
        observed_envelope_digest="",
    )
    assert result.state == RunnerState.REJECTED
    assert "CONTEXT_ENVELOPE_REQUIRED" in result.rejection_reasons


# ── Estado 2-4: Happy path ───────────────────────────────────────────────


def test_runner_full_cycle_reaches_executed_unverified(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.EXECUTED_UNVERIFIED, result.rejection_reasons
    assert result.final_status == "EXECUTION_COMPLETED_UNVERIFIED"
    # done/verified/certified NUNCA aparecen en el estado final.
    assert "done" not in result.final_status.lower()
    assert "verified" not in result.final_status.lower() or "unverified" in result.final_status.lower()
    assert "certified" not in result.final_status.lower()
    # El bundle tiene ContextReceipt canónico.
    assert result.bundle is not None
    assert result.bundle.final_status == "EXECUTION_COMPLETED_UNVERIFIED"
    # El log tiene los 5 eventos esperados del sidecar mock.
    assert result.log is not None
    types = [e.event_type for e in result.log.events()]
    assert types == [
        "runtime_attested",
        "provider_attested",
        "model_output_delta",
        "usage_reported",
        "pi_finished",
    ]
    # Eventos persistidos en disco.
    events_dir = tmp_path / ".gabo" / "integrations" / "pi" / "receipts" / "exec-1"
    assert events_dir.exists()
    persisted = sorted(events_dir.glob("event_*.json"))
    assert len(persisted) == 5
    # Bundle persistido.
    assert (events_dir / "context_receipt.json").exists()


def test_runner_persists_events_with_atomic_writes(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.EXECUTED_UNVERIFIED
    # No hay archivos .tmp residuales.
    events_dir = tmp_path / ".gabo" / "integrations" / "pi" / "receipts" / "exec-1"
    assert not list(events_dir.glob("*.tmp"))


# ── Cancelación ──────────────────────────────────────────────────────────


def test_runner_cancel_before_run(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import (
        AgentRunner,
        CancelToken,
        RunnerState,
    )

    cfg = _config(str(tmp_path), str(tmp_path))
    token = CancelToken()
    token.cancel("test cancel before run")
    runner = AgentRunner(cfg, cancel_token=token)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.REJECTED
    assert any("BRIDGE_CANCELLED" in r for r in result.rejection_reasons)


def test_runner_cancel_during_run(tmp_path: Path) -> None:
    """Si la cancelación se invoca durante el run, el sidecar se mata."""
    from integrations.pi.agent_runner import (
        AgentRunner,
        CancelToken,
        RunnerState,
    )

    cfg = _config(str(tmp_path), str(tmp_path))
    token = CancelToken()
    runner = AgentRunner(cfg, cancel_token=token)

    def _cancel_later() -> None:
        time.sleep(0.05)
        runner.cancel("test cancel during")

    t = threading.Thread(target=_cancel_later, daemon=True)
    t.start()
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    t.join(timeout=2)
    # El runner puede llegar a REJECTED (cancel) o a EXECUTED_UNVERIFIED
    # (si el sidecar terminó antes del cancel). En cualquier caso, el
    # estado final NO debe ser `done`/`verified`.
    assert result.state in (RunnerState.REJECTED, RunnerState.EXECUTED_UNVERIFIED)


def test_cancel_token_is_thread_safe() -> None:
    from integrations.pi.agent_runner import CancelToken

    token = CancelToken()
    errors: list[str] = []

    def hammer() -> None:
        for _ in range(1000):
            try:
                if not token.is_cancelled():
                    token.cancel("threaded cancel")
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))

    import threading

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert token.is_cancelled()


# ── Tool flow integrado ─────────────────────────────────────────────────


def test_runner_with_tool_request(tmp_path: Path) -> None:
    """El runner ejecuta una tool dentro del flujo y emite el receipt."""
    from integrations.pi.contracts import CapabilityClaims
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    f = tmp_path / "x.txt"
    f.write_text("hello world", encoding="utf-8")

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    req["input"]["tool_requests"] = [
        {
            "tool_call_id": "tc-1",
            "tool": "read",
            "arguments": {"path": str(f)},
        }
    ]
    req["capability_claims"]["filesystem_read"] = True
    req["capability_claims"]["filesystem_read_root"] = str(tmp_path)
    req["capability_claims"]["tools_allowed"] = ["read"]

    claims = CapabilityClaims(
        filesystem_read=True,
        filesystem_read_root=str(tmp_path),
        filesystem_write=False,
        process_spawn=False,
        network_mode="provider_endpoints_only",
        tools_allowed=("read",),
        skills_imported_ids=(),
        extensions_allowed=(),
        packages_allowed=(),
    )
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
        claims=claims,
    )
    # El sidecar mock emite tool_requested cuando el input declara
    # `tool_requests[]`. El runner los procesa, ejecuta la tool y
    # emite el receipt. La ejecución llega a EXECUTED_UNVERIFIED.
    assert result.state == RunnerState.EXECUTED_UNVERIFIED, result.rejection_reasons
    # El tool_result aparece en el log final.
    types = [e.event_type for e in result.log.events()]
    assert "tool_requested" in types
    assert "tool_policy_decided" in types
    assert "tool_result_attached" in types


# ── Drift detection ─────────────────────────────────────────────────────


def test_runner_rejects_when_sidecar_reports_drift(tmp_path: Path) -> None:
    """Si la attestation efectiva != requested, el runner rechaza.

    Para forzar drift, escribimos un sidecar shim que reporta
    effective_provider != requested_provider.
    """
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    shim = tmp_path / "drift_sidecar.js"
    shim.write_text(
        """
const crypto = require("node:crypto");
function hashEvent(prev) {
  const sorted = Object.keys(prev).sort();
  const stable = {};
  for (const k of sorted) stable[k] = prev[k];
  return crypto.createHash("sha256").update(JSON.stringify(stable)).digest("hex");
}
const argv = process.argv.slice(2);
let raw = "";
process.stdin.on("data", c => raw += c);
process.stdin.on("end", () => {
  const req = JSON.parse(raw.split("\\n")[0]);
  const eid = req.execution_id;
  let seq = 0;
  let prev = "0".repeat(16);
  const events = [];
  function emit(et, payload) {
    seq += 1;
    const ev = {
      execution_id: eid, sequence_number: seq, event_id: "s-" + seq,
      event_type: et, timestamp: new Date().toISOString(),
      payload, previous_event_hash: prev, redaction_applied: false,
      source: "pi_sidecar",
    };
    ev.event_hash = hashEvent(ev);
    prev = ev.event_hash;
    process.stdout.write(JSON.stringify(ev) + "\\n");
  }
  emit("runtime_attested", { effective_cwd: process.cwd() });
  emit("provider_attested", {
    requested_provider: req.requested_provider,
    effective_provider: "rogue-provider",
    requested_model: req.requested_model,
    effective_model: "rogue-model",
    endpoint_normalized: "mock://rogue",
    adapter: "rogue", bridge_version: "0.1.0",
    pi_package_version: "0.0.0-mock",
    pi_lockfile_hash: "",
    sidecar_artifact_hash: "",
    credential_ref: req.credential_ref,
    fallback_used: false, auto_selection_used: false,
    config_effective: {}, result: "MISMATCH",
  });
  emit("model_output_delta", { delta: "drift" });
  emit("usage_reported", { input_tokens: 1, output_tokens: 1, total_tokens: 2 });
  emit("pi_finished", { finish_reason: "stop" });
});
""",
        encoding="utf-8",
    )
    cfg = _config(str(tmp_path), str(tmp_path))
    cfg = type(cfg)(
        **{**cfg.__dict__, "sidecar_path": str(shim)}
    )
    runner = AgentRunner(cfg)
    req = _request_payload(
        scope_root=str(tmp_path),
        workspace_root=str(tmp_path),
        provider="bago-pi-mock",
        model="mock-1",
    )
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.REJECTED
    assert any("PROVIDER_ATTESTATION_MISMATCH" in r for r in result.rejection_reasons)


def test_runner_rejects_when_pi_finished_missing(tmp_path: Path) -> None:
    """Si el sidecar termina sin `pi_finished`, el runner rechaza."""
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    shim = tmp_path / "no_finished_sidecar.js"
    shim.write_text(
        """
const crypto = require("node:crypto");
function hashEvent(prev) {
  const sorted = Object.keys(prev).sort();
  const stable = {};
  for (const k of sorted) stable[k] = prev[k];
  return crypto.createHash("sha256").update(JSON.stringify(stable)).digest("hex");
}
let raw = "";
process.stdin.on("data", c => raw += c);
process.stdin.on("end", () => {
  const req = JSON.parse(raw.split("\\n")[0]);
  const eid = req.execution_id;
  let seq = 0;
  let prev = "0".repeat(16);
  function emit(et, payload) {
    seq += 1;
    const ev = {
      execution_id: eid, sequence_number: seq, event_id: "s-" + seq,
      event_type: et, timestamp: new Date().toISOString(),
      payload, previous_event_hash: prev, redaction_applied: false,
      source: "pi_sidecar",
    };
    ev.event_hash = hashEvent(ev);
    prev = ev.event_hash;
    process.stdout.write(JSON.stringify(ev) + "\\n");
  }
  emit("runtime_attested", {});
  emit("provider_attested", {
    requested_provider: req.requested_provider,
    effective_provider: req.requested_provider,
    requested_model: req.requested_model,
    effective_model: req.requested_model,
    endpoint_normalized: "mock://x", adapter: "mock",
    bridge_version: "0.1.0", pi_package_version: "0.0.0-mock",
    pi_lockfile_hash: "", sidecar_artifact_hash: "",
    credential_ref: req.credential_ref, fallback_used: false,
    auto_selection_used: false, config_effective: {}, result: "MATCH",
  });
  emit("model_output_delta", { delta: "x" });
  emit("usage_reported", { input_tokens: 1, output_tokens: 1, total_tokens: 2 });
  // NO emit pi_finished.
});
""",
        encoding="utf-8",
    )
    cfg = _config(str(tmp_path), str(tmp_path))
    cfg = type(cfg)(**{**cfg.__dict__, "sidecar_path": str(shim)})
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.REJECTED
    assert any("PI_MISSING_PI_FINISHED" in r for r in result.rejection_reasons)


def test_runner_rejects_when_no_provider_attested(tmp_path: Path) -> None:
    """Si el sidecar no emite `provider_attested`, el runner rechaza."""
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    shim = tmp_path / "no_attest_sidecar.js"
    shim.write_text(
        """
const crypto = require("node:crypto");
function hashEvent(prev) {
  const sorted = Object.keys(prev).sort();
  const stable = {};
  for (const k of sorted) stable[k] = prev[k];
  return crypto.createHash("sha256").update(JSON.stringify(stable)).digest("hex");
}
let raw = "";
process.stdin.on("data", c => raw += c);
process.stdin.on("end", () => {
  const req = JSON.parse(raw.split("\\n")[0]);
  const eid = req.execution_id;
  let seq = 0;
  let prev = "0".repeat(16);
  function emit(et, payload) {
    seq += 1;
    const ev = {
      execution_id: eid, sequence_number: seq, event_id: "s-" + seq,
      event_type: et, timestamp: new Date().toISOString(),
      payload, previous_event_hash: prev, redaction_applied: false,
      source: "pi_sidecar",
    };
    ev.event_hash = hashEvent(ev);
    prev = ev.event_hash;
    process.stdout.write(JSON.stringify(ev) + "\\n");
  }
  emit("runtime_attested", {});
  // Sin provider_attested.
  emit("model_output_delta", { delta: "x" });
  emit("usage_reported", { input_tokens: 1, output_tokens: 1, total_tokens: 2 });
  emit("pi_finished", { finish_reason: "stop" });
});
""",
        encoding="utf-8",
    )
    cfg = _config(str(tmp_path), str(tmp_path))
    cfg = type(cfg)(**{**cfg.__dict__, "sidecar_path": str(shim)})
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.REJECTED
    assert any("PI_MISSING_ATTESTATION" in r for r in result.rejection_reasons)


# ── Adversariales ────────────────────────────────────────────────────────


def test_runner_rejects_oversized_event_line(tmp_path: Path) -> None:
    """Una línea de evento > MAX_EVENT_BYTES se rechaza como
    `BRIDGE_PROTOCOL_VIOLATION`."""
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    shim = tmp_path / "oversized_sidecar.js"
    shim.write_text(
        """
const crypto = require("node:crypto");
function hashEvent(prev) {
  const sorted = Object.keys(prev).sort();
  const stable = {};
  for (const k of sorted) stable[k] = prev[k];
  return crypto.createHash("sha256").update(JSON.stringify(stable)).digest("hex");
}
let raw = "";
process.stdin.on("data", c => raw += c);
process.stdin.on("end", () => {
  const req = JSON.parse(raw.split("\\n")[0]);
  const eid = req.execution_id;
  let seq = 0;
  let prev = "0".repeat(16);
  function emit(et, payload) {
    seq += 1;
    const ev = {
      execution_id: eid, sequence_number: seq, event_id: "s-" + seq,
      event_type: et, timestamp: new Date().toISOString(),
      payload, previous_event_hash: prev, redaction_applied: false,
      source: "pi_sidecar",
    };
    ev.event_hash = hashEvent(ev);
    prev = ev.event_hash;
    process.stdout.write(JSON.stringify(ev) + "\\n");
  }
  emit("runtime_attested", { huge: "x".repeat(300000) });
});
""",
        encoding="utf-8",
    )
    cfg = _config(str(tmp_path), str(tmp_path))
    cfg = type(cfg)(**{**cfg.__dict__, "sidecar_path": str(shim)})
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.REJECTED
    assert any("BRIDGE_PROTOCOL_VIOLATION" in r for r in result.rejection_reasons)


def test_runner_rejects_unknown_event(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    shim = tmp_path / "bad_event_sidecar.js"
    shim.write_text(
        """
const crypto = require("node:crypto");
function hashEvent(prev) {
  const sorted = Object.keys(prev).sort();
  const stable = {};
  for (const k of sorted) stable[k] = prev[k];
  return crypto.createHash("sha256").update(JSON.stringify(stable)).digest("hex");
}
let raw = "";
process.stdin.on("data", c => raw += c);
process.stdin.on("end", () => {
  const req = JSON.parse(raw.split("\\n")[0]);
  const eid = req.execution_id;
  let seq = 0;
  let prev = "0".repeat(16);
  function emit(et, payload) {
    seq += 1;
    const ev = {
      execution_id: eid, sequence_number: seq, event_id: "s-" + seq,
      event_type: et, timestamp: new Date().toISOString(),
      payload, previous_event_hash: prev, redaction_applied: false,
      source: "pi_sidecar",
    };
    ev.event_hash = hashEvent(ev);
    prev = ev.event_hash;
    process.stdout.write(JSON.stringify(ev) + "\\n");
  }
  emit("runtime_attested", {});
  emit("something_not_in_allowlist", {});  // Evento desconocido.
  emit("pi_finished", { finish_reason: "stop" });
});
""",
        encoding="utf-8",
    )
    cfg = _config(str(tmp_path), str(tmp_path))
    cfg = type(cfg)(**{**cfg.__dict__, "sidecar_path": str(shim)})
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.REJECTED
    assert any(
        "PI_UNKNOWN_EVENT" in r or "BRIDGE_PROTOCOL_VIOLATION" in r
        for r in result.rejection_reasons
    )


# ── Estado de la máquina ─────────────────────────────────────────────────


def test_runner_state_machine_has_no_done_state() -> None:
    """El runner NUNCA expone un estado `done`."""
    from integrations.pi.agent_runner import RunnerState

    for state in RunnerState:
        assert "done" not in state.value
        assert "verified" not in state.value or "unverified" in state.value
        assert "certified" not in state.value


def test_runner_terminal_states_are_only_unverified_or_rejected() -> None:
    from integrations.pi.agent_runner import RunnerState, TERMINAL_STATES

    assert TERMINAL_STATES == frozenset(
        {RunnerState.EXECUTED_UNVERIFIED, RunnerState.REJECTED}
    )

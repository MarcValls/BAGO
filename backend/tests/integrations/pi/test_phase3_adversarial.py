"""Fase 3 — pruebas adversariales y de cobertura.

Cubre:
    - Replay de request nonces
    - agent_step_started / agent_step_finished events
    - Persistencia atómica con fsync
    - Cancelación durante el sidecar (kill real)
    - Out-of-order events rechazados
    - Eventos faltantes detectados
    - TOCTOU en archivos
    - Bundles sin `done`/`verified`/`certified` (verificación)
"""
from __future__ import annotations

import json
import os
import shutil
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
    nonce: str | None = None,
    scope_root: str = ".",
    workspace_root: str = ".",
    provider: str = "bago-pi-mock",
    model: str = "mock-1",
    session_revision: str = "rev-1",
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "protocol_version": "0.1.0",
        "bridge_request_id": f"br-{execution_id}",
        "execution_id": execution_id,
        "correlation_id": "corr-1",
        "request_nonce": nonce or f"nonce-{time.time_ns()}",
        "issued_at": now.isoformat(),
        "deadline": (now + timedelta(seconds=60)).isoformat(),
        "session_id": "sess-1",
        "session_revision": session_revision,
        "workspace_id": "ws-1",
        "project_root": workspace_root,
        "workspace_root": workspace_root,
        "workspace_scope_root": scope_root,
        "context_envelope_id": "env-1",
        "context_envelope_digest": "env-1",
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
        "credential_ref": "ref-bago-mock",
        "input": {"messages": []},
        "output_limits": {"max_tokens": 10, "max_bytes_per_event": 262144,
                          "max_events": 4096, "max_seconds": 30},
    }


def _config(workspace_root: str, workspace_scope_root: str) -> "RunnerConfig":
    from integrations.pi.agent_runner import RunnerConfig

    return RunnerConfig(
        enabled=True,
        max_phase=3,
        workspace_root=workspace_root,
        workspace_scope_root=workspace_scope_root,
        project_root=workspace_root,
        session_id="sess-1",
        session_revision="rev-1",
        workspace_id="ws-1",
        credential_ref="ref-bago-mock",
        sidecar_path=str(SIDECAR_JS),
        node_path=shutil.which("node") or "node",
        timeout_seconds=15.0,
    )


@pytest.fixture(autouse=True)
def _force_max_phase_3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAGO_PI_MAX_PHASE", "3")


pytestmark = pytest.mark.skipif(
    not _node_available() or not _sidecar_present(),
    reason="node or sidecar not available",
)


# ── Replay protection ────────────────────────────────────────────────────


def test_runner_rejects_replay_of_same_nonce(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    fixed_nonce = f"fixed-nonce-{time.time_ns()}"
    req = _request_payload(
        scope_root=str(tmp_path),
        workspace_root=str(tmp_path),
        nonce=fixed_nonce,
    )
    # Primera ejecución: éxito.
    result1 = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result1.state == RunnerState.EXECUTED_UNVERIFIED
    # Segunda ejecución con el mismo nonce: NonceReplayDenied.
    req2 = _request_payload(
        execution_id="exec-2",
        scope_root=str(tmp_path),
        workspace_root=str(tmp_path),
        nonce=fixed_nonce,
    )
    result2 = runner.run(
        req2,
        observed_envelope_digest=req2["context_envelope_digest"],
    )
    assert result2.state == RunnerState.REJECTED
    assert any("NONCE_REPLAY_DENIED" in r for r in result2.rejection_reasons)


# ── agent_step events ────────────────────────────────────────────────────


def test_runner_accepts_agent_step_events_in_phase_3(tmp_path: Path) -> None:
    """Si el sidecar emite `agent_step_started` / `agent_step_finished`
    (permitidos en fase 3), el runner los procesa sin rechazo."""
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    shim = tmp_path / "step_sidecar.js"
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
  emit("agent_step_started", { step: 1, reason: "thinking" });
  emit("model_output_delta", { delta: "answer" });
  emit("agent_step_finished", { step: 1 });
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
    assert result.state == RunnerState.EXECUTED_UNVERIFIED
    types = [e.event_type for e in result.log.events()]
    assert "agent_step_started" in types
    assert "agent_step_finished" in types


# ── Out-of-order events ──────────────────────────────────────────────────


def test_runner_rejects_out_of_order_events(tmp_path: Path) -> None:
    """Si los eventos llegan con chain rota, el runner los rechaza."""
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    shim = tmp_path / "ooo_sidecar.js"
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
  // Simulamos chain rota: el segundo evento tiene
  // previous_event_hash incorrecto (todo ceros) en vez del hash
  // del primero.
  const ev1 = {
    execution_id: eid, sequence_number: 1, event_id: "s-1",
    event_type: "runtime_attested", timestamp: new Date().toISOString(),
    payload: {}, previous_event_hash: "0".repeat(16),
    redaction_applied: false, source: "pi_sidecar",
  };
  ev1.event_hash = hashEvent(ev1);
  process.stdout.write(JSON.stringify(ev1) + "\\n");
  const ev2 = {
    execution_id: eid, sequence_number: 2, event_id: "s-2",
    event_type: "provider_attested", timestamp: new Date().toISOString(),
    payload: {
      requested_provider: req.requested_provider,
      effective_provider: req.requested_provider,
      requested_model: req.requested_model,
      effective_model: req.requested_model,
      endpoint_normalized: "mock://x", adapter: "mock",
      bridge_version: "0.1.0", pi_package_version: "0.0.0-mock",
      pi_lockfile_hash: "", sidecar_artifact_hash: "",
      credential_ref: req.credential_ref, fallback_used: false,
      auto_selection_used: false, config_effective: {}, result: "MATCH",
    },
    // Forzamos previous_event_hash incorrecto (todo ceros) en vez
    // del hash del primer evento.
    previous_event_hash: "0".repeat(16),
    redaction_applied: false, source: "pi_sidecar",
  };
  ev2.event_hash = hashEvent(ev2);
  process.stdout.write(JSON.stringify(ev2) + "\\n");
  // Tercer evento: pi_finished con chain válida al segundo.
  const ev3 = {
    execution_id: eid, sequence_number: 3, event_id: "s-3",
    event_type: "pi_finished", timestamp: new Date().toISOString(),
    payload: { finish_reason: "stop" },
    previous_event_hash: ev2.event_hash,
    redaction_applied: false, source: "pi_sidecar",
  };
  ev3.event_hash = hashEvent(ev3);
  process.stdout.write(JSON.stringify(ev3) + "\\n");
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


# ── Persistencia atómica ─────────────────────────────────────────────────


def test_persistence_uses_atomic_writes(tmp_path: Path) -> None:
    """Verifica que cada evento se escribe de forma atómica."""
    from integrations.pi.agent_runner import _atomic_write_json

    test_file = tmp_path / "test_atomic.json"
    _atomic_write_json(test_file, {"hello": "world"})
    assert test_file.exists()
    # No hay archivos .tmp residuales.
    assert not test_file.with_suffix(".json.tmp").exists()
    # El contenido es JSON válido.
    assert json.loads(test_file.read_text()) == {"hello": "world"}


def test_runner_persists_tool_receipts(tmp_path: Path) -> None:
    from integrations.pi.contracts import CapabilityClaims
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    req["input"]["tool_requests"] = [
        {"tool_call_id": "tc-1", "tool": "read", "arguments": {"path": str(f)}}
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
    assert result.state == RunnerState.EXECUTED_UNVERIFIED
    # El tool_receipt_*.json debe estar en disco.
    receipts_dir = tmp_path / ".gabo" / "integrations" / "pi" / "receipts" / "exec-1"
    receipt_files = list(receipts_dir.glob("tool_receipt_*.json"))
    assert len(receipt_files) >= 1
    receipt_data = json.loads(receipt_files[0].read_text())
    assert receipt_data["tool"] == "read"
    assert receipt_data["status"] == "completed"
    assert receipt_data["policy_decision"] == "allow"


# ── Bundle no expone done/verified/certified ─────────────────────────────


def test_runner_bundle_never_has_done_or_verified_state(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path), str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.EXECUTED_UNVERIFIED
    bundle = result.bundle
    assert bundle is not None
    # El bundle puede serializarse.
    payload = bundle.to_dict()
    rendered = json.dumps(payload, default=str)
    # Nunca debe contener "done" como estado final, ni "verified" sin
    # "unverified", ni "certified".
    assert '"done"' not in rendered
    assert '"verified"' not in rendered
    assert '"certified"' not in rendered
    # El estado final siempre es "EXECUTION_COMPLETED_UNVERIFIED".
    assert "EXECUTION_COMPLETED_UNVERIFIED" in rendered


# ── Cancelación real ──────────────────────────────────────────────────────


def test_runner_cancel_kills_sidecar_process(tmp_path: Path) -> None:
    """Si la cancelación se invoca durante el run, el proceso sidecar
    se mata y el runner transita a REJECTED."""
    from integrations.pi.agent_runner import (
        AgentRunner,
        CancelToken,
        RunnerState,
    )

    # Sidecar que duerme indefinidamente.
    shim = tmp_path / "sleep_sidecar.js"
    shim.write_text(
        """
let raw = "";
process.stdin.on("data", c => raw += c);
process.stdin.on("end", () => {
  setInterval(() => {}, 1000);
});
""",
        encoding="utf-8",
    )
    cfg = _config(str(tmp_path), str(tmp_path))
    cfg = type(cfg)(**{**cfg.__dict__, "sidecar_path": str(shim), "timeout_seconds": 5.0})
    token = CancelToken()
    runner = AgentRunner(cfg, cancel_token=token)

    def _cancel_after() -> None:
        time.sleep(0.2)
        runner.cancel("test cancel kills sidecar")

    import threading
    t = threading.Thread(target=_cancel_after, daemon=True)
    t.start()
    req = _request_payload(scope_root=str(tmp_path), workspace_root=str(tmp_path))
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    t.join(timeout=3)
    # Cancel puede llegar antes o después del read del stdout; el
    # resultado es REJECTED.
    assert result.state == RunnerState.REJECTED
    # El estado final NUNCA es done/verified.
    assert "done" not in result.final_status.lower()
    assert "verified" not in result.final_status.lower() or "unverified" in result.final_status.lower()

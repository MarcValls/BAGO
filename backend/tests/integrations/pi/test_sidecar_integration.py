"""Test de integración con un sidecar Python que emite eventos JSONL.

Simula el sidecar Node/TS del PLAN §4.3. El sidecar simulado:
    - Recibe un BridgeExecutionRequest codificado como una línea JSON
      por stdin.
    - Emite una secuencia de eventos JSONL por stdout.
    - No toca filesystem ni red.

El test valida que el bridge puede consumir el stream del sidecar
usando `iter_events` y que la transición `pi_finished` se traduce
implícitamente a un estado `EXECUTION_COMPLETED_UNVERIFIED` (no
`done`/`verified`).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from integrations.pi.contracts import make_event
from integrations.pi.errors import UnknownEvent
from integrations.pi.preflight import preflight
from integrations.pi.process_boundary import build_boundary, run_sidecar
from integrations.pi.protocol import decode_event, encode_event, iter_events


SIDE_CAR_SCRIPT = """
import json, sys, time

req = json.loads(sys.stdin.readline())
events = []
seq = 0
prev = "0" * 16

def emit(et, payload):
    global seq, prev
    seq += 1
    ev = {
        "execution_id": req["execution_id"],
        "sequence_number": seq,
        "event_id": f"sim-{seq}",
        "event_type": et,
        "timestamp": "2025-01-01T00:00:00+00:00",
        "payload": payload,
        "previous_event_hash": prev,
        "event_hash": "h" + str(seq),
        "redaction_applied": False,
        "source": "pi_sidecar",
    }
    sys.stdout.write(json.dumps(ev) + "\\n")
    sys.stdout.flush()
    return ev["event_hash"]

emit("runtime_attested", {"home": "/tmp/ephemeral", "cwd": req["input"].get("cwd", "")})
emit("provider_attested", {"requested": req["requested_provider"], "effective": req["requested_provider"]})
emit("model_output_delta", {"delta": "hello "})
emit("model_output_delta", {"delta": "world"})
emit("usage_reported", {"input": 10, "output": 2})
emit("pi_finished", {"finish_reason": "stop"})
"""


@pytest.fixture
def sidecar_script(tmp_path: Path) -> Path:
    path = tmp_path / "fake_sidecar.py"
    path.write_text(SIDE_CAR_SCRIPT, encoding="utf-8")
    return path


def _request(tmp_path: Path) -> dict:
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    future = (now + timedelta(seconds=60)).isoformat()
    return {
        "protocol_version": "0.1.0",
        "bridge_request_id": "br-1",
        "execution_id": "exec-1",
        "correlation_id": "corr-1",
        "request_nonce": f"nonce-{os.urandom(8).hex()}",
        "issued_at": now.isoformat(),
        "deadline": future,
        "session_id": "sess-1",
        "session_revision": "rev-1",
        "workspace_id": "ws-1",
        "project_root": str(tmp_path),
        "workspace_root": str(tmp_path),
        "workspace_scope_root": str(tmp_path),
        "context_envelope_id": "env-1",
        "context_envelope_digest": "env-1",
        "policy_profile": "disabled",
        "policy_digest": "policy-1",
        "capability_claims": {
            "filesystem_read": False,
            "filesystem_write": False,
            "process_spawn": False,
            "network_mode": "none",
            "tools_allowed": [],
            "skills_imported_ids": [],
            "extensions_allowed": [],
            "packages_allowed": [],
        },
        "requested_provider": "ollama-local",
        "requested_model": "llama3.2:3b",
        "credential_ref": "ref-1",
        "input": {"cwd": str(tmp_path)},
        "output_limits": {
            "max_tokens": 100,
            "max_bytes_per_event": 65536,
            "max_events": 1024,
            "max_seconds": 30,
        },
    }


def test_sidecar_stream_roundtrip(tmp_path: Path, sidecar_script: Path) -> None:
    request = _request(tmp_path)
    preflight(
        request,
        observed_envelope_digest="env-1",
        active_session_revision="rev-1",
        phase=0,
    )

    spec = build_boundary(
        argv=[sys.executable, str(sidecar_script)],
        cwd=str(tmp_path),
        timeout_seconds=10,
        correlation_id="corr-1",
        execution_id="exec-1",
        parent_home=tmp_path,
    )
    result = run_sidecar(spec, stdin_payload=json.dumps(request) + "\n")
    assert result.returncode == 0

    events = list(iter_events(result.stdout.splitlines(), phase=0))
    assert [e.event_type for e in events] == [
        "runtime_attested",
        "provider_attested",
        "model_output_delta",
        "model_output_delta",
        "usage_reported",
        "pi_finished",
    ]
    # El bridge NO traduce pi_finished a "done": lo emite como evento
    # crudo y la autoridad final vive en el validador BAGO.
    finished = events[-1]
    assert finished.event_type == "pi_finished"
    # El bridge no expone un campo "state" = done en el evento.
    assert "state" not in finished.payload


def test_sidecar_unknown_event_rejected(tmp_path: Path, sidecar_script: Path) -> None:
    bad_script = tmp_path / "bad_sidecar.py"
    bad_script.write_text(
        SIDE_CAR_SCRIPT.replace(
            'emit("pi_finished"',
            'emit("custom_unknown_event"',
        ),
        encoding="utf-8",
    )
    request = _request(tmp_path)
    spec = build_boundary(
        argv=[sys.executable, str(bad_script)],
        cwd=str(tmp_path),
        timeout_seconds=10,
        correlation_id="c",
        execution_id="e",
        parent_home=tmp_path,
    )
    result = run_sidecar(spec, stdin_payload=json.dumps(request) + "\n")
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    # El primer evento custom_unknown_event dispara UnknownEvent.
    with pytest.raises(UnknownEvent):
        list(iter_events(lines, phase=0))

def test_sidecar_uses_ephemeral_home(tmp_path: Path, sidecar_script: Path) -> None:
    request = _request(tmp_path)
    spec = build_boundary(
        argv=[sys.executable, str(sidecar_script)],
        cwd=str(tmp_path),
        timeout_seconds=10,
        correlation_id="c",
        execution_id="e",
        parent_home=tmp_path,
    )
    result = run_sidecar(spec, stdin_payload=json.dumps(request) + "\n")
    assert spec.env["HOME"] == spec.home_dir
    # El home debe ser un directorio bajo el parent_home.
    assert Path(spec.home_dir).parent == tmp_path
    # El HOME del proceso del sidecar es el efímero, no el del usuario.
    user_home = str(Path.home())
    assert spec.home_dir != user_home
    # El stdout del sidecar contiene runtime_attested con home /tmp/...
    # Sólo validamos que el evento llegó, no su contenido exacto.
    events = list(iter_events(result.stdout.splitlines(), phase=0))
    assert events[0].event_type == "runtime_attested"

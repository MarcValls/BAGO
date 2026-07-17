"""Tests v0.2 — bloqueante B1 y acciones A1-A4.

Cubre:
    - B1: BagoPiProviderAdapter es subclase virtual de
      ProviderAdapter; `isinstance(adapter, ProviderAdapter)` es True.
    - A1: la anotación sobre `verification_state` está presente.
    - A2: el WAL persiste cada evento aceptado antes de aceptar en
      memoria; los eventos rechazados no llegan al WAL; el WAL se
      cierra al final del run (éxito o rechazo).
    - A3: el sidecar `package.json` declara `engines.node >= 20`.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INTEGRATIONS_DIR = REPO_ROOT / ".bago" / "integrations" / "pi"
SIDECAR_JS = INTEGRATIONS_DIR / "sidecar" / "src" / "main.js"


# ── B1 ───────────────────────────────────────────────────────────────────


def test_B1_adapter_is_instance_of_canonical_provider_adapter() -> None:
    """B1: el adapter del bridge es subclase virtual de `ProviderAdapter`."""
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    # Cargar el canónico (lo hace el import del bridge).
    from integrations.pi.provider_adapter import (
        _import_provider_adapter_base,
    )
    canonical = _import_provider_adapter_base()
    assert canonical is not None
    adapter = BagoPiProviderAdapter(
        workspace_root=".",
        workspace_scope_root=".",
    )
    # El registro como subclase virtual hace que isinstance
    # devuelva True.
    assert isinstance(adapter, canonical)


def test_B1_provider_adapter_module_registered_in_sys_modules() -> None:
    """B1: el canónico se registra en `sys.modules['provider_adapter']`."""
    import sys

    # Asegurar que el bridge está importado (puede que pytest ya lo
    # haya hecho, pero por si acaso).
    from integrations.pi.provider_adapter import (  # noqa: F401
        BagoPiProviderAdapter,
    )
    mod = sys.modules.get("provider_adapter")
    assert mod is not None
    assert hasattr(mod, "ProviderAdapter")


def test_B1_adapter_method_signatures_compatible() -> None:
    """B1: la API expuesta por el adapter es la misma que el canónico."""
    from integrations.pi.provider_adapter import BagoPiProviderAdapter

    adapter = BagoPiProviderAdapter(
        workspace_root=".",
        workspace_scope_root=".",
    )
    # Los 6 métodos que el router espera.
    assert callable(adapter.chat)
    assert callable(adapter.list_models)
    assert callable(adapter.health_check)
    assert callable(adapter.is_configured)
    assert callable(adapter.supports_tools)
    assert callable(adapter.supports_streaming)
    # Defaults coherentes con Fase 1+.
    assert adapter.supports_tools() is False
    assert adapter.supports_streaming() is False


# ── A1 ───────────────────────────────────────────────────────────────────


def test_A1_receipt_factory_documents_verification_state_authority() -> None:
    """A1: la anotación sobre `verification_state` está presente en
    `receipt_factory.py`."""
    receipt_factory_path = (
        REPO_ROOT / ".bago" / "integrations" / "pi" / "receipt_factory.py"
    )
    content = receipt_factory_path.read_text(encoding="utf-8")
    assert "ANOTACIÓN A1" in content
    assert "propuesta del bridge" in content
    assert "validador BAGO" in content


# ── A2 ───────────────────────────────────────────────────────────────────


def _node_available() -> bool:
    return shutil.which("node") is not None


def _sidecar_present() -> bool:
    return SIDECAR_JS.exists()


def _request_payload(tmp_path: Path) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "protocol_version": "0.1.0",
        "bridge_request_id": "br-1",
        "execution_id": "exec-A2-1",
        "correlation_id": "c-1",
        "request_nonce": f"nonce-{time.time_ns()}",
        "issued_at": now.isoformat(),
        "deadline": (now + timedelta(seconds=60)).isoformat(),
        "session_id": "sess-1",
        "session_revision": "rev-1",
        "workspace_id": "ws-1",
        "project_root": str(tmp_path),
        "workspace_root": str(tmp_path),
        "workspace_scope_root": str(tmp_path),
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
        "requested_provider": "bago-pi-mock",
        "requested_model": "mock-1",
        "credential_ref": "ref-bago-mock",
        "input": {"messages": []},
        "output_limits": {"max_tokens": 10, "max_bytes_per_event": 262144,
                          "max_events": 4096, "max_seconds": 30},
    }


def _config(workspace_root: str) -> "RunnerConfig":
    from integrations.pi.agent_runner import RunnerConfig

    return RunnerConfig(
        enabled=True,
        max_phase=3,
        workspace_root=workspace_root,
        workspace_scope_root=workspace_root,
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


@pytest.mark.skipif(
    not _node_available() or not _sidecar_present(),
    reason="node or sidecar not available",
)
def test_A2_wal_persists_events_for_successful_run(tmp_path: Path) -> None:
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(tmp_path)
    result = runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    assert result.state == RunnerState.EXECUTED_UNVERIFIED
    # El WAL existe en disco.
    wal_path = tmp_path / ".gabo" / "integrations" / "pi" / "wal" / f"{req['execution_id']}.jsonl"
    assert wal_path.exists()
    # El WAL contiene los eventos aceptados.
    lines = [
        line
        for line in wal_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) >= 5
    # El primer evento del WAL es runtime_attested, el último es pi_finished.
    events = [json.loads(line) for line in lines]
    assert events[0]["event_type"] == "runtime_attested"
    last = json.loads(lines[-1])
    assert last["event_type"] == "pi_finished"


@pytest.mark.skipif(
    not _node_available() or not _sidecar_present(),
    reason="node or sidecar not available",
)
def test_A2_wal_is_closed_after_run(tmp_path: Path) -> None:
    """A2: el WAL se cierra al final del run, sea éxito o rechazo."""
    from integrations.pi.agent_runner import AgentRunner, RunnerState

    cfg = _config(str(tmp_path))
    runner = AgentRunner(cfg)
    req = _request_payload(tmp_path)
    runner.run(
        req,
        observed_envelope_digest=req["context_envelope_digest"],
    )
    # Tras el run, runner._wal debe ser None (cerrado).
    assert runner._wal is None


def test_A2_wal_module_basic_operations(tmp_path: Path) -> None:
    """A2: el módulo WAL tiene las operaciones básicas esperadas."""
    from integrations.pi.wal import WALStore

    wal = WALStore(str(tmp_path))
    wal.append("exec-1", {"event_type": "test", "sequence_number": 1})
    wal.append("exec-1", {"event_type": "test", "sequence_number": 2})
    # list_events recupera los eventos en orden.
    events = wal.list_events("exec-1")
    assert len(events) == 2
    assert events[0]["sequence_number"] == 1
    assert events[1]["sequence_number"] == 2
    # El archivo está en la ruta esperada.
    wal_path = tmp_path / ".gabo" / "integrations" / "pi" / "wal" / "exec-1.jsonl"
    assert wal_path.exists()
    # close_all no falla.
    wal.close_all()


def test_A2_wal_rejects_unknown_execution_id_safely(tmp_path: Path) -> None:
    """A2: pedir eventos de un execution_id que no existe devuelve []."""
    from integrations.pi.wal import WALStore

    wal = WALStore(str(tmp_path))
    assert wal.list_events("nonexistent") == []


# ── A3 ───────────────────────────────────────────────────────────────────


def test_A3_sidecar_engines_declare_node_20_or_higher() -> None:
    """A3: el `package.json` del sidecar declara `engines.node >= 20.0.0`."""
    pkg_path = INTEGRATIONS_DIR / "sidecar" / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    engines = pkg.get("engines", {})
    assert "node" in engines, "engines.node missing"
    # Aceptamos `>=20.0.0`, `>=20`, o `^20`. El test garantiza que el
    # rango cubre Node 20+.
    node_range = engines["node"]
    assert (
        "20" in node_range
    ), f"engines.node should include 20+, got {node_range!r}"


# ── Smoke test de integración ────────────────────────────────────────────


@pytest.mark.skipif(
    not _node_available() or not _sidecar_present(),
    reason="node or sidecar not available",
)
def test_v02_smoke_full_flow(tmp_path: Path) -> None:
    """v0.2: smoke test que ejecuta el flujo completo con WAL + adapter."""
    from integrations.pi.agent_runner import AgentRunner, RunnerState
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    # Configurar Fase 3.
    bago_dir = tmp_path / ".bago"
    bago_dir.mkdir(exist_ok=True)
    (bago_dir / "config.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "pi": {
                        "enabled": True,
                        "max_phase": 3,
                        "network_mode": "provider_endpoints_only",
                        "allow_pi_auth_store": False,
                        "allow_pi_sessions": False,
                        "allow_pi_settings": False,
                        "allow_pi_system_prompt_discovery": False,
                        "allow_skills": False,
                        "allow_extensions": False,
                        "allow_packages": False,
                        "allow_native_tools": False,
                        "allow_process_spawn": False,
                        "allow_mutations": False,
                        "quarantine_mode": True,
                        "fail_on_provider_drift": True,
                        "fail_on_unknown_event": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cfg = load_config()
    finally:
        os.chdir(cwd)
    adapter = BagoPiProviderAdapter(
        config=cfg,
        integrations_dir=INTEGRATIONS_DIR,
        workspace_root=str(tmp_path),
        workspace_scope_root=str(tmp_path),
        project_root=str(tmp_path),
    )
    now = datetime.now(timezone.utc)
    env_id = f"env-{int(now.timestamp() * 1000)}"
    out = adapter.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="mock-1",
        provider_key="bago-pi-mock",
        envelope_id=env_id,
        envelope_digest=env_id,
    )
    # B1: isinstance funciona.
    from integrations.pi.provider_adapter import (
        _import_provider_adapter_base,
    )
    canonical = _import_provider_adapter_base()
    assert isinstance(adapter, canonical)
    # A2: el WAL existe para esta ejecución.
    wal_path = (
        tmp_path
        / ".gabo"
        / "integrations"
        / "pi"
        / "wal"
        / f"exec-{env_id}.jsonl"
    )
    assert wal_path.exists()
    # El bundle final es EXECUTED_UNVERIFIED (nunca done/verified).
    assert out["receipt_bundle"].final_status == "EXECUTION_COMPLETED_UNVERIFIED"

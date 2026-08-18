"""Fase 1 — tests de integración del `BagoPiProviderAdapter`.

Estos tests arrancan el sidecar Node real desde el adapter, capturan
el stream JSONL, validan la attestation y verifican que el resultado
cumple las invariantes de Fase 1.

Requiere:
    - node >= 20 en PATH
    - el sidecar compilado (o `.js` directo) en
      `backend/.bago/integrations/pi/sidecar/src/main.js`

Se salta automáticamente si node no está disponible.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
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


def _make_config(tmp_path: Path, *, enabled: bool, max_phase: int) -> dict:
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    bago_dir = config_dir / ".bago"
    bago_dir.mkdir(exist_ok=True)
    (bago_dir / "config.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "pi": {
                        "enabled": enabled,
                        "quarantine_mode": True,
                        "max_phase": max_phase,
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
                        "network_mode": "provider_endpoints_only",
                        "fail_on_provider_drift": True,
                        "fail_on_unknown_event": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return config_dir


def _request_envelope() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "envelope_id": f"env-{int(now.timestamp() * 1000)}",
        "envelope_digest": f"env-{int(now.timestamp() * 1000)}",
        "issued_at": now.isoformat(),
        "deadline": (now + timedelta(seconds=60)).isoformat(),
    }


pytestmark = pytest.mark.skipif(
    not _node_available() or not _sidecar_present(),
    reason="node or sidecar not available",
)


def test_adapter_is_not_configured_when_disabled(tmp_path: Path) -> None:
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config(tmp_path, enabled=False, max_phase=0)
    cwd = os.getcwd()
    try:
        os.chdir(config_root)
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
    assert adapter.is_configured() is False
    assert adapter.supports_tools() is False
    assert adapter.supports_streaming() is False
    health = adapter.health_check()
    assert health["ok"] is False


def test_adapter_rejects_streaming_and_tools_in_phase_1(tmp_path: Path) -> None:
    from integrations.pi.errors import CapabilityDenied, ToolNotAllowed
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config(tmp_path, enabled=True, max_phase=1)
    cwd = os.getcwd()
    try:
        os.chdir(config_root)
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
    with pytest.raises(ToolNotAllowed):
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            tools=[{"type": "function", "function": {"name": "read"}}],
            provider_key="bago-pi-mock",
        )
    with pytest.raises(CapabilityDenied):
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            stream=True,
            provider_key="bago-pi-mock",
        )


def test_adapter_chat_roundtrip_with_mock_sidecar(tmp_path: Path) -> None:
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config(tmp_path, enabled=True, max_phase=1)
    cwd = os.getcwd()
    try:
        os.chdir(config_root)
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
    env = _request_envelope()
    out = adapter.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="mock-1",
        system="you are bago",
        temperature=0.0,
        max_tokens=10,
        stream=False,
        tools=None,
        provider_key="bago-pi-mock",
        envelope_id=env["envelope_id"],
        envelope_digest=env["envelope_digest"],
    )
    assert out["provider"] == "bago-pi-mock"
    assert out["model"] == "mock-1"
    assert "mock-reply" in out["content"]
    assert out["finish_reason"] == "stop"
    assert out["attestation"]["result"] == "MATCH"
    # El receipt bundle está en el resultado.
    assert out["receipt_bundle"].final_status == "EXECUTION_COMPLETED_UNVERIFIED"
    # El bridge no expone "done"/"verified"/"certified".
    assert "done" not in out["receipt_bundle"].final_status.lower()
    assert "certified" not in out["receipt_bundle"].final_status.lower()


def test_adapter_does_not_modify_persistent_state(tmp_path: Path) -> None:
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config(tmp_path, enabled=True, max_phase=1)
    cwd = os.getcwd()
    try:
        os.chdir(config_root)
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
    before = {p.name for p in tmp_path.iterdir()}
    env = _request_envelope()
    adapter.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="mock-1",
        provider_key="bago-pi-mock",
        envelope_id=env["envelope_id"],
        envelope_digest=env["envelope_digest"],
    )
    after = {p.name for p in tmp_path.iterdir()}
    # No se crean artefactos persistentes en el workspace del proyecto.
    assert before == after


def test_adapter_rejects_phase_0_config() -> None:
    from integrations.pi.errors import CapabilityDenied
    from integrations.pi.provider_adapter import BagoPiProviderAdapter

    adapter = BagoPiProviderAdapter(
        config=None,
        integrations_dir=INTEGRATIONS_DIR,
    )
    # Carga el config por defecto (max_phase=0).
    assert adapter._config.max_phase == 0
    with pytest.raises(CapabilityDenied):
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            provider_key="bago-pi-mock",
        )


def test_adapter_rejects_max_phase_below_1() -> None:
    """Verifica que incluso con un Phase 0 config, no se ejecuta."""
    from integrations.pi.errors import CapabilityDenied
    from integrations.pi.provider_adapter import BagoPiProviderAdapter

    adapter = BagoPiProviderAdapter(
        config=None,
        integrations_dir=INTEGRATIONS_DIR,
    )
    with pytest.raises(CapabilityDenied):
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            provider_key="bago-pi-mock",
        )

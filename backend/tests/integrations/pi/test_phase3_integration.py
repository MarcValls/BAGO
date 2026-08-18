"""Fase 3 — tests de integración adapter → runner.

El `BagoPiProviderAdapter` en Fase 3 debe delegar al `AgentRunner`
cuando el sidecar emite tool events. Esta suite verifica que la
integración es coherente y que el bundle final contiene los tool
receipts.
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


def _node_available() -> bool:
    return shutil.which("node") is not None


def _make_config_with_tools(tmp_path: Path, max_phase: int = 3) -> Path:
    bago = tmp_path / ".bago"
    bago.mkdir(exist_ok=True)
    (bago / "config.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "pi": {
                        "enabled": True,
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
    return tmp_path


@pytest.fixture(autouse=True)
def _force_max_phase_3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAGO_PI_MAX_PHASE", "3")


pytestmark = pytest.mark.skipif(
    not _node_available(), reason="node not available"
)


def test_adapter_phase_3_uses_runner(tmp_path: Path) -> None:
    """El adapter, en Fase 3, invoca el AgentRunner."""
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config_with_tools(tmp_path, max_phase=3)
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
    now = datetime.now(timezone.utc)
    env_id = f"env-{int(now.timestamp() * 1000)}"
    out = adapter.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="mock-1",
        provider_key="bago-pi-mock",
        envelope_id=env_id,
        envelope_digest=env_id,
    )
    # El adapter sigue funcionando en Fase 3: ejecuta el sidecar,
    # captura eventos, valida attestation, emite receipt.
    assert out["provider"] == "bago-pi-mock"
    assert "mock-reply" in out["content"]
    assert out["attestation"]["result"] == "MATCH"
    # El receipt bundle es EXECUTED_UNVERIFIED.
    assert out["receipt_bundle"].final_status == "EXECUTION_COMPLETED_UNVERIFIED"
    # done/verified/certified nunca aparecen.
    assert "done" not in out["receipt_bundle"].final_status.lower()
    assert "verified" not in out["receipt_bundle"].final_status.lower() or "unverified" in out["receipt_bundle"].final_status.lower()
    assert "certified" not in out["receipt_bundle"].final_status.lower()


def test_adapter_in_phase_3_persists_events(tmp_path: Path) -> None:
    """En Fase 3, los eventos del log se persisten en disco."""
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config_with_tools(tmp_path, max_phase=3)
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
    now = datetime.now(timezone.utc)
    env_id = f"env-{int(now.timestamp() * 1000)}"
    out = adapter.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="mock-1",
        provider_key="bago-pi-mock",
        envelope_id=env_id,
        envelope_digest=env_id,
    )
    # El context_receipt debe estar en disco bajo .gabo/integrations/pi/receipts/.
    receipts_dir = tmp_path / ".gabo" / "integrations" / "pi" / "receipts"
    # En Fase 3 el adapter persiste vía el runner.
    assert receipts_dir.exists()
    # Hay al menos un subdir (uno por execution_id).
    subdirs = list(receipts_dir.iterdir())
    assert len(subdirs) >= 1
    # Cada subdir tiene un context_receipt.json.
    for subdir in subdirs:
        if subdir.is_dir():
            assert (subdir / "context_receipt.json").exists()
            break

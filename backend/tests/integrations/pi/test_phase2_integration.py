"""Fase 2 — integración end-to-end del tool flow a través del adapter.

El bridge:
    1. Levanta el sidecar Node.
    2. El sidecar emite un `tool_requested` (read de un archivo en scope).
    3. El bridge intercepta, ejecuta la tool, emite `tool_policy_decided`
       y `tool_result_attached` con `ToolReceipt`.
    4. El bundle final incluye los `tool_receipts` en el receipt canónico.

Requiere node >= 20 en PATH; se salta si no está.
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


def _node_available() -> bool:
    return shutil.which("node") is not None


def _make_config_with_tools(tmp_path: Path, max_phase: int = 2) -> Path:
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


pytestmark = pytest.mark.skipif(
    not _node_available(), reason="node not available"
)


def test_adapter_chat_emits_only_provider_events_in_phase_1(tmp_path: Path) -> None:
    """En Fase 1, el adapter no procesa tool events (no debería
    invocarse process_tool_events). El sidecar mock no emite tool
    requests por defecto. Verifica que la salida está limpia de tool
    events."""
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config_with_tools(tmp_path, max_phase=1)
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
    log = out["metadata"]["event_log"]
    # No hay tool events en Fase 1.
    assert log.by_type("tool_requested") == []
    assert log.by_type("tool_policy_decided") == []
    assert log.by_type("tool_result_attached") == []


def test_adapter_in_phase_1_rejects_tools_argument(tmp_path: Path) -> None:
    from integrations.pi.errors import ToolNotAllowed
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _make_config_with_tools(tmp_path, max_phase=1)
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
    )
    now = datetime.now(timezone.utc)
    env_id = f"env-{int(now.timestamp() * 1000)}"
    with pytest.raises(ToolNotAllowed):
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            provider_key="bago-pi-mock",
            tools=[{"type": "function", "function": {"name": "read"}}],
            envelope_id=env_id,
            envelope_digest=env_id,
        )


def test_tool_flow_does_not_modify_workspace(tmp_path: Path) -> None:
    """El tool flow (read) no debe crear ni modificar archivos en el
    workspace del proyecto."""
    from integrations.pi.contracts import (
        CapabilityClaims,
        make_event,
    )
    from integrations.pi.event_capture import EventLog
    from integrations.pi.tool_event_flow import process_tool_events

    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    before = {p.name for p in tmp_path.iterdir()}
    log = EventLog(execution_id="exec-1")
    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log.append(e1)
    e2 = make_event(
        execution_id="exec-1", sequence_number=2, event_id="tc-1",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-1", "tool": "read", "arguments": {"path": str(f)}},
        previous_event_hash=e1.event_hash,
    )
    log.append(e2)
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
    process_tool_events(
        log=log,
        claims=claims,
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=e2.event_hash,
    )
    after = {p.name for p in tmp_path.iterdir()}
    assert before == after


def test_tool_flow_output_appears_in_receipt(tmp_path: Path) -> None:
    """El output de la tool aparece en el `tool_result_attached`."""
    from integrations.pi.contracts import CapabilityClaims, make_event
    from integrations.pi.event_capture import EventLog
    from integrations.pi.tool_event_flow import process_tool_events

    f = tmp_path / "x.txt"
    f.write_text("hello world", encoding="utf-8")
    log = EventLog(execution_id="exec-1")
    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log.append(e1)
    e2 = make_event(
        execution_id="exec-1", sequence_number=2, event_id="tc-1",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-1", "tool": "read", "arguments": {"path": str(f)}},
        previous_event_hash=e1.event_hash,
    )
    log.append(e2)
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
    flow = process_tool_events(
        log=log,
        claims=claims,
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=e2.event_hash,
    )
    result_event = flow.new_events[1]
    assert result_event.event_type == "tool_result_attached"
    assert result_event.payload["output"] == "hello world"
    assert result_event.payload["status"] == "completed"
    assert result_event.payload["tool_receipt_id"] == "tc-1"

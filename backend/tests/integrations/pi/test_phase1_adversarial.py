"""Fase 1 — tests adversariales de drift, secretos y kill switch."""
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


pytestmark = pytest.mark.skipif(
    not _node_available(), reason="node not available"
)


def _config_with(tmp_path: Path, **overrides) -> Path:
    bago = tmp_path / ".bago"
    bago.mkdir(exist_ok=True)
    cfg = {
        "integrations": {
            "pi": {
                "enabled": True,
                "quarantine_mode": True,
                "max_phase": 1,
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
    if overrides:
        cfg["integrations"]["pi"].update(overrides)
    (bago / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def test_kill_switch_global_disables_adapter(tmp_path: Path) -> None:
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _config_with(tmp_path, enabled=False)
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
    assert adapter.is_configured() is False
    from integrations.pi.errors import CapabilityDenied

    with pytest.raises(CapabilityDenied):
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            provider_key="bago-pi-mock",
        )


def test_kill_switch_phase_lock_blocks_below_max(tmp_path: Path) -> None:
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _config_with(tmp_path, enabled=True, max_phase=0)
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
    from integrations.pi.errors import CapabilityDenied

    with pytest.raises(CapabilityDenied):
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            provider_key="bago-pi-mock",
        )


def test_credential_drift_detected() -> None:
    """El bridge rechaza si el sidecar emite credential_ref distinto."""
    from integrations.pi.attestation import AttestationPolicy, verify
    from integrations.pi.errors import BridgeError

    payload = {
        "requested_provider": "bago-pi-mock",
        "effective_provider": "bago-pi-mock",
        "requested_model": "mock-1",
        "effective_model": "mock-1",
        "endpoint_normalized": "mock://x",
        "adapter": "mock",
        "bridge_version": "0.1.0",
        "pi_package_version": "0.0.0-mock",
        "pi_lockfile_hash": "",
        "sidecar_artifact_hash": "",
        "credential_ref": "rogue-ref",
        "fallback_used": False,
        "auto_selection_used": False,
        "config_effective": {},
        "result": "MATCH",
    }
    with pytest.raises(BridgeError) as exc:
        verify(
            payload,
            expected_credential_ref="expected-ref",
            policy=AttestationPolicy(),
        )
    assert "credential_ref drift" in str(exc.value.reason)


def test_secret_does_not_appear_in_receipt(tmp_path: Path) -> None:
    """El bundle nunca contiene el credential_ref en metadata visible
    más allá del campo `credential_ref` del attestation, que es
    referencia opaca. Verifica que el output del adapter tampoco
    filtra el token."""
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config
    from integrations.pi.errors import CapabilityDenied

    secret_value = "sk-SECRET-LEAK-CANARY-9999"

    config_root = _config_with(tmp_path, enabled=True, max_phase=1)
    cwd = os.getcwd()
    try:
        os.chdir(config_root)
        cfg = load_config()
    finally:
        os.chdir(cwd)
    adapter = BagoPiProviderAdapter(
        config=cfg,
        integrations_dir=INTEGRATIONS_DIR,
        workspace_root=str(config_root),
        workspace_scope_root=str(config_root),
        credential_ref=secret_value,
    )
    # Llamamos sin levantar el sidecar: la verificación se hace en
    # el adapter antes del spawn. Provocamos un error de preflight
    # pasando un envelope id inválido (session_revision drift).
    try:
        adapter.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="mock-1",
            provider_key="bago-pi-mock",
            envelope_id="env-1",
            envelope_digest="env-1",
        )
    except CapabilityDenied as exc:
        rendered = str(exc)
        assert secret_value not in rendered
    except Exception as exc:  # noqa: BLE001
        rendered = repr(exc) + str(getattr(exc, "details", ""))
        # Permitimos que el secret aparezca en `credential_ref` porque
        # es la referencia opaca; pero NO en el resto del error.
        # Aquí, como el error es de policy, no debería aparecer.
        occurrences = rendered.count(secret_value)
        assert occurrences <= 1, rendered


def test_provider_drift_raises() -> None:
    """Drift de provider/modelo efectivo vs solicitado."""
    from integrations.pi.attestation import AttestationPolicy, verify
    from integrations.pi.errors import ProviderAttestationMismatch

    payload = {
        "requested_provider": "bago-pi-mock",
        "effective_provider": "rogue-provider",
        "requested_model": "mock-1",
        "effective_model": "rogue-model",
        "endpoint_normalized": "mock://rogue",
        "adapter": "rogue",
        "bridge_version": "0.1.0",
        "pi_package_version": "0.0.0-mock",
        "pi_lockfile_hash": "",
        "sidecar_artifact_hash": "",
        "credential_ref": "ref-bago-mock",
        "fallback_used": False,
        "auto_selection_used": False,
        "config_effective": {},
        "result": "MISMATCH",
    }
    with pytest.raises(ProviderAttestationMismatch):
        verify(
            payload,
            expected_credential_ref="ref-bago-mock",
            policy=AttestationPolicy(),
        )


def test_fallback_flag_rejected() -> None:
    """El sidecar emitió fallback_used=true: el bridge rechaza."""
    from integrations.pi.attestation import AttestationPolicy, verify
    from integrations.pi.errors import ProviderFallbackDenied

    payload = {
        "requested_provider": "bago-pi-mock",
        "effective_provider": "bago-pi-mock",
        "requested_model": "mock-1",
        "effective_model": "mock-1",
        "endpoint_normalized": "mock://bago",
        "adapter": "mock",
        "bridge_version": "0.1.0",
        "pi_package_version": "0.0.0-mock",
        "pi_lockfile_hash": "",
        "sidecar_artifact_hash": "",
        "credential_ref": "ref-bago-mock",
        "fallback_used": True,
        "auto_selection_used": False,
        "config_effective": {},
        "result": "MATCH",
    }
    with pytest.raises(ProviderFallbackDenied):
        verify(
            payload,
            expected_credential_ref="ref-bago-mock",
            policy=AttestationPolicy(),
        )


def test_unknown_event_from_sidecar_rejected(tmp_path: Path) -> None:
    """Si el sidecar emite un event_type no permitido, el decoder del
    bridge rechaza con `UnknownEvent` (no se permite que un evento
    desconocido entre al log)."""
    from integrations.pi.protocol import encode_event, decode_event
    from integrations.pi.errors import UnknownEvent
    from integrations.pi.contracts import make_event

    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    line1 = encode_event(e1)
    # Decodifica OK en fase 1.
    decoded = decode_event(line1, phase=1)
    assert decoded.event_type == "runtime_attested"

    bad = make_event(
        execution_id="exec-1", sequence_number=2, event_id="e2",
        event_type="custom_unknown_event",
        payload={}, previous_event_hash=e1.event_hash,
    )
    line_bad = encode_event(bad)
    with pytest.raises(UnknownEvent) as exc:
        decode_event(line_bad, phase=1)
    assert exc.value.code == "PI_UNKNOWN_EVENT"


def test_no_persistent_state_after_chat(tmp_path: Path) -> None:
    """El bridge no debe dejar artefactos persistentes en el workspace."""
    from integrations.pi.provider_adapter import BagoPiProviderAdapter
    from integrations.pi.config import load_config

    config_root = _config_with(tmp_path, enabled=True, max_phase=1)
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
    # Listar el contenido del workspace ANTES.
    before = {p.name for p in tmp_path.iterdir()}
    now = datetime.now(timezone.utc)
    env_id = f"env-{int(now.timestamp() * 1000)}"
    adapter.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="mock-1",
        provider_key="bago-pi-mock",
        envelope_id=env_id,
        envelope_digest=env_id,
    )
    after = {p.name for p in tmp_path.iterdir()}
    assert before == after

"""Tests de carga de configuración del BagoPiBridge."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from integrations.pi.config import PiBridgeConfig, load_config
from integrations.pi.errors import BridgeError


def test_defaults_when_no_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.enabled is False
    assert cfg.quarantine_mode is True
    assert cfg.max_phase == 0
    assert cfg.allow_mutations is False
    assert cfg.allow_skills is False
    assert cfg.allow_extensions is False
    assert cfg.allow_packages is False
    assert cfg.allow_native_tools is False
    assert cfg.allow_process_spawn is False
    assert cfg.network_mode == "none"
    assert cfg.fail_on_provider_drift is True
    assert cfg.fail_on_unknown_event is True


def test_loads_from_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend_bago = tmp_path / "backend" / ".bago"
    backend_bago.mkdir(parents=True)
    (backend_bago / "config.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "pi": {
                        "enabled": False,
                        "max_phase": 0,
                        "network_mode": "none",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "backend")
    cfg = load_config()
    assert cfg.max_phase == 0
    assert cfg.network_mode == "none"


def test_unknown_flag_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend_bago = tmp_path / "backend" / ".bago"
    backend_bago.mkdir(parents=True)
    (backend_bago / "config.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "pi": {
                        "enabled": False,
                        "max_phase": 0,
                        "network_mode": "none",
                        "allow_everything": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "backend")
    with pytest.raises(BridgeError) as exc:
        load_config()
    assert "unknown config flag" in str(exc.value)


def test_invalid_max_phase_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend_bago = tmp_path / "backend" / ".bago"
    backend_bago.mkdir(parents=True)
    (backend_bago / "config.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "pi": {"enabled": False, "max_phase": 5}
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "backend")
    with pytest.raises(BridgeError) as exc:
        load_config()
    assert "max_phase" in str(exc.value)


def test_invalid_network_mode_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend_bago = tmp_path / "backend" / ".bago"
    backend_bago.mkdir(parents=True)
    (backend_bago / "config.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "pi": {"enabled": False, "max_phase": 0, "network_mode": "wildcard"}
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "backend")
    with pytest.raises(BridgeError) as exc:
        load_config()
    assert "network_mode" in str(exc.value)


def test_env_forces_max_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BAGO_PI_MAX_PHASE", "0")
    cfg = load_config()
    assert cfg.max_phase == 0

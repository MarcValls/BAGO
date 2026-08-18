"""Tests de diagnostics.snapshot()."""
from __future__ import annotations

from pathlib import Path

import pytest

from integrations.pi.config import load_config
from integrations.pi.diagnostics import snapshot


def test_snapshot_quarantined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    status = snapshot(cfg, integrations_dir=tmp_path)
    assert status.protocol_version == "0.1.0"
    assert status.quarantine_phase == 0
    assert status.quarantined is True
    assert status.capabilities["infer"] is False
    assert status.capabilities["read_only_tools"] is False
    assert status.capabilities["agent_runner"] is False
    assert status.capabilities["mutations"] is False
    assert status.capabilities["skills"] is False
    assert status.capabilities["extensions"] is False
    assert status.capabilities["packages"] is False
    assert status.capabilities["process_spawn"] is False
    assert status.kill_switch["global"] is True
    assert status.kill_switch["phase_lock"] is True


def test_snapshot_reads_lockfile_hash(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar"
    sidecar.mkdir()
    (sidecar / "package-lock.json").write_text("{}")
    cfg = load_config()
    status = snapshot(cfg, integrations_dir=tmp_path)
    assert status.runtime["lockfile_hash"]


def test_snapshot_no_lockfile(tmp_path: Path) -> None:
    cfg = load_config()
    status = snapshot(cfg, integrations_dir=tmp_path)
    assert status.runtime["lockfile_hash"] == ""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path[:0] = [str(BACKEND / ".bago" / "core"), str(BACKEND)]

import msix_bootstrap


def _authority(tmp_path: Path) -> tuple[Path, str]:
    authority = tmp_path / "authority"
    core = authority / "core"
    core.mkdir(parents=True)
    manifest = {"schema": "bago.release-manifest.v1"}
    manifest_path = tmp_path / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return authority, hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def test_manifest_digest_mismatch_fails_before_import_or_state_write(tmp_path: Path):
    authority, _ = _authority(tmp_path)
    with pytest.raises(RuntimeError, match="identity mismatch"):
        msix_bootstrap.verify_loaded_authority(str(authority), "0" * 64)
    assert not (tmp_path / "state").exists()


def test_invalid_release_manifest_schema_is_rejected(tmp_path: Path):
    authority, digest = _authority(tmp_path)
    (tmp_path / "release-manifest.json").write_text(json.dumps({"schema": "unknown"}), encoding="utf-8")
    digest = hashlib.sha256((tmp_path / "release-manifest.json").read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match="Unsupported"):
        msix_bootstrap.verify_loaded_authority(str(authority), digest)


def test_canonical_session_uses_state_root_and_disables_mutable_mirror(tmp_path: Path, monkeypatch):
    if os.name != "nt":
        pytest.skip("Windows base-path validation is required for this runtime smoke")
    state = tmp_path / "state"
    monkeypatch.setenv("BAGO_STATE_ROOT", str(state))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAGO_SESSION_MIRROR", "0")
    session_id = msix_bootstrap.create_bootstrap_session(str(state))
    assert session_id
    assert msix_bootstrap._SESSION_MANAGER.workspace_mirror_ready is False
    assert (state / "sessions" / session_id / "meta.json").is_file()
    assert not (tmp_path / "BAGO" / "workspace").exists()

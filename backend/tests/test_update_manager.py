from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest


API_DIR = Path(__file__).resolve().parents[1] / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import update_manager as updater


def _bundle(version: str = "4.8.3") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("compiled/backend/release_version.txt", version)
        archive.writestr("compiled/backend/bago_core/launcher.py", "print('ok')")
        archive.writestr("compiled/electron-viewer/BAGO.exe", b"MZfixture")
    return output.getvalue()


def _release(payload: bytes, *, digest: str | None = None) -> dict:
    sha = digest or hashlib.sha256(payload).hexdigest()
    return {
        "tag_name": "v4.8.3",
        "name": "BAGO 4.8.3",
        "body": "Actualización de prueba",
        "published_at": "2026-08-10T00:00:00Z",
        "html_url": "https://github.com/MarcValls/BAGO/releases/tag/v4.8.3",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "bago-4.8.3-backend.zip",
                "browser_download_url": "https://github.com/example/backend.zip",
                "size": 10,
                "digest": f"sha256:{sha}",
            },
            {
                "name": "bago-4.8.3-distribution.zip",
                "browser_download_url": "http://127.0.0.1/distribution.zip",
                "size": len(payload),
                "digest": f"sha256:{sha}",
            },
        ],
    }


class _Response(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    install_root = tmp_path / "BAGO"
    (install_root / "backend").mkdir(parents=True)
    (install_root / "electron-viewer").mkdir()
    (install_root / "electron-viewer" / "BAGO.exe").write_bytes(b"MZold")
    monkeypatch.setenv("BAGO_UPDATE_ROOT", str(tmp_path / "updates"))
    monkeypatch.setenv("BAGO_UPDATE_ALLOW_INSECURE_LOCAL", "1")
    monkeypatch.setattr(updater, "_installation", lambda: {
        "ready": True,
        "root": str(install_root),
        "viewer": str(install_root / "electron-viewer" / "BAGO.exe"),
        "reason": "",
    })
    updater._state = updater._default_state()
    yield install_root


def _wait_for(status_name: str, timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = updater.status()
        if state.get("status") == status_name:
            return state
        time.sleep(0.02)
    raise AssertionError(f"Estado {status_name} no alcanzado: {updater.status()}")


def test_check_uses_latest_stable_distribution_asset(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _bundle()
    monkeypatch.setattr(updater, "_request_json", lambda _url: _release(payload))

    result = updater.check()

    assert result["available"] is True
    assert result["latest"] == "v4.8.3"
    assert result["asset"]["name"] == "bago-4.8.3-distribution.zip"
    assert result["installation"]["root"] == str(isolated)


def test_check_uses_cached_release_when_github_is_temporarily_offline(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _bundle()
    monkeypatch.setattr(updater, "_request_json", lambda _url: _release(payload))
    assert updater.check()["latest"] == "v4.8.3"
    monkeypatch.setattr(updater, "_request_json", lambda _url: (_ for _ in ()).throw(OSError("dns unavailable")))

    result = updater.check()

    assert result["latest"] == "v4.8.3"
    assert result["offline"] is True
    assert "última comprobación" in result["warning"]
    assert "error" not in result


def test_prepare_download_verifies_sha_and_payload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _bundle()
    monkeypatch.setattr(updater, "_request_json", lambda _url: _release(payload))
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *_args, **_kwargs: _Response(payload))

    started = updater.start_update("v4.8.3")
    state = _wait_for("ready")

    assert started["ok"] is True
    assert state["percent"] == 100
    assert Path(state["detail"]["bundle_path"]).is_file()
    assert state["detail"]["sha256"] == hashlib.sha256(payload).hexdigest()


def test_prepare_rejects_changed_payload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _bundle()
    wrong_digest = "0" * 64
    monkeypatch.setattr(updater, "_request_json", lambda _url: _release(payload, digest=wrong_digest))
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *_args, **_kwargs: _Response(payload))

    assert updater.start_update("v4.8.3")["ok"] is True
    state = _wait_for("error")

    assert "SHA-256 no coincide" in state["error"]
    assert not list((Path(updater._update_root())).glob("*.part"))


def test_apply_launches_external_helper_for_active_installation(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = Path(updater._update_root()) / "verified.zip"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_bytes(b"verified")
    captured: dict = {}

    class _Process:
        pass

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Process()

    monkeypatch.setattr(updater.subprocess, "Popen", fake_popen)
    updater._set_state(
        status="ready",
        latest="v4.8.3",
        detail={"bundle_path": str(bundle), "sha256": "a" * 64},
    )

    result = updater.apply_update()

    assert result["ok"] is True
    assert result["status"] == "applying"
    assert "-InstallRoot" in captured["command"]
    assert str(isolated) in captured["command"]


def test_apply_rejects_unprepared_update_with_actionable_error(isolated: Path) -> None:
    updater._set_state(status="idle", error="")

    result = updater.apply_update()

    assert result["ok"] is False
    assert result["error"] == "La actualización aún no está descargada y verificada"


@pytest.mark.skipif(os.name != "nt", reason="El helper de aplicación es específico de Windows")
def test_external_helper_swaps_components_and_keeps_state(tmp_path: Path) -> None:
    install_root = tmp_path / "BAGO"
    backend = install_root / "backend"
    viewer = install_root / "electron-viewer"
    (backend / "bago_core").mkdir(parents=True)
    viewer.mkdir()
    (backend / "release_version.txt").write_text("4.8.2", encoding="utf-8")
    (backend / "bago_core" / "launcher.py").write_text("print('old')", encoding="utf-8")
    (viewer / "BAGO.exe").write_bytes(b"MZold")
    state_path = install_root / "state" / "updates" / "release-update.json"
    bundle = tmp_path / "release.zip"
    payload = _bundle()
    bundle.write_bytes(payload)
    helper = API_DIR / "apply_release_update.ps1"

    subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(helper),
        "-BundlePath", str(bundle),
        "-InstallRoot", str(install_root),
        "-StatePath", str(state_path),
        "-ExpectedVersion", "v4.8.3",
        "-ExpectedSha256", hashlib.sha256(payload).hexdigest(),
    ], check=True, timeout=30)

    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["status"] == "completed"
    assert (backend / "release_version.txt").read_text(encoding="utf-8").strip() == "4.8.3"
    assert (viewer / "BAGO.exe").read_bytes() == b"MZfixture"
    assert list((install_root / "backups" / "updates").glob("*/backend/release_version.txt"))

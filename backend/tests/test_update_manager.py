from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import pytest


API_DIR = Path(__file__).resolve().parents[1] / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import update_manager as updater


def _bundle(version: str = "4.8.5") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("compiled/backend/release_version.txt", version)
        archive.writestr("compiled/backend/bago_core/launcher.py", "print('ok')")
        archive.writestr("compiled/electron-viewer/BAGO.exe", b"MZfixture")
    return output.getvalue()


def _write_helper_ticket(
    helper: Path,
    bundle: Path,
    install_root: Path,
    state_path: Path,
    expected_version: str,
    expected_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    backend_pid: int = 0,
) -> tuple[Path, str, str]:
    import authorization_boundary as auth
    from execution_adapters.system_update import SystemUpdateApplyEffectAdapter
    from execution_request import build_execution_request

    monkeypatch.setenv("BAGO_STATE_ROOT", str(bundle.parent / "user-state"))
    ledger_path = auth.authorization_ledger_path().resolve()
    target = {
        "bundle_path": str(bundle.resolve()),
        "bundle_sha256": expected_sha256.lower(),
        "helper_path": str(helper.resolve()),
        "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        "authorization_ledger_path": str(ledger_path),
        "install_root": str(install_root.resolve()),
        "state_path": str(state_path.resolve()),
        "expected_version": expected_version,
        "backend_pid": str(backend_pid),
        "restart": False,
    }
    request = build_execution_request(
        effect_id="system.update.apply",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="test-session",
        source_surface="api.release.apply",
        target=target,
        arguments={},
        scope="system",
    )
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="test-update-helper")
    approved = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="test-update-helper",
        session_id=request.session_id,
        channel="ui-react",
    )
    authorization = boundary.consume_permit(
        permit_token=approved["permit"]["token"], request=request,
    )
    ticket, nonce, permit_id = SystemUpdateApplyEffectAdapter._write_helper_ticket(
        request, authorization, bundle,
    )
    return ticket, nonce, permit_id


def _release(payload: bytes, *, digest: str | None = None) -> dict:
    sha = digest or hashlib.sha256(payload).hexdigest()
    return {
        "tag_name": "v4.8.5",
        "name": "BAGO 4.8.5",
        "body": "Actualización de prueba",
        "published_at": "2026-08-10T00:00:00Z",
        "html_url": "https://github.com/MarcValls/BAGO/releases/tag/v4.8.5",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "bago-4.8.5-backend.zip",
                "browser_download_url": "https://github.com/example/backend.zip",
                "size": 10,
                "digest": f"sha256:{sha}",
            },
            {
                "name": "bago-4.8.5-distribution.zip",
                "browser_download_url": "https://github.com/MarcValls/BAGO/releases/download/v4.8.5/distribution.zip",
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


class _FixtureOpener:
    def __init__(self, payload: bytes):
        self._payload = payload

    def open(self, *_args, **_kwargs):
        return _Response(self._payload)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    install_root = tmp_path / "BAGO"
    (install_root / "backend").mkdir(parents=True)
    (install_root / "electron-viewer").mkdir()
    (install_root / "electron-viewer" / "BAGO.exe").write_bytes(b"MZold")
    monkeypatch.setenv("BAGO_UPDATE_ROOT", str(tmp_path / "updates"))
    monkeypatch.setattr(updater, "_installation", lambda: {
        "ready": True,
        "root": str(install_root),
        "viewer": str(install_root / "electron-viewer" / "BAGO.exe"),
        "reason": "",
    })
    monkeypatch.setattr(updater, "_current", lambda: "4.8.3")
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
    assert result["latest"] == "v4.8.5"
    assert result["asset"]["name"] == "bago-4.8.5-distribution.zip"
    assert result["installation"]["root"] == str(isolated)


def test_request_json_uses_release_network_policy(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    payload = json.dumps({"tag_name": "v4.8.5", "assets": []}).encode("utf-8")

    def fake_gateway_urlopen(request, *, timeout, network_class):
        captured.update({"url": request.full_url, "timeout": timeout, "network_class": network_class})
        return _Response(payload)

    monkeypatch.setattr(updater, "gateway_urlopen", fake_gateway_urlopen)

    result = updater._request_json(updater.REPO_API)

    assert result["tag_name"] == "v4.8.5"
    assert captured == {
        "url": updater.REPO_API,
        "timeout": 20,
        "network_class": "release_metadata",
    }


def test_release_download_blocks_unapproved_url_before_creating_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "release-cache"
    monkeypatch.setattr(updater, "_update_root", lambda: cache)
    from bago_core.server_effects import download_release_bundle

    with pytest.raises(Exception) as blocked:
        download_release_bundle(
            url="https://evil.example/payload.zip",
            sha256="a" * 64,
            size=10,
            filename="bago-v4.8.5-distribution.zip",
        )

    assert blocked.value.code == "network_read_release_host_blocked"
    assert not cache.exists()


def test_check_uses_cached_release_when_github_is_temporarily_offline(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _bundle()
    monkeypatch.setattr(updater, "_request_json", lambda _url: _release(payload))
    assert updater.check()["latest"] == "v4.8.5"
    monkeypatch.setattr(updater, "_request_json", lambda _url: (_ for _ in ()).throw(OSError("dns unavailable")))

    result = updater.check()

    assert result["latest"] == "v4.8.5"
    assert result["offline"] is True
    assert "última comprobación" in result["warning"]
    assert "error" not in result


def test_prepare_download_verifies_sha_and_payload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _bundle()
    monkeypatch.setattr(updater, "_request_json", lambda _url: _release(payload))
    monkeypatch.setattr(updater.urllib.request, "build_opener", lambda *_args, **_kwargs: _FixtureOpener(payload))

    started = updater.start_update("v4.8.5")
    state = _wait_for("ready")

    assert started["ok"] is True
    assert state["percent"] == 100
    assert Path(state["detail"]["bundle_path"]).is_file()
    assert state["detail"]["sha256"] == hashlib.sha256(payload).hexdigest()


def test_prepare_rejects_changed_payload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _bundle()
    wrong_digest = "0" * 64
    monkeypatch.setattr(updater, "_request_json", lambda _url: _release(payload, digest=wrong_digest))
    monkeypatch.setattr(updater.urllib.request, "build_opener", lambda *_args, **_kwargs: _FixtureOpener(payload))

    assert updater.start_update("v4.8.5")["ok"] is True
    state = _wait_for("error")

    assert "SHA-256 no coincide" in state["error"]
    assert not list((Path(updater._update_root())).glob("*.part"))


def test_start_update_blocks_parallel_release_discovery(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    results: list[dict] = []

    def slow_find(_tag: str = "") -> dict:
        entered.set()
        assert release.wait(timeout=3)
        return {
            "available": False,
            "current": "4.8.3",
            "latest": "v4.8.5",
            "installation": updater._installation(),
            "message": "BAGO ya está actualizado",
        }

    monkeypatch.setattr(updater, "_find_release", slow_find)

    worker = threading.Thread(target=lambda: results.append(updater.start_update("v4.8.5")))
    worker.start()
    assert entered.wait(timeout=3)

    concurrent = updater.start_update("v4.8.5")

    release.set()
    worker.join(timeout=3)

    assert concurrent["ok"] is False
    assert concurrent["error"] == "Ya hay una actualización en curso"
    assert results and results[0]["ok"] is False
    assert updater.status()["status"] == "idle"


def test_apply_launches_external_helper_only_through_authorized_gateway(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import authorization_boundary as auth
    from execution_gateway import ExecutionContext, ExecutionGateway
    from execution_request import build_execution_request

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

    import execution_adapters.system_update as system_update
    import update_manager as adapter_updater
    monkeypatch.setattr(system_update.subprocess, "Popen", fake_popen)
    updater._set_state(
        status="ready",
        latest="v4.8.5",
        detail={"bundle_path": str(bundle), "sha256": hashlib.sha256(b"verified").hexdigest()},
    )
    monkeypatch.setattr(adapter_updater, "_installation", lambda: {
        "ready": True, "root": str(isolated), "viewer": str(isolated / "electron-viewer" / "BAGO.exe"), "reason": "",
    })
    monkeypatch.setattr(auth, "state_root", lambda: Path(updater._update_root()) / "auth")
    descriptor = updater.update_apply_descriptor()
    class Manager:
        session_id = "release-session"
    manager = Manager()
    request = build_execution_request(
        effect_id="system.update.apply", actor_kind="user",
        principal_id="interactive-local-user", session_id=manager.session_id,
        source_surface="test.release.apply", target=descriptor,
        arguments={}, scope="system",
    )
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="release-apply-test")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="release-apply-test",
        session_id=request.session_id, channel="ui-react",
    )["permit"]
    result, _ = ExecutionGateway(boundary).execute(
        permit_token=permit["token"], request=request, context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is True
    assert result["status"] == "applying"
    assert "-InstallRoot" in captured["command"]
    assert str(isolated) in captured["command"]
    assert captured["command"][captured["command"].index("-AuthorizationLedgerPath") + 1] == request.target["authorization_ledger_path"]
    ticket_arg = captured["command"][captured["command"].index("-AuthorizationTicketPath") + 1]
    ticket = json.loads(Path(ticket_arg).read_text(encoding="utf-8"))
    assert ticket["effect_id"] == "system.update.apply"
    assert ticket["operation_fingerprint"] == request.fingerprint
    assert ticket["target"] == request.target


def test_apply_rejects_unprepared_update_with_actionable_error(isolated: Path) -> None:
    updater._set_state(status="idle", error="")

    with pytest.raises(RuntimeError, match="aún no está descargada y verificada"):
        updater.update_apply_descriptor()


def test_external_helper_persists_error_state_when_preflight_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_root = tmp_path / "invalid-install"
    install_root.mkdir()
    state_path = install_root / "state" / "updates" / "release-update.json"
    bundle = tmp_path / "release.zip"
    bundle.write_bytes(b"placeholder")
    helper = API_DIR / "apply_release_update.ps1"
    ticket, nonce, permit_id = _write_helper_ticket(
        helper, bundle, install_root, state_path, "v4.8.5", "0" * 64, monkeypatch,
    )

    completed = subprocess.run([
        "pwsh", "-NoProfile",
        "-File", str(helper),
        "-BundlePath", str(bundle),
        "-InstallRoot", str(install_root),
        "-StatePath", str(state_path),
        "-ExpectedVersion", "v4.8.5",
        "-ExpectedSha256", "0" * 64,
        "-AuthorizationLedgerPath", str(bundle.parent / "user-state" / "authorization" / "ledger.json"),
        "-AuthorizationTicketPath", str(ticket),
        "-AuthorizationTicketNonce", nonce,
        "-PermitId", permit_id,
    ], check=False, timeout=30, capture_output=True, text=True)

    assert completed.returncode != 0
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["status"] == "error"
    assert "Destino de actualización inseguro" in state["error"]


def test_external_helper_direct_invocation_blocks_before_any_effect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_root = tmp_path / "BAGO"
    install_root.mkdir()
    state_path = install_root / "state" / "updates" / "release-update.json"
    bundle = tmp_path / "release.zip"
    bundle.write_bytes(b"placeholder")
    helper = API_DIR / "apply_release_update.ps1"
    ticket = bundle.parent / ".apply-forged-permit.json"
    monkeypatch.setenv("BAGO_STATE_ROOT", str(tmp_path / "isolated-state"))
    ledger_path = tmp_path / "isolated-state" / "authorization" / "ledger.json"
    ticket.write_text(json.dumps({
        "schema": "bago.system-update-helper-ticket.v1",
        "nonce": "a" * 32,
        "permit_id": "forged-permit",
        "operation_fingerprint": "b" * 64,
        "effect_id": "system.update.apply",
        "session_id": "forged-session",
        "target": {
            "authorization_ledger_path": str(ledger_path),
            "bundle_path": str(bundle.resolve()),
            "bundle_sha256": "0" * 64,
            "install_root": str(install_root.resolve()),
            "state_path": str(state_path.resolve()),
            "expected_version": "v4.8.5",
            "backend_pid": "0",
            "restart": False,
            "helper_path": str(helper.resolve()),
            "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        },
    }), encoding="utf-8")

    completed = subprocess.run([
        "pwsh", "-NoProfile",
        "-File", str(helper),
        "-BundlePath", str(bundle),
        "-InstallRoot", str(install_root),
        "-StatePath", str(state_path),
        "-ExpectedVersion", "v4.8.5",
        "-ExpectedSha256", "0" * 64,
        "-AuthorizationLedgerPath", str(ledger_path),
        "-AuthorizationTicketPath", str(ticket),
        "-AuthorizationTicketNonce", "a" * 32,
        "-PermitId", "forged-permit",
    ], check=False, timeout=30, capture_output=True, text=True)

    assert completed.returncode != 0
    assert bundle.read_bytes() == b"placeholder"
    assert not state_path.exists()
    assert not (install_root / "backups").exists()


def test_external_helper_rejects_ticket_for_changed_target_before_effects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    digest = hashlib.sha256(payload).hexdigest()
    ticket, nonce, permit_id = _write_helper_ticket(
        helper, bundle, install_root, state_path, "v4.8.5", digest, monkeypatch,
    )
    ticket_data = json.loads(ticket.read_text(encoding="utf-8"))
    ticket_data["target"]["install_root"] = str((tmp_path / "other").resolve())
    ticket.write_text(json.dumps(ticket_data), encoding="utf-8")

    completed = subprocess.run([
        "pwsh", "-NoProfile",
        "-File", str(helper),
        "-BundlePath", str(bundle),
        "-InstallRoot", str(install_root),
        "-StatePath", str(state_path),
        "-ExpectedVersion", "v4.8.5",
        "-ExpectedSha256", digest,
        "-AuthorizationLedgerPath", str(bundle.parent / "user-state" / "authorization" / "ledger.json"),
        "-AuthorizationTicketPath", str(ticket),
        "-AuthorizationTicketNonce", nonce,
        "-PermitId", permit_id,
    ], check=False, timeout=30, capture_output=True, text=True)

    assert completed.returncode != 0
    assert bundle.read_bytes() == payload
    assert not state_path.exists()
    assert not (install_root / "backups").exists()


@pytest.mark.skipif(os.name != "nt", reason="El helper de aplicación es específico de Windows")
def test_external_helper_swaps_components_and_keeps_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    ticket, nonce, permit_id = _write_helper_ticket(
        helper, bundle, install_root, state_path, "v4.8.5", expected_sha256, monkeypatch,
    )

    subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(helper),
        "-BundlePath", str(bundle),
        "-InstallRoot", str(install_root),
        "-StatePath", str(state_path),
        "-ExpectedVersion", "v4.8.5",
        "-ExpectedSha256", expected_sha256,
        "-AuthorizationLedgerPath", str(bundle.parent / "user-state" / "authorization" / "ledger.json"),
        "-AuthorizationTicketPath", str(ticket),
        "-AuthorizationTicketNonce", nonce,
        "-PermitId", permit_id,
    ], check=True, timeout=30)

    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["status"] == "completed"
    assert (backend / "release_version.txt").read_text(encoding="utf-8").strip() == "4.8.5"
    assert (viewer / "BAGO.exe").read_bytes() == b"MZfixture"
    assert list((install_root / "backups" / "updates").glob("*/backend/release_version.txt"))

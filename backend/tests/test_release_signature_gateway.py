from __future__ import annotations

import io
import json
from types import SimpleNamespace
import zipfile

import pytest

from execution_gateway import ExecutionGateway, ExecutionGatewayError, ExecutionContext
from execution_request import build_execution_request
from execution_adapters.release_signature import ReleaseSignatureEffectAdapter
from execution_adapters.release_stage import ReleaseBundleStageEffectAdapter
from api_dispatch import resolve_post


def _request(signature: str, bundle: str):
    return build_execution_request(
        effect_id="release.signature.verify",
        actor_kind="server",
        principal_id="bago-electron-release-manager",
        session_id="release-job-manager",
        source_surface="server.electron.release_job.signature",
        target={"signature_path": signature, "bundle_path": bundle},
        arguments={},
        scope="system",
    )


def test_release_signature_is_gateway_owned_and_returns_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    signature = cache / "bundle.zip.sig"
    bundle = cache / "bundle.zip"
    signature.write_text("signature")
    bundle.write_bytes(b"PK\x03\x04")
    calls = []
    monkeypatch.setattr("execution_adapters.release_signature.shutil.which", lambda name: "gpg.exe")
    monkeypatch.setattr(
        "execution_adapters.release_signature.subprocess.run",
        lambda argv, **kwargs: calls.append((argv, kwargs)) or SimpleNamespace(returncode=0, stderr=""),
    )

    result, authorization = ExecutionGateway().execute_server_owned(
        request=_request(str(signature), str(bundle)), context=ExecutionContext()
    )

    assert result["ok"] is True
    assert result["effect_id"] == "release.signature.verify"
    assert result["receipt_id"].startswith("release-signature:")
    assert authorization["kind"] == "server_policy"
    assert len(calls) == 1
    assert calls[0][0][1:] == ["--batch", "--verify", str(signature), str(bundle)]
    assert calls[0][1]["shell"] is False


@pytest.mark.parametrize("escape", ["outside", "symlink"])
def test_release_signature_invalid_paths_block_before_process(tmp_path, monkeypatch, escape):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    bundle = cache / "bundle.zip"
    bundle.write_bytes(b"PK\x03\x04")
    if escape == "outside":
        signature = tmp_path / "outside.sig"
        signature.write_text("signature")
    else:
        outside = tmp_path / "outside.sig"
        outside.write_text("signature")
        signature = cache / "linked.sig"
        signature.symlink_to(outside)
    calls = []
    monkeypatch.setattr("execution_adapters.release_signature.shutil.which", lambda name: "gpg.exe")
    monkeypatch.setattr(
        "execution_adapters.release_signature.subprocess.run",
        lambda *args, **kwargs: calls.append(args),
    )

    with pytest.raises(ExecutionGatewayError):
        ExecutionGateway().execute_server_owned(
            request=_request(str(signature), str(bundle)), context=ExecutionContext()
        )
    assert calls == []


def test_signature_adapter_rejects_direct_non_gateway_call():
    request = _request("C:/invalid.sig", "C:/invalid.zip")
    with pytest.raises(ExecutionGatewayError) as exc:
        ReleaseSignatureEffectAdapter().execute(request, ExecutionContext())
    assert exc.value.code == "release_signature_authorization_required"


def _stage_request(bundle: str, job_id: str = "job-1"):
    return build_execution_request(
        effect_id="release.bundle.stage",
        actor_kind="server",
        principal_id="bago-electron-release-manager",
        session_id="release-job-manager",
        source_surface="server.electron.release_job.stage",
        target={"job_id": job_id, "bundle_path": bundle},
        arguments={},
        scope="system",
    )


def test_release_bundle_stage_is_gateway_owned_and_publishes_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    bundle = cache / "release.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("source/install-v4.ps1", "installer")
        archive.writestr("source/bago_core/launcher.py", "launcher")
    result, authorization = ExecutionGateway().execute_server_owned(
        request=_stage_request(str(bundle)), context=ExecutionContext()
    )
    destination = tmp_path / "manager" / "release-jobs" / "staging" / "job-1"
    assert result["ok"] is True
    assert authorization["kind"] == "server_policy"
    assert result["receipt_id"].startswith("release-stage:")
    assert (destination / "source" / "install-v4.ps1").read_text() == "installer"
    assert (destination / "source" / "bago_core" / "launcher.py").read_text() == "launcher"


@pytest.mark.parametrize("entries", [
    [("../escaped.txt", "bad")],
    [("safe", "file"), ("safe/child.txt", "bad")],
])
def test_release_bundle_preflight_blocks_unsafe_archive_before_staging(tmp_path, monkeypatch, entries):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    bundle = cache / "release.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        for name, body in entries:
            archive.writestr(name, body)
    with pytest.raises(ExecutionGatewayError):
        ExecutionGateway().execute_server_owned(
            request=_stage_request(str(bundle)), context=ExecutionContext()
        )
    staging = tmp_path / "manager" / "release-jobs" / "staging"
    assert not staging.exists()


def test_stage_adapter_rejects_direct_non_gateway_call(tmp_path):
    request = _stage_request(str(tmp_path / "anything.zip"))
    with pytest.raises(ExecutionGatewayError) as exc:
        ReleaseBundleStageEffectAdapter().execute(request, ExecutionContext())
    assert exc.value.code == "release_stage_authorization_required"


def test_release_stage_http_dispatch_uses_gateway_before_publishing(tmp_path, monkeypatch):
    import api_state

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    bundle = cache / "release.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("BAGO/install-v4.ps1", "installer")
    manager = SimpleNamespace(session_id="test-session")
    monkeypatch.setattr(api_state, "get_mgr", lambda handler: manager)

    class Handler:
        def __init__(self):
            self.wfile = io.BytesIO()
            self.status = None

        def send_response(self, status):
            self.status = status

        def send_header(self, *args):
            pass

        def _send_cors_headers(self):
            pass

        def end_headers(self):
            pass

    handler = Handler()
    matched, dispatch = resolve_post(handler, "/release/jobs/stage-bundle", {})
    assert matched is True
    dispatch(handler, {"job_id": "http-job", "bundle_path": str(bundle)})

    result = json.loads(handler.wfile.getvalue())
    assert handler.status == 200, result
    assert result["ok"] is True
    assert result["authorization"]["kind"] == "server_policy"
    staged = tmp_path / "manager" / "release-jobs" / "staging" / "http-job" / "BAGO" / "install-v4.ps1"
    assert staged.read_text() == "installer"


def test_release_stage_rejects_symlinked_staging_root_before_write(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    bundle = cache / "release.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("safe.txt", "data")
    staging = tmp_path / "manager" / "release-jobs" / "staging"
    outside = tmp_path / "outside"
    outside.mkdir()
    staging.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ExecutionGatewayError) as exc:
        ExecutionGateway().execute_server_owned(
            request=_stage_request(str(bundle)), context=ExecutionContext()
        )
    assert exc.value.code == "release_stage_symlink_forbidden"
    assert list(outside.iterdir()) == []


def test_release_stage_rejects_traversal_job_id_before_staging(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    bundle = cache / "release.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("safe.txt", "data")
    with pytest.raises(ExecutionGatewayError) as exc:
        ExecutionGateway().execute_server_owned(
            request=_stage_request(str(bundle), ".."), context=ExecutionContext()
        )
    assert exc.value.code == "release_stage_job_id_invalid"
    assert not (tmp_path / "manager" / "release-jobs" / "staging").exists()

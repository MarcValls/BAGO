from __future__ import annotations

import importlib
import importlib.util
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request
import pytest


API = Path(__file__).resolve().parents[1] / ".bago" / "api"
CORE = API.parent / "core"
sys.path[:0] = [str(API), str(CORE)]
SPEC = importlib.util.spec_from_file_location("handlers_release_jobs_download_test", API / "handlers_release_jobs.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class _Response:
    def __init__(self, content: bytes, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.content = content
        self.status = status
        self.headers = headers or {"Content-Length": str(len(content))}
        self.offset = 0

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            amount = len(self.content)
        chunk = self.content[self.offset:self.offset + amount]
        self.offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def _setup(monkeypatch, tmp_path: Path):
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    adapter = importlib.import_module("execution_adapters.release")
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    manager = SimpleNamespace(session_id="download-session")
    responses: list[tuple[int, dict]] = []
    handler = SimpleNamespace(headers={})
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))
    state_path = tmp_path / "manager" / "release-jobs" / "jobs" / "job-1.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"id": "job-1", "cancel_requested": False}), encoding="utf-8")
    base = {
        "job_id": "job-1",
        "filename": "bago-v4.6.0-distribution.zip",
        "asset_kind": "bundle",
        "url": "https://objects.githubusercontent.com/assets/bago-v4.6.0-distribution.zip",
        "size": 10,
        "digest": "",
        "resume": False,
    }
    return adapter, state_path, responses, handler, base


def test_release_job_bundle_download_is_gateway_owned_and_cache_is_job_scoped(monkeypatch, tmp_path: Path) -> None:
    adapter, _state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    body = b"0123456789"
    opened: list[Request] = []

    def urlopen(request, *, timeout, network_class):
        assert timeout == 60
        assert network_class == "release_asset_download"
        opened.append(request)
        return _Response(body)

    monkeypatch.setattr(adapter, "_gateway_urlopen", urlopen)
    MODULE.handle_download_asset(handler, payload)

    expected = tmp_path / "manager" / "release-jobs" / "cache" / "job-1" / payload["filename"]
    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "release.download"
    assert Path(responses[-1][1]["path"]) == expected
    assert expected.read_bytes() == body
    assert len(opened) == 1


def test_release_job_download_resumes_valid_range_and_hashes_full_asset(monkeypatch, tmp_path: Path) -> None:
    adapter, _state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    full = b"abcdefghij"
    partial = tmp_path / "manager" / "release-jobs" / "cache" / "job-1" / f"{payload['filename']}.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(full[:4])
    remaining = full[4:]
    opened: list[Request] = []

    def urlopen(request, *, timeout, network_class):
        opened.append(request)
        return _Response(
            remaining,
            status=206,
            headers={
                "Content-Length": str(len(remaining)),
                "Content-Range": f"bytes 4-{len(full) - 1}/{len(full)}",
            },
        )

    payload["resume"] = True
    monkeypatch.setattr(adapter, "_gateway_urlopen", urlopen)
    MODULE.handle_download_asset(handler, payload)

    assert opened[0].get_header("Range") == "bytes=4-"
    assert responses[-1][0] == 200
    assert Path(responses[-1][1]["path"]).read_bytes() == full
    assert responses[-1][1]["sha256"] == hashlib.sha256(full).hexdigest()


def test_release_job_download_rejects_invalid_filename_before_cache_or_network(monkeypatch, tmp_path: Path) -> None:
    _adapter, _state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    opened: list[bool] = []
    monkeypatch.setattr(_adapter, "_gateway_urlopen", lambda *_args, **_kwargs: opened.append(True))
    MODULE.handle_download_asset(handler, {**payload, "filename": "../outside.zip"})

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "release_download_filename_invalid"
    assert not (tmp_path / "manager" / "release-jobs" / "cache").exists()
    assert opened == []


def test_release_job_download_rejects_symlinked_job_cache_before_network(monkeypatch, tmp_path: Path) -> None:
    adapter, _state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    cache = tmp_path / "manager" / "release-jobs" / "cache"
    cache.mkdir(parents=True)
    external = tmp_path / "outside-cache"
    external.mkdir()
    try:
        (cache / "job-1").symlink_to(external, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    opened: list[bool] = []
    monkeypatch.setattr(adapter, "_gateway_urlopen", lambda *_args, **_kwargs: opened.append(True))
    MODULE.handle_download_asset(handler, payload)

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "release_download_job_id_invalid"
    assert list(external.iterdir()) == []
    assert opened == []


def test_release_job_digest_mismatch_never_publishes_asset(monkeypatch, tmp_path: Path) -> None:
    adapter, _state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    body = b"0123456789"
    monkeypatch.setattr(adapter, "_gateway_urlopen", lambda *_args, **_kwargs: _Response(body))
    MODULE.handle_download_asset(handler, {**payload, "digest": "0" * 64})

    target = tmp_path / "manager" / "release-jobs" / "cache" / "job-1" / payload["filename"]
    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "release_download_digest_mismatch"
    assert not target.exists()
    assert not target.with_suffix(target.suffix + ".part").exists()


def test_release_job_download_rejects_inconsistent_resume_range_before_cache_write(monkeypatch, tmp_path: Path) -> None:
    adapter, _state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    partial = tmp_path / "manager" / "release-jobs" / "cache" / "job-1" / f"{payload['filename']}.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"abcd")
    opened: list[bool] = []

    def urlopen(*_args, **_kwargs):
        opened.append(True)
        return _Response(
            b"efghij",
            status=206,
            headers={"Content-Length": "6", "Content-Range": "bytes 4-9/11"},
        )

    monkeypatch.setattr(adapter, "_gateway_urlopen", urlopen)
    MODULE.handle_download_asset(handler, {**payload, "resume": True})

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "release_download_range_invalid"
    assert not partial.exists()


def test_release_job_cancel_preserves_partial_and_opens_no_network(monkeypatch, tmp_path: Path) -> None:
    adapter, state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    state_path.write_text(json.dumps({"id": "job-1", "cancel_requested": True}), encoding="utf-8")
    partial = tmp_path / "manager" / "release-jobs" / "cache" / "job-1" / f"{payload['filename']}.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"partial")

    def forbidden_urlopen(*_args, **_kwargs):
        raise AssertionError("cancelled jobs must be rejected before network access")

    monkeypatch.setattr(adapter, "_gateway_urlopen", forbidden_urlopen)
    MODULE.handle_download_asset(handler, {**payload, "resume": True})

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "release_download_cancelled"
    assert partial.read_bytes() == b"partial"


def test_release_job_unapproved_url_is_rejected_before_cache_creation(monkeypatch, tmp_path: Path) -> None:
    adapter, _state_path, responses, handler, payload = _setup(monkeypatch, tmp_path)
    opened: list[bool] = []
    monkeypatch.setattr(adapter, "_gateway_urlopen", lambda *_args, **_kwargs: opened.append(True))
    MODULE.handle_download_asset(handler, {**payload, "url": "http://attacker.invalid/bundle.zip"})

    cache = tmp_path / "manager" / "release-jobs" / "cache"
    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "network_read_release_host_blocked"
    assert not cache.exists()
    assert opened == []

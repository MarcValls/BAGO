from __future__ import annotations

import json
import io
from pathlib import Path

import pytest

from execution_adapters.release_job_log import ReleaseJobLogEffectAdapter
from execution_adapters.release_job_state import ReleaseJobStateEffectAdapter
from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_gateway import ExecutionGateway
from execution_request import build_execution_request
from api_dispatch import resolve_post
from authorization_boundary import AuthorizationBoundary
from execution_adapters.release_job_archive import ReleaseJobArchiveEffectAdapter


def _request(effect_id: str, job_id: str, arguments: dict):
    source = {
        "release.job.persist": "server.electron.release_job.persist",
        "release.job.log.append": "server.electron.release_job.log",
    }[effect_id]
    return build_execution_request(
        effect_id=effect_id,
        actor_kind="server",
        principal_id="bago-electron-release-manager",
        session_id="release-job-manager",
        source_surface=source,
        target={"job_id": job_id},
        arguments=arguments,
        scope="system",
    )


def test_release_job_state_is_persisted_atomically_by_gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    state = {"id": "release-123-abcd", "state": "queued", "progress": {"percent": 0}}
    result, authorization = ExecutionGateway().execute_server_owned(
        request=_request("release.job.persist", state["id"], {"state": state}),
        context=ExecutionContext(),
    )
    target = tmp_path / "manager" / "release-jobs" / "jobs" / f"{state['id']}.json"
    assert result["ok"] is True
    assert authorization["kind"] == "server_policy"
    assert result["receipt_id"].startswith("release-job-state:")
    assert json.loads(target.read_text(encoding="utf-8")) == state
    assert list(target.parent.glob("*.tmp")) == []


def test_release_job_state_identity_mismatch_blocks_before_directory_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    request = _request("release.job.persist", "release-expected", {"state": {"id": "release-other"}})
    with pytest.raises(ExecutionGatewayError) as exc:
        ExecutionGateway().execute_server_owned(request=request, context=ExecutionContext())
    assert exc.value.code == "release_job_state_identity_mismatch"
    assert not (tmp_path / "manager" / "release-jobs").exists()


def test_release_job_state_rejects_traversal_id_before_directory_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    request = _request("release.job.persist", "..", {"state": {"id": ".."}})
    with pytest.raises(ExecutionGatewayError) as exc:
        ExecutionGateway().execute_server_owned(request=request, context=ExecutionContext())
    assert exc.value.code == "release_job_state_invalid"
    assert not (tmp_path / "manager" / "release-jobs").exists()


def test_release_job_log_appends_one_bounded_record_through_gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    record = {"timestamp": "2026-09-25T05:00:00.000Z", "level": "warn", "message": "cancel requested"}
    result, authorization = ExecutionGateway().execute_server_owned(
        request=_request("release.job.log.append", "release-123-abcd", {"record": record}),
        context=ExecutionContext(),
    )
    target = tmp_path / "manager" / "release-jobs" / "logs" / "release-123-abcd.jsonl"
    assert result["ok"] is True
    assert authorization["kind"] == "server_policy"
    assert json.loads(target.read_text(encoding="utf-8")) == record


def test_release_job_storage_http_routes_dispatch_to_canonical_adapters(tmp_path, monkeypatch):
    import api_state

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    monkeypatch.setattr(api_state, "get_mgr", lambda handler: object())

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

    state = {"id": "release-http-1", "state": "queued"}
    handler = Handler()
    matched, dispatch = resolve_post(handler, "/release/jobs/persist", {})
    assert matched is True
    dispatch(handler, {"job_id": state["id"], "state": state})
    persisted = json.loads(handler.wfile.getvalue())
    assert handler.status == 200
    assert persisted["authorization"]["kind"] == "server_policy"
    assert json.loads((tmp_path / "manager/release-jobs/jobs/release-http-1.json").read_text()) == state

    handler = Handler()
    matched, dispatch = resolve_post(handler, "/release/jobs/append-log", {})
    assert matched is True
    dispatch(handler, {"job_id": state["id"], "record": {"timestamp": "now", "level": "info", "message": "created"}})
    appended = json.loads(handler.wfile.getvalue())
    assert handler.status == 200
    assert appended["authorization"]["kind"] == "server_policy"
    line = (tmp_path / "manager/release-jobs/logs/release-http-1.jsonl").read_text().splitlines()[0]
    assert json.loads(line)["message"] == "created"


@pytest.mark.parametrize("adapter,effect_id,arguments", [
    (ReleaseJobStateEffectAdapter(), "release.job.persist", {"state": {"id": "release-1"}}),
    (ReleaseJobLogEffectAdapter(), "release.job.log.append", {"record": {"level": "invalid"}}),
])
def test_job_storage_adapters_reject_direct_non_gateway_calls(adapter, effect_id, arguments):
    request = _request(effect_id, "release-1", arguments)
    with pytest.raises(ExecutionGatewayError):
        adapter.execute(request, ExecutionContext())


def test_release_job_archive_is_permit_bound_and_moves_only_exact_terminal_state(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    root = tmp_path / "manager" / "release-jobs"
    jobs = root / "jobs"
    logs = root / "logs"
    staging = root / "staging" / "release-archive-1"
    jobs.mkdir(parents=True)
    logs.mkdir(parents=True)
    staging.mkdir(parents=True)
    state_path = jobs / "release-archive-1.json"
    state_path.write_text(json.dumps({"id": "release-archive-1", "state": "failed"}), encoding="utf-8")
    (logs / "release-archive-1.jsonl").write_text('{"message":"done"}\n', encoding="utf-8")
    (staging / "payload.bin").write_bytes(b"payload")
    archived_at = "2026-09-25T05:30:00.000Z"
    import hashlib

    request = build_execution_request(
        effect_id="release.job.archive",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="archive-test-session",
        source_surface="api.release.jobs.archive",
        target={"job_id": "release-archive-1", "state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest()},
        arguments={"archived_at": archived_at},
        scope="system",
    )
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="archive-interaction-1")
    approval = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="archive-interaction-1",
        session_id=request.session_id,
        channel="desktop",
    )
    result, authorization = ExecutionGateway(boundary).execute(
        permit_token=approval["permit"]["token"], request=request, context=ExecutionContext()
    )
    archive_dir = root / "archive" / "deleted-jobs" / "release-archive-1"
    assert authorization["state"] == "consumed"
    assert result["effect_id"] == "release.job.archive"
    assert json.loads((archive_dir / "job.json").read_text(encoding="utf-8"))["state"] == "deleted"
    assert (archive_dir / "job.active.json").is_file()
    assert (archive_dir / "job.log.jsonl").is_file()
    assert (archive_dir / "staging" / "payload.bin").read_bytes() == b"payload"
    assert not state_path.exists()


def test_release_job_archive_changed_state_blocks_before_archive_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    jobs = tmp_path / "manager" / "release-jobs" / "jobs"
    jobs.mkdir(parents=True)
    state_path = jobs / "release-archive-2.json"
    state_path.write_text('{"id":"release-archive-2","state":"failed"}', encoding="utf-8")
    import hashlib

    request = build_execution_request(
        effect_id="release.job.archive", actor_kind="user", principal_id="interactive-local-user",
        session_id="archive-test-session", source_surface="api.release.jobs.archive",
        target={"job_id": "release-archive-2", "state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest()},
        arguments={"archived_at": "2026-09-25T05:30:00Z"}, scope="system",
    )
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="archive-interaction-2")
    approval = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="archive-interaction-2",
        session_id=request.session_id, channel="desktop",
    )
    state_path.write_text('{"id":"release-archive-2","state":"completed"}', encoding="utf-8")
    with pytest.raises(ExecutionGatewayError) as exc:
        ExecutionGateway(boundary).execute(permit_token=approval["permit"]["token"], request=request, context=ExecutionContext())
    assert exc.value.code == "release_job_archive_state_changed"
    assert state_path.exists()
    assert not (tmp_path / "manager" / "release-jobs" / "archive").exists()


def test_release_job_archive_preserves_recovery_data_if_rollback_move_fails(tmp_path, monkeypatch):
    import hashlib
    import execution_adapters.release_job_archive as archive_adapter

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    root = tmp_path / "manager" / "release-jobs"
    (root / "jobs").mkdir(parents=True)
    (root / "logs").mkdir()
    (root / "staging" / "release-archive-recovery").mkdir(parents=True)
    state_path = root / "jobs" / "release-archive-recovery.json"
    log_path = root / "logs" / "release-archive-recovery.jsonl"
    stage_path = root / "staging" / "release-archive-recovery"
    state_path.write_text('{"id":"release-archive-recovery","state":"failed"}', encoding="utf-8")
    log_path.write_text('{"message":"preserve"}\n', encoding="utf-8")
    (stage_path / "payload.bin").write_bytes(b"preserve")
    request = build_execution_request(
        effect_id="release.job.archive", actor_kind="user", principal_id="interactive-local-user",
        session_id="archive-recovery-session", source_surface="api.release.jobs.archive",
        target={"job_id": "release-archive-recovery", "state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest()},
        arguments={"archived_at": "2026-09-25T05:30:00Z"}, scope="system",
    )
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="archive-recovery-interaction")
    approval = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="archive-recovery-interaction",
        session_id=request.session_id, channel="desktop",
    )
    real_replace = archive_adapter.os.replace

    def fail_stage_and_state_restore(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path == stage_path or (source_path.name == "job.active.json" and destination_path == state_path):
            raise OSError("injected move failure")
        return real_replace(source, destination)

    monkeypatch.setattr(archive_adapter.os, "replace", fail_stage_and_state_restore)
    with pytest.raises(ExecutionGatewayError) as exc:
        ExecutionGateway(boundary).execute(permit_token=approval["permit"]["token"], request=request, context=ExecutionContext())
    assert exc.value.code == "release_job_archive_recovery_required"
    archive_dir = root / "archive" / "deleted-jobs" / "release-archive-recovery"
    assert (archive_dir / "job.json").is_file()
    assert (archive_dir / "job.active.json").is_file()
    assert log_path.is_file()
    assert (stage_path / "payload.bin").is_file()


def test_release_job_archive_api_uses_boundary_challenge_approve_and_gateway(tmp_path, monkeypatch):
    import api_state

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path))
    jobs = tmp_path / "manager" / "release-jobs" / "jobs"
    jobs.mkdir(parents=True)
    state_path = jobs / "release-http-archive.json"
    state_path.write_text('{"id":"release-http-archive","state":"cancelled"}', encoding="utf-8")

    class Manager:
        session_id = "release-archive-api-session"

    monkeypatch.setattr(api_state, "get_mgr", lambda handler: Manager())

    class Handler:
        headers = {"X-Bago-Channel": "desktop"}

        def __init__(self):
            self.wfile = io.BytesIO()
            self.status = None

        def send_response(self, status): self.status = status
        def send_header(self, *args): pass
        def _send_cors_headers(self): pass
        def end_headers(self): pass

    matched, dispatch = resolve_post(Handler(), "/release/jobs/archive", {})
    assert matched is True
    payload = {"job_id": "release-http-archive", "archived_at": "2026-09-25T05:30:00Z", "interaction_id": "release-http-archive-interaction"}
    challenge_handler = Handler()
    dispatch(challenge_handler, {**payload, "authorization_action": "challenge"})
    challenge_response = json.loads(challenge_handler.wfile.getvalue())
    assert challenge_handler.status == 200
    challenge_id = challenge_response["authorization"]["challenge"]["challenge_id"]

    approve_handler = Handler()
    dispatch(approve_handler, {**payload, "authorization_action": "approve", "challenge_id": challenge_id, "user_decision": "approve"})
    approve_response = json.loads(approve_handler.wfile.getvalue())
    assert approve_handler.status == 200
    permit = approve_response["authorization"]["permit"]["token"]

    execute_handler = Handler()
    dispatch(execute_handler, {**payload, "authorization_action": "execute", "authorization_permit": permit})
    result = json.loads(execute_handler.wfile.getvalue())
    assert execute_handler.status == 200
    assert result["effect_id"] == "release.job.archive"
    assert result["authorization"]["state"] == "consumed"

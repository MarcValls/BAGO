from __future__ import annotations

import json
from pathlib import Path

import pytest

import authorization_boundary as auth
from effect_registry import REGISTRY
from execution_request import ExecutionRequest, build_execution_request


@pytest.fixture(autouse=True)
def _confirmed_native_dialog_for_unit_tests(monkeypatch) -> None:
    monkeypatch.setattr(auth, "confirm_strong_challenge", lambda _challenge: True)


def _request(inputs: dict | None = None) -> ExecutionRequest:
    return build_execution_request(
        effect_id="capability.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.authorization",
        target={
            "package_id": "local.safe-example",
            "package_kind": "capability",
            "package_version": "1.0.0",
            "package_digest": "digest-A",
        },
        arguments=inputs or {"value": "A"},
    )


def _strong_request() -> ExecutionRequest:
    return build_execution_request(
        effect_id="system.update.apply",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.authorization",
        target={"resource": "release", "release_id": "candidate-A"},
        arguments={},
        scope="system",
    )


def test_strong_header_cannot_self_approve_without_native_confirmation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    monkeypatch.setattr(auth, "confirm_strong_challenge", lambda _challenge: False)
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(_strong_request(), interaction_id="interaction-strong")

    with pytest.raises(auth.AuthorizationError) as denied:
        boundary.approve_challenge(
            challenge_id=challenge["challenge_id"], interaction_id="interaction-strong",
            session_id="session-1", channel="desktop",
        )
    assert denied.value.code == "authorization_strong_confirmation_denied"
    ledger = json.loads((tmp_path / "authorization" / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["challenges"][challenge["challenge_id"]]["state"] == "denied"
    assert ledger["permits"] == {}


def test_strong_native_confirmation_binds_one_challenge_and_rejects_parallel_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    request = _strong_request()
    challenge = boundary.create_challenge(request, interaction_id="interaction-strong")
    seen = []

    def confirm(record):
        seen.append(record)
        with pytest.raises(auth.AuthorizationError) as replay:
            boundary.approve_challenge(
                challenge_id=challenge["challenge_id"], interaction_id="interaction-strong",
                session_id="session-1", channel="desktop",
            )
        assert replay.value.code == "authorization_challenge_not_pending"
        return True

    monkeypatch.setattr(auth, "confirm_strong_challenge", confirm)
    approved = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="interaction-strong",
        session_id="session-1", channel="desktop",
    )
    assert seen[0]["operation_fingerprint"] == request.fingerprint
    assert seen[0]["session_id"] == request.session_id
    assert approved["proof"]["provenance"]["verified_by"] == "server_native_dialog"
    assert boundary.consume_permit(permit_token=approved["permit"]["token"], request=request)["state"] == "consumed"


def test_projection_tamper_cannot_change_strong_operation_after_dialog(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(_strong_request(), interaction_id="interaction-strong")

    def tamper(_record):
        ledger_path = tmp_path / "authorization" / "ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["challenges"][challenge["challenge_id"]]["operation_fingerprint"] = "changed"
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        return True

    monkeypatch.setattr(auth, "confirm_strong_challenge", tamper)
    approved = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="interaction-strong",
        session_id="session-1", channel="desktop",
    )
    assert approved["permit"]["operation_fingerprint"] == challenge["operation_fingerprint"]
    projected = json.loads((tmp_path / "authorization" / "ledger.json").read_text(encoding="utf-8"))
    assert projected["challenges"][challenge["challenge_id"]]["operation_fingerprint"] == challenge["operation_fingerprint"]


def test_forged_projection_permit_is_not_live_authority(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    request = _strong_request()
    token = "forged-token"
    projection = {
        "contract_version": auth.AUTHORIZATION_CONTRACT_VERSION,
        "challenges": {},
        "permits": {
            auth._token_hash(token): {
                "state": "active", "effect_id": request.effect_id,
                "session_id": request.session_id,
                "operation_fingerprint": request.fingerprint,
            }
        },
    }
    path = tmp_path / "authorization" / "ledger.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(projection), encoding="utf-8")
    with pytest.raises(auth.AuthorizationError) as denied:
        auth.AuthorizationBoundary().consume_permit(permit_token=token, request=request)
    assert denied.value.code == "authorization_permit_invalid"


@pytest.mark.parametrize(
    "effect_id,scope",
    [(effect.id, effect.default_scope) for effect in REGISTRY.effects if effect.authorization_mode == "strong"],
)
def test_every_strong_effect_rejects_declared_channel_without_native_confirmation(
    effect_id, scope, tmp_path, monkeypatch,
) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    monkeypatch.setattr(auth, "confirm_strong_challenge", lambda _challenge: False)
    request = build_execution_request(
        effect_id=effect_id, actor_kind="user", principal_id="interactive-local-user",
        session_id="session-strong", source_surface="test.authorization",
        target={"resource": "test-target"}, arguments={}, scope=scope,
    )
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="interaction-strong")
    with pytest.raises(auth.AuthorizationError) as denied:
        boundary.approve_challenge(
            challenge_id=challenge["challenge_id"], interaction_id="interaction-strong",
            session_id=request.session_id, channel="desktop",
        )
    assert denied.value.code == "authorization_strong_confirmation_denied"


def test_second_strong_challenge_cannot_open_parallel_prompt(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    first = boundary.create_challenge(_strong_request(), interaction_id="first")
    second = boundary.create_challenge(_strong_request(), interaction_id="second")

    def confirm(_record):
        with pytest.raises(auth.AuthorizationError) as busy:
            boundary.approve_challenge(
                challenge_id=second["challenge_id"], interaction_id="second",
                session_id="session-1", channel="desktop",
            )
        assert busy.value.code == "authorization_strong_confirmation_busy"
        return True

    monkeypatch.setattr(auth, "confirm_strong_challenge", confirm)
    boundary.approve_challenge(
        challenge_id=first["challenge_id"], interaction_id="first",
        session_id="session-1", channel="desktop",
    )


def test_restart_invalidates_process_local_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    request = _strong_request()
    challenge = boundary.create_challenge(request, interaction_id="interaction-strong")
    token = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="interaction-strong",
        session_id=request.session_id, channel="desktop",
    )["permit"]["token"]
    auth._PROCESS_AUTHORITY.pop(str((tmp_path / "authorization" / "ledger.json").resolve()), None)
    with pytest.raises(auth.AuthorizationError) as invalid:
        boundary.consume_permit(permit_token=token, request=request)
    assert invalid.value.code == "authorization_permit_invalid"


def test_direct_user_challenge_issues_one_time_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    request = _request()

    challenge = boundary.create_challenge(request, interaction_id="interaction-1")
    authorized = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-1",
        session_id="session-1",
        channel="ui-react",
    )

    proof = authorized["proof"]
    decision = authorized["decision"]
    permit = authorized["permit"]
    assert challenge["effect_id"] == "capability.execute"
    assert challenge["arguments_digest"] == request.arguments_digest
    assert proof["user_decision"] == "approve"
    assert proof["provenance"]["kind"] == "direct_user_interaction"
    assert proof["operation_fingerprint"] == request.fingerprint
    assert proof["effect_id"] == request.effect_id
    assert decision["result"] == "allow"
    assert permit["operation_fingerprint"] == request.fingerprint
    assert permit["effect_id"] == request.effect_id

    consumed = boundary.consume_permit(
        permit_token=permit["token"],
        request=request,
    )
    assert consumed["state"] == "consumed"

    with pytest.raises(auth.AuthorizationError) as replay:
        boundary.consume_permit(
            permit_token=permit["token"],
            request=request,
        )
    assert replay.value.code == "authorization_permit_replay"


def test_non_interactive_origin_cannot_mint_user_authorization(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(_request(), interaction_id="interaction-agent")

    with pytest.raises(auth.AuthorizationError) as denied:
        boundary.approve_challenge(
            challenge_id=challenge["challenge_id"],
            interaction_id="interaction-agent",
            session_id="session-1",
            channel="agent",
        )
    assert denied.value.code == "authorization_user_origin_unverified"


def test_operation_mutation_after_approval_invalidates_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    original = _request({"value": "A"})
    challenge = boundary.create_challenge(original, interaction_id="interaction-2")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-2",
        session_id="session-1",
        channel="ui-react",
    )["permit"]

    mutated = _request({"value": "B"})
    with pytest.raises(auth.AuthorizationError) as mismatch:
        boundary.consume_permit(permit_token=permit["token"], request=mutated)
    assert mismatch.value.code == "authorization_operation_mismatch"


def test_effect_change_after_approval_invalidates_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    original = _request()
    challenge = boundary.create_challenge(original, interaction_id="interaction-effect")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-effect",
        session_id="session-1",
        channel="ui-react",
    )["permit"]

    mutated = build_execution_request(
        effect_id="pipeline.execute",
        actor_kind=original.actor_kind,
        principal_id=original.principal_id,
        session_id=original.session_id,
        source_surface=original.source_surface,
        target={
            "package_id": "local.safe-example",
            "package_kind": "pipeline",
            "package_version": "1.0.0",
            "package_digest": "digest-A",
        },
        arguments=original.arguments,
    )
    with pytest.raises(auth.AuthorizationError) as mismatch:
        boundary.consume_permit(permit_token=permit["token"], request=mutated)
    assert mismatch.value.code == "authorization_effect_mismatch"


def test_raw_permit_token_is_not_persisted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(_request(), interaction_id="interaction-3")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-3",
        session_id="session-1",
        channel="ui-react",
    )["permit"]

    ledger = (tmp_path / "authorization" / "ledger.json").read_text(encoding="utf-8")
    assert permit["token"] not in ledger
    parsed = json.loads(ledger)
    assert parsed["contract_version"] == "bago.authorization/v2"
    assert parsed["permits"]


def test_http_capability_handler_uses_closed_gateway_not_caller_callable() -> None:
    root = Path(__file__).resolve().parents[2]
    handlers = (root / "backend" / ".bago" / "api" / "handlers_capability_packages.py").read_text(encoding="utf-8")
    bridge = (root / "backend" / ".bago" / "api" / "bridge.py").read_text(encoding="utf-8")

    assert 'payload.get("authorization_permit")' in handlers
    assert 'payload.get("authorization_action")' in handlers
    assert "build_execution_request(" in handlers
    assert "ExecutionContext(manager=mgr)" in handlers
    assert "def material_execute" not in handlers
    assert "executor=" not in handlers
    assert "execute_package(" not in handlers
    assert "execute_pipeline_package(" not in handlers
    assert '(body or {}).get("confirmed") is True' not in handlers
    assert '(body or {}).get("approved_permissions", [])' not in handlers
    assert 'mgr.set_tool_approval_policy("always")' not in bridge
    assert 'mgr.set_tool_approval_policy("ask")' in bridge


def test_permit_becomes_world_state_stale_before_operation_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    original = build_execution_request(
        effect_id="filesystem.read", actor_kind="user", principal_id="interactive-local-user",
        session_id="session-world-state", source_surface="test.world-state",
        target={"path": "notes/state.txt"}, arguments={},
        world_state={"workspace": "repo-a", "branch": "main", "revision": "one"},
    )
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(original, interaction_id="interaction-world-state")
    approved = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="interaction-world-state",
        session_id=original.session_id, channel="ui-react",
    )
    ledger = json.loads((tmp_path / "authorization" / "ledger.json").read_text(encoding="utf-8"))
    assert next(iter(ledger["permits"].values()))["world_state_digest"] == original.world_state_digest
    changed = build_execution_request(
        effect_id=original.effect_id, actor_kind=original.actor_kind, principal_id=original.principal_id,
        session_id=original.session_id, source_surface=original.source_surface,
        target=original.target, arguments=original.arguments, policy_version=original.policy_version,
        world_state={"workspace": "repo-a", "branch": "main", "revision": "two"},
    )
    assert changed.world_state_digest != original.world_state_digest
    with pytest.raises(auth.AuthorizationError) as stale:
        boundary.consume_permit(permit_token=approved["permit"]["token"], request=changed)
    assert stale.value.code == "authorization_world_state_stale"


def test_legacy_operation_builder_requires_explicit_snapshot_authority():
    with pytest.raises(auth.AuthorizationError) as blocked:
        auth.build_operation(
            capability_id="legacy-package", inputs={}, permissions=[], session_id="legacy-session",
        )
    assert blocked.value.code == "authorization_world_state_authority_required"


def test_world_state_digest_must_match_declared_state():
    with pytest.raises(ValueError) as mismatch:
        build_execution_request(
            effect_id="filesystem.read", actor_kind="user", principal_id="user",
            session_id="session-world-invalid", source_surface="test.world-state",
            target={"path": "notes/state.txt"}, arguments={},
            world_state={"revision": "one"}, world_state_digest="0" * 64,
        )
    assert mismatch.value.code == "execution_world_state_mismatch"

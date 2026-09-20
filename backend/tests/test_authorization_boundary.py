from __future__ import annotations

import json
from pathlib import Path

import pytest

import authorization_boundary as auth
from execution_request import ExecutionRequest, build_execution_request


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

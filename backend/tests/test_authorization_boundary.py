from __future__ import annotations

import json
from pathlib import Path

import pytest

import authorization_boundary as auth


def _operation(inputs: dict | None = None) -> auth.AuthorizationOperation:
    return auth.build_operation(
        capability_id="local.safe-example",
        inputs=inputs or {"value": "A"},
        permissions=["filesystem.read", "filesystem.write"],
        session_id="session-1",
    )


def test_direct_user_challenge_issues_one_time_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    operation = _operation()

    challenge = boundary.create_challenge(operation, interaction_id="interaction-1")
    authorized = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-1",
        session_id="session-1",
        channel="ui-react",
    )

    proof = authorized["proof"]
    decision = authorized["decision"]
    permit = authorized["permit"]
    assert proof["user_decision"] == "approve"
    assert proof["provenance"]["kind"] == "direct_user_interaction"
    assert proof["operation_fingerprint"] == operation.fingerprint
    assert decision["result"] == "allow"
    assert permit["operation_fingerprint"] == operation.fingerprint

    result, consumed = auth.ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        operation=operation,
        executor=lambda: {"ok": True},
    )
    assert result == {"ok": True}
    assert consumed["state"] == "consumed"

    with pytest.raises(auth.AuthorizationError) as replay:
        auth.ExecutionGateway(boundary).execute(
            permit_token=permit["token"],
            operation=operation,
            executor=lambda: {"should_not": "run"},
        )
    assert replay.value.code == "authorization_permit_replay"


def test_non_interactive_origin_cannot_mint_user_authorization(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(_operation(), interaction_id="interaction-agent")

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
    original = _operation({"value": "A"})
    challenge = boundary.create_challenge(original, interaction_id="interaction-2")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-2",
        session_id="session-1",
        channel="ui-react",
    )["permit"]

    mutated = _operation({"value": "B"})
    with pytest.raises(auth.AuthorizationError) as mismatch:
        boundary.consume_permit(permit_token=permit["token"], operation=mutated)
    assert mismatch.value.code == "authorization_operation_mismatch"


def test_raw_permit_token_is_not_persisted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    challenge = boundary.create_challenge(_operation(), interaction_id="interaction-3")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-3",
        session_id="session-1",
        channel="ui-react",
    )["permit"]

    ledger = (tmp_path / "authorization" / "ledger.json").read_text(encoding="utf-8")
    assert permit["token"] not in ledger
    parsed = json.loads(ledger)
    assert parsed["permits"]


def test_http_capability_handler_does_not_trust_client_confirmation_flags() -> None:
    root = Path(__file__).resolve().parents[2]
    handlers = (root / "backend" / ".bago" / "api" / "handlers_capability_packages.py").read_text(encoding="utf-8")
    bridge = (root / "backend" / ".bago" / "api" / "bridge.py").read_text(encoding="utf-8")

    assert 'payload.get("authorization_permit")' in handlers
    assert 'payload.get("authorization_action")' in handlers
    assert '"confirmed": True' in handlers
    assert '"approved_permissions": list(operation.permissions)' in handlers
    assert '(body or {}).get("confirmed") is True' not in handlers
    assert '(body or {}).get("approved_permissions", [])' not in handlers
    assert 'mgr.set_tool_approval_policy("always")' not in bridge
    assert 'mgr.set_tool_approval_policy("ask")' in bridge

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import authorization_boundary as auth
import delegation_grant as dg
from delegation_grant import DelegationError, DelegationGrantRegistry
from effect_registry import REGISTRY
from execution_gateway import EffectAdapterRegistry, ExecutionContext, ExecutionGateway
from execution_request import build_execution_request, stable_digest


class _RecordingAdapter:
    effect_ids = frozenset({"filesystem.write"})

    def __init__(self) -> None:
        self.calls = []

    def execute(self, request, context):
        self.calls.append(request)
        return {"ok": True, "path": request.target["path"]}


def _future(minutes: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _issue_grant(tmp_path, monkeypatch, *, max_runs: int = 2, allowed_effect: str = "filesystem.write"):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    boundary = auth.AuthorizationBoundary()

    child_target = {"path": "notes/example.txt"}
    child_arguments = {"content": "A"}
    schedule_id = "schedule-1"
    schedule_digest = stable_digest({"schedule_id": schedule_id, "definition": "fixed"})
    grant_id = "delegation-test-1"

    parent = build_execution_request(
        effect_id="schedule.delegate",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.schedule.delegate",
        target={
            "schedule_id": schedule_id,
            "schedule_digest": schedule_digest,
            "grant_id": grant_id,
        },
        arguments={
            "grant_id": grant_id,
            "allowed_effects": [allowed_effect],
            "target_digest": stable_digest(child_target),
            "arguments_digest": stable_digest(child_arguments),
            "scope": "workspace",
            "policy_version": REGISTRY.digest,
            "expires_at": _future(),
            "max_runs": max_runs,
            "child_actor_kind": "scheduler",
            "child_source_surface": "scheduler",
        },
        scope="persistent",
        policy_version=REGISTRY.digest,
    )
    challenge = boundary.create_challenge(parent, interaction_id="interaction-delegation")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-delegation",
        session_id=parent.session_id,
        channel="ui-react",
    )["permit"]
    result, consumed = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=parent,
        context=ExecutionContext(services={"state_dir": tmp_path / "state"}),
    )
    grant = result["delegation_grant"]

    child = build_execution_request(
        effect_id=allowed_effect,
        actor_kind="scheduler",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="scheduler",
        target=child_target,
        arguments=child_arguments,
        scope="workspace",
        policy_version=REGISTRY.digest,
        parent_execution_id=f"schedule:{schedule_id}",
        delegation_id=grant_id,
    )
    return {
        "boundary": boundary,
        "grant": grant,
        "child": child,
        "schedule_id": schedule_id,
        "schedule_digest": schedule_digest,
        "state_dir": tmp_path / "state",
        "parent_consumed": consumed,
    }


def test_grant_is_materialized_only_from_consumed_parent_authorization(tmp_path, monkeypatch):
    issued = _issue_grant(tmp_path, monkeypatch)
    grant = issued["grant"]

    assert issued["parent_consumed"]["state"] == "consumed"
    assert grant["state"] == "active"
    assert grant["allowed_effects"] == ["filesystem.write"]
    assert grant["run_count"] == 0
    assert grant["max_runs"] == 2
    assert grant["origin"]["proof_kind"] == "direct_user_interaction"
    assert grant["origin"]["proof_assurance"] == "interactive_origin"
    assert grant["can_redelegate"] is False
    assert grant["delegation_depth"] == 1


def test_each_delegated_run_gets_fresh_one_time_permit(tmp_path, monkeypatch):
    issued = _issue_grant(tmp_path, monkeypatch, max_runs=1)
    boundary = issued["boundary"]
    child = issued["child"]

    delegated = boundary.issue_delegated_permit(
        request=child,
        state_dir=issued["state_dir"],
        schedule_id=issued["schedule_id"],
        schedule_digest=issued["schedule_digest"],
    )
    assert delegated["delegation"]["claimed_run"] == 1
    assert delegated["delegation"]["grant_state_after_claim"] == "exhausted"

    adapter = _RecordingAdapter()
    adapters = EffectAdapterRegistry()
    adapters.register(adapter)
    gateway = ExecutionGateway(boundary=boundary, adapters=adapters)
    result, consumed = gateway.execute(
        permit_token=delegated["permit"]["token"],
        request=child,
    )
    assert result["ok"] is True
    assert consumed["state"] == "consumed"
    assert len(adapter.calls) == 1

    with pytest.raises(auth.AuthorizationError) as replay:
        gateway.execute(
            permit_token=delegated["permit"]["token"],
            request=child,
        )
    assert replay.value.code == "authorization_permit_replay"

    with pytest.raises(DelegationError) as exhausted:
        boundary.issue_delegated_permit(
            request=child,
            state_dir=issued["state_dir"],
            schedule_id=issued["schedule_id"],
            schedule_digest=issued["schedule_digest"],
        )
    assert exhausted.value.code == "delegation_exhausted"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("effect", "delegation_effect_exceeds_grant"),
        ("target", "delegation_target_exceeds_grant"),
        ("arguments", "delegation_arguments_exceed_grant"),
        ("scope", "delegation_scope_exceeds_grant"),
        ("actor", "delegation_actor_mismatch"),
        ("surface", "delegation_surface_mismatch"),
        ("lineage", "delegation_parent_lineage_mismatch"),
    ],
)
def test_child_authority_cannot_expand(tmp_path, monkeypatch, mutation, expected_code):
    issued = _issue_grant(tmp_path, monkeypatch, max_runs=10)
    base = issued["child"]
    kwargs = {
        "effect_id": base.effect_id,
        "actor_kind": base.actor_kind,
        "principal_id": base.principal_id,
        "session_id": base.session_id,
        "source_surface": base.source_surface,
        "target": base.target,
        "arguments": base.arguments,
        "scope": base.scope,
        "policy_version": base.policy_version,
        "parent_execution_id": base.parent_execution_id,
        "delegation_id": base.delegation_id,
    }
    if mutation == "effect":
        kwargs["effect_id"] = "filesystem.read"
    elif mutation == "target":
        kwargs["target"] = {"path": "notes/other.txt"}
    elif mutation == "arguments":
        kwargs["arguments"] = {"content": "B"}
    elif mutation == "scope":
        kwargs["scope"] = "persistent"
    elif mutation == "actor":
        kwargs["actor_kind"] = "agent"
    elif mutation == "surface":
        kwargs["source_surface"] = "agent"
    elif mutation == "lineage":
        kwargs["parent_execution_id"] = "schedule:other"
    mutated = build_execution_request(**kwargs)

    with pytest.raises(DelegationError) as denied:
        DelegationGrantRegistry(issued["state_dir"]).validate_child(
            issued["grant"]["grant_id"],
            mutated,
            schedule_id=issued["schedule_id"],
            schedule_digest=issued["schedule_digest"],
        )
    assert denied.value.code == expected_code


def test_schedule_definition_change_invalidates_grant(tmp_path, monkeypatch):
    issued = _issue_grant(tmp_path, monkeypatch)

    with pytest.raises(DelegationError) as denied:
        DelegationGrantRegistry(issued["state_dir"]).validate_child(
            issued["grant"]["grant_id"],
            issued["child"],
            schedule_id=issued["schedule_id"],
            schedule_digest=stable_digest({"changed": True}),
        )
    assert denied.value.code == "delegation_schedule_digest_mismatch"


def test_revoked_grant_cannot_issue_child_permit(tmp_path, monkeypatch):
    issued = _issue_grant(tmp_path, monkeypatch)
    DelegationGrantRegistry(issued["state_dir"]).revoke(
        issued["grant"]["grant_id"],
        reason="test",
    )

    with pytest.raises(DelegationError) as denied:
        issued["boundary"].issue_delegated_permit(
            request=issued["child"],
            state_dir=issued["state_dir"],
            schedule_id=issued["schedule_id"],
            schedule_digest=issued["schedule_digest"],
        )
    assert denied.value.code == "delegation_revoked"


def test_expired_grant_fails_closed(tmp_path, monkeypatch):
    issued = _issue_grant(tmp_path, monkeypatch)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    monkeypatch.setattr(dg, "_now", lambda: future)

    with pytest.raises(DelegationError) as denied:
        DelegationGrantRegistry(issued["state_dir"]).validate_child(
            issued["grant"]["grant_id"],
            issued["child"],
            schedule_id=issued["schedule_id"],
            schedule_digest=issued["schedule_digest"],
        )
    assert denied.value.code == "delegation_expired"


def test_nondelegable_effect_cannot_be_granted(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    boundary = auth.AuthorizationBoundary()
    schedule_id = "schedule-delete"
    schedule_digest = stable_digest({"schedule_id": schedule_id})
    target = {"path": "danger.txt"}
    arguments = {}
    parent = build_execution_request(
        effect_id="schedule.delegate",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.schedule.delegate",
        target={"schedule_id": schedule_id, "schedule_digest": schedule_digest},
        arguments={
            "allowed_effects": ["filesystem.delete"],
            "target_digest": stable_digest(target),
            "arguments_digest": stable_digest(arguments),
            "scope": "workspace",
            "policy_version": REGISTRY.digest,
            "expires_at": _future(),
            "max_runs": 1,
            "child_actor_kind": "scheduler",
            "child_source_surface": "scheduler",
        },
        scope="persistent",
        policy_version=REGISTRY.digest,
    )
    challenge = boundary.create_challenge(parent, interaction_id="interaction-delete")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-delete",
        session_id=parent.session_id,
        channel="ui-react",
    )["permit"]

    with pytest.raises(DelegationError) as denied:
        ExecutionGateway(boundary).execute(
            permit_token=permit["token"],
            request=parent,
            context=ExecutionContext(services={"state_dir": tmp_path / "state"}),
        )
    assert denied.value.code == "delegation_effect_not_delegable"


def test_client_assertion_cannot_issue_grant_without_parent_authorization(tmp_path):
    request = build_execution_request(
        effect_id="schedule.delegate",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test",
        target={"schedule_id": "schedule-1", "schedule_digest": "abc"},
        arguments={},
        scope="persistent",
        policy_version=REGISTRY.digest,
    )
    fake = {
        "state": "consumed",
        "effect_id": "schedule.delegate",
        "operation_fingerprint": request.fingerprint,
        "proof": {
            "provenance": {"kind": "agent_asserted_authorization"},
        },
        "decision": {"result": "allow"},
    }

    with pytest.raises(DelegationError) as denied:
        DelegationGrantRegistry(tmp_path).issue_from_authorized_request(request, fake)
    assert denied.value.code == "delegation_user_origin_unverified"


def test_unconsumed_parent_assertion_cannot_issue_grant(tmp_path):
    request = build_execution_request(
        effect_id="schedule.delegate",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test",
        target={"schedule_id": "schedule-1", "schedule_digest": "abc"},
        arguments={},
        scope="persistent",
        policy_version=REGISTRY.digest,
    )
    fake = {
        "state": "active",
        "effect_id": request.effect_id,
        "operation_fingerprint": request.fingerprint,
        "proof": {
            "proof_id": "proof-fake",
            "operation_fingerprint": request.fingerprint,
            "provenance": {"kind": "direct_user_interaction"},
        },
        "decision": {"result": "allow"},
    }

    with pytest.raises(DelegationError) as denied:
        DelegationGrantRegistry(tmp_path).issue_from_authorized_request(request, fake)
    assert denied.value.code == "delegation_parent_permit_not_consumed"

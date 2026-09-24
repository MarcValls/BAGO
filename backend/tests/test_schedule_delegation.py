from __future__ import annotations

import inspect
import sys
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import authorization_boundary as auth
import capability_packages
import handlers_schedule
import delegation_grant as dg
import execution_gateway as eg
import schedule_registry as sr
from authorization_boundary import AuthorizationBoundary
from delegation_grant import DelegationError, DelegationGrantRegistry
from execution_gateway import ExecutionContext, ExecutionGateway, ExecutionGatewayError


@pytest.fixture(autouse=True)
def _bind_dynamic_p4_modules(monkeypatch):
    monkeypatch.setitem(sys.modules, "authorization_boundary", auth)
    monkeypatch.setitem(sys.modules, "capability_packages", capability_packages)
    monkeypatch.setitem(sys.modules, "delegation_grant", dg)
    monkeypatch.setitem(sys.modules, "execution_gateway", eg)
    monkeypatch.setitem(sys.modules, "handlers_schedule", handlers_schedule)
    monkeypatch.setitem(sys.modules, "schedule_registry", sr)


def _package():
    return {
        "id": "cap-1",
        "kind": "capability",
        "version": "1.0.0",
        "digest": "package-digest-1",
        "permissions": ["filesystem.read"],
    }


def _schedule_payload():
    return {
        "id": "schedule-cap-1",
        "name": "Capability periódica",
        "target_type": "capability",
        "target": {
            "capability_id": "cap-1",
            "input": {"query": "status"},
        },
        "schedule_type": "interval",
        "interval_s": 60,
        "timezone": "UTC",
        "enabled": True,
        "delegation": {
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "max_runs": 2,
        },
    }


def _materialize_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    monkeypatch.setattr(capability_packages, "get_package", lambda package_id: _package())

    mgr = SimpleNamespace(base_path=tmp_path, session_id="session-scheduler")
    payload = _schedule_payload()
    request, draft, requested_enabled, _ = handlers_schedule._delegation_request(mgr, payload)

    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="interaction-schedule")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-schedule",
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]
    result, _ = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(
            manager=mgr,
            services={"state_dir": handlers_schedule._state_dir(mgr)},
        ),
    )
    grant = result["delegation_grant"]
    schedule = handlers_schedule._registry(mgr).create(
        {
            **draft,
            "enabled": requested_enabled,
            "delegation_id": grant["grant_id"],
        }
    )
    return mgr, schedule, grant


def test_scheduler_executes_capability_only_through_child_permit(tmp_path, monkeypatch):
    calls = []

    def execute_package(package_id, *, inputs, confirmed, approved_permissions):
        calls.append(
            {
                "package_id": package_id,
                "inputs": inputs,
                "confirmed": confirmed,
                "approved_permissions": approved_permissions,
            }
        )
        return {
            "ok": True,
            "receipt": {"receipt_id": "receipt-cap-1"},
        }

    monkeypatch.setattr(capability_packages, "get_package", lambda package_id: _package())
    monkeypatch.setattr(capability_packages, "execute_package", execute_package)
    mgr, schedule, grant = _materialize_schedule(tmp_path, monkeypatch)

    # Legacy fields may be injected into a caller-owned copy, but are not authority.
    poisoned = {
        **schedule,
        "confirmed": True,
        "approved_permissions": ["process.execute", "filesystem.write"],
    }
    result = handlers_schedule._execute_target(mgr, poisoned)

    assert result["ok"] is True
    assert result["receipt_id"] == "receipt-cap-1"
    assert result["authorization"]["state"] == "consumed"
    assert result["authorization"]["delegation_id"] == grant["grant_id"]
    assert result["authorization"]["delegation_claim_id"].startswith("delegation-claim-")
    assert len(calls) == 1
    # Runtime compatibility receives package-owned permissions, never schedule-owned claims.
    assert calls[0]["approved_permissions"] == ["filesystem.read"]

    persisted = DelegationGrantRegistry(handlers_schedule._state_dir(mgr)).get(grant["grant_id"])
    assert persisted["run_count"] == 1


def test_revoked_schedule_grant_blocks_runtime_before_effect(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(capability_packages, "get_package", lambda package_id: _package())
    monkeypatch.setattr(
        capability_packages,
        "execute_package",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"ok": True},
    )
    mgr, schedule, grant = _materialize_schedule(tmp_path, monkeypatch)
    DelegationGrantRegistry(handlers_schedule._state_dir(mgr)).revoke(grant["grant_id"], reason="test")

    with pytest.raises(DelegationError) as denied:
        handlers_schedule._execute_target(mgr, schedule)
    assert denied.value.code == "delegation_revoked"
    assert calls == []


def test_dynamic_task_schedule_cannot_receive_persistent_authority(tmp_path):
    mgr = SimpleNamespace(base_path=tmp_path, session_id="session-scheduler")
    payload = {
        **_schedule_payload(),
        "id": "schedule-task-1",
        "target_type": "task",
        "target": {"task": "Generate whatever plan seems useful at runtime"},
    }

    with pytest.raises(DelegationError) as denied:
        handlers_schedule._delegation_request(mgr, payload)
    assert denied.value.code == "delegation_target_dynamic"


def test_scheduler_handler_contains_no_direct_package_runtime_call():
    source = inspect.getsource(handlers_schedule)
    assert "execute_package(" not in source
    assert "execute_pipeline_package(" not in source
    assert "confirmed=True" not in source


def test_scheduler_executes_governed_plan_through_gateway(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Plan periódico gobernado",
        "1. Crear archivo notes/scheduled.txt con contenido: scheduled",
    )
    plan_id = engine.register_plan(plan)
    mgr = SimpleNamespace(
        base_path=tmp_path,
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=tmp_path,
        session_id="session-scheduler",
        plan_engine=engine,
    )
    payload = {
        "id": "schedule-plan-1",
        "name": "Plan periódico",
        "target_type": "plan",
        "target": {"plan_id": plan_id},
        "schedule_type": "interval",
        "interval_s": 60,
        "timezone": "UTC",
        "enabled": True,
        "delegation": {
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "max_runs": 2,
        },
    }
    request, draft, requested_enabled, _ = handlers_schedule._delegation_request(mgr, payload)
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="interaction-plan")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-plan",
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]
    result, _ = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(
            manager=mgr,
            services={"state_dir": handlers_schedule._state_dir(mgr)},
        ),
    )
    grant = result["delegation_grant"]
    schedule = handlers_schedule._registry(mgr).create(
        {
            **draft,
            "enabled": requested_enabled,
            "delegation_id": grant["grant_id"],
        }
    )

    execution = handlers_schedule._execute_target(mgr, schedule)
    assert execution["ok"] is True
    assert execution["authorization"]["state"] == "consumed"
    assert execution["authorization"]["delegation_id"] == grant["grant_id"]
    assert execution["result"]["receipt_id"].startswith("plan-execute:sha256:")
    assert (tmp_path / "notes" / "scheduled.txt").read_text(encoding="utf-8") == "scheduled"
    assert plan.steps[0].status == "done"
    assert plan.governed_work["budget_consumed"] == 1

    persisted = DelegationGrantRegistry(handlers_schedule._state_dir(mgr)).get(grant["grant_id"])
    assert persisted["run_count"] == 1


def test_delegated_grant_revocation_between_plan_children_blocks_next_effect(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Plan delegado con revocación intermedia",
        "1. Crear archivo notes/delegated-first.txt con contenido: first\n"
        "2. Crear archivo notes/delegated-second.txt con contenido: second",
    )
    plan_id = engine.register_plan(plan)
    mgr = SimpleNamespace(
        base_path=tmp_path,
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=tmp_path,
        session_id="session-scheduler",
        plan_engine=engine,
    )
    payload = {
        "id": "schedule-plan-revoke-between",
        "name": "Plan delegado con revocación",
        "target_type": "plan",
        "target": {"plan_id": plan_id},
        "schedule_type": "interval",
        "interval_s": 60,
        "timezone": "UTC",
        "enabled": True,
        "delegation": {
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "max_runs": 2,
        },
    }

    request, draft, requested_enabled, _ = handlers_schedule._delegation_request(mgr, payload)
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="interaction-plan-revoke-between")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-plan-revoke-between",
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]
    issued, _ = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(
            manager=mgr,
            services={"state_dir": handlers_schedule._state_dir(mgr)},
        ),
    )
    grant = issued["delegation_grant"]
    schedule = handlers_schedule._registry(mgr).create(
        {
            **draft,
            "enabled": requested_enabled,
            "delegation_id": grant["grant_id"],
        }
    )

    original_nested = ExecutionGateway.execute_nested
    calls = {"count": 0}

    def revoke_after_first_child(self, **kwargs):
        calls["count"] += 1
        result = original_nested(self, **kwargs)
        if calls["count"] == 1:
            DelegationGrantRegistry(handlers_schedule._state_dir(mgr)).revoke(
                grant["grant_id"],
                reason="test_between_plan_children",
            )
        return result

    monkeypatch.setattr(ExecutionGateway, "execute_nested", revoke_after_first_child)
    execution = handlers_schedule._execute_target(mgr, schedule)

    assert execution["ok"] is False
    assert plan.steps[0].status == "done"
    assert plan.steps[1].status == "blocked"
    assert plan.steps[1].block_code == "delegation_revoked"
    assert (tmp_path / "notes" / "delegated-first.txt").read_text(encoding="utf-8") == "first"
    assert not (tmp_path / "notes" / "delegated-second.txt").exists()

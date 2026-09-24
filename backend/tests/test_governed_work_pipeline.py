from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import authorization_boundary as auth
from authorization_boundary import AuthorizationBoundary
from effect_registry import REGISTRY
from execution_gateway import ExecutionContext, ExecutionGateway, ExecutionGatewayError
from execution_request import build_execution_request
from plan_engine import PlanEngine


def _manager(tmp_path, engine: PlanEngine, *, session_id: str = "session-governed"):
    return SimpleNamespace(
        base_path=tmp_path,
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=tmp_path,
        session_id=session_id,
        plan_engine=engine,
    )


def _request(plan, *, session_id: str = "session-governed"):
    from governed_work_pipeline import plan_execution_target

    return build_execution_request(
        effect_id="plan.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=session_id,
        source_surface="test.governed-plan",
        target=plan_execution_target(plan),
        arguments={},
        scope=REGISTRY.get("plan.execute").default_scope,
        policy_version=REGISTRY.digest,
    )


def _permit(boundary: AuthorizationBoundary, request, interaction_id: str):
    challenge = boundary.create_challenge(request, interaction_id=interaction_id)
    return boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id=interaction_id,
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]


def _registered_plan(
    tmp_path,
    response: str,
    *,
    budget_limit: int | None = None,
):
    engine = PlanEngine()
    plan = engine.create_plan_with_actions("Plan gobernado", response)
    if budget_limit is not None:
        plan.governed_work = {"budget_limit": budget_limit}
    engine.register_plan(plan)
    return engine, plan, _manager(tmp_path, engine)


def test_plan_engine_material_effects_use_one_consumed_parent_permit(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine, plan, manager = _registered_plan(
        tmp_path,
        "1. Crear archivo notes/one.txt con contenido: one\n"
        "2. Leer archivo notes/one.txt",
    )
    request = _request(plan)
    boundary = AuthorizationBoundary()
    permit = _permit(boundary, request, "interaction-one-parent")

    result, authorization = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is True
    assert result["executed"] is True
    assert authorization["state"] == "consumed"
    assert all(step.status == "done" for step in plan.steps)
    assert (tmp_path / "notes" / "one.txt").read_text(encoding="utf-8") == "one"
    assert plan.governed_work["budget_consumed"] == 2
    assert plan.governed_work["budget_remaining"] == 0
    assert {item["outcome_status"] for item in plan.governed_work["outcomes"].values()} == {"COMMITTED"}
    assert all(
        item["attempt_permit_ref"] == authorization["permit_id"]
        for item in plan.governed_work["outcomes"].values()
    )

    ledger = json.loads(
        (tmp_path / "auth" / "authorization" / "ledger.json").read_text(encoding="utf-8")
    )
    assert len(ledger["permits"]) == 1
    assert next(iter(ledger["permits"].values()))["state"] == "consumed"


def test_workflow_mutation_after_authorization_is_rejected_before_child_effect(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine, plan, manager = _registered_plan(
        tmp_path,
        "1. Crear archivo notes/stale.txt con contenido: stale",
    )
    request = _request(plan)
    boundary = AuthorizationBoundary()
    permit = _permit(boundary, request, "interaction-stale-workflow")
    plan.steps[0].description = "Crear archivo notes/stale.txt con contenido: cambiado"

    with pytest.raises(ExecutionGatewayError) as stale:
        ExecutionGateway(boundary).execute(
            permit_token=permit["token"],
            request=request,
            context=ExecutionContext(manager=manager),
        )

    assert stale.value.code == "workflow_definition_stale"
    assert not (tmp_path / "notes" / "stale.txt").exists()
    assert plan.governed_work["budget_consumed"] == 0
    assert plan.steps[0].status == "pending"


def test_budget_envelope_is_monotonic_and_blocks_after_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine, plan, manager = _registered_plan(
        tmp_path,
        "1. Crear archivo notes/first.txt con contenido: first\n"
        "2. Crear archivo notes/second.txt con contenido: second",
        budget_limit=1,
    )
    request = _request(plan)
    boundary = AuthorizationBoundary()
    permit = _permit(boundary, request, "interaction-budget")

    result, _ = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is False
    assert result["plan_result"]["executed"] == 1
    assert result["plan_result"]["blocked"] == 1
    assert plan.steps[0].status == "done"
    assert plan.steps[1].status == "blocked"
    assert plan.steps[1].block_code == "pipeline_budget_exhausted"
    assert (tmp_path / "notes" / "first.txt").read_text(encoding="utf-8") == "first"
    assert not (tmp_path / "notes" / "second.txt").exists()
    assert plan.governed_work["budget_consumed"] == 1
    assert plan.governed_work["budget_remaining"] == 0
    assert plan.governed_work["budget_state"] == "EXHAUSTED"
    assert len(plan.governed_work["outcomes"]) == 1


def test_invalid_explicit_budget_is_rejected_fail_closed(tmp_path):
    from governed_work_pipeline import GovernedWorkError

    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Plan con presupuesto inválido",
        "1. Crear archivo notes/invalid-budget.txt con contenido: no",
    )
    plan.governed_work = {"budget_limit": 0}

    with pytest.raises(GovernedWorkError) as invalid:
        engine.register_plan(plan)

    assert getattr(invalid.value, "code", "") == "pipeline_budget_invalid"


def test_unknown_outcome_blocks_automatic_retry_without_refilling_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine, plan, manager = _registered_plan(
        tmp_path,
        "1. Crear archivo notes/ambiguous.txt con contenido: ambiguous",
    )
    boundary = AuthorizationBoundary()
    gateway = ExecutionGateway(boundary)
    request = _request(plan)
    first_permit = _permit(boundary, request, "interaction-unknown-1")

    def ambiguous_dispatch(self, **kwargs):
        raise RuntimeError("transport ended after dispatch")

    monkeypatch.setattr(ExecutionGateway, "execute_nested", ambiguous_dispatch)
    first, _ = gateway.execute(
        permit_token=first_permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert first["ok"] is False
    assert first["block_code"] == "pipeline_outcome_unknown"
    assert plan.governed_work["budget_consumed"] == 1
    assert plan.governed_work["budget_remaining"] == 0
    assert list(plan.governed_work["outcomes"].values())[0]["outcome_status"] == "OUTCOME_UNKNOWN"
    assert not (tmp_path / "notes" / "ambiguous.txt").exists()

    plan.steps[0].status = "pending"
    plan.steps[0].block_reason = ""
    plan.steps[0].block_code = ""
    second_request = _request(plan)
    second_permit = _permit(boundary, second_request, "interaction-unknown-2")
    second, _ = gateway.execute(
        permit_token=second_permit["token"],
        request=second_request,
        context=ExecutionContext(manager=manager),
    )

    assert second["ok"] is False
    assert second["block_code"] == "pipeline_outcome_unknown"
    assert plan.governed_work["budget_consumed"] == 1
    assert plan.governed_work["budget_remaining"] == 0
    assert len(plan.governed_work["outcomes"]) == 1


def test_durable_pending_write_is_reapplied_idempotently_and_reconciled(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine, plan, manager = _registered_plan(
        tmp_path,
        "1. Crear archivo notes/reconcile.txt con contenido: desired-state",
    )
    manager.state_root = tmp_path / "session-state"
    boundary = AuthorizationBoundary()
    gateway = ExecutionGateway(boundary)
    request = _request(plan)
    permit = _permit(boundary, request, "interaction-reconcile-first")
    import filesystem_effects
    original_write = filesystem_effects.write_file_effect

    def write_then_disconnect(*args, **kwargs):
        original_write(*args, **kwargs)
        raise RuntimeError("caller lost the receipt after file replacement")

    monkeypatch.setattr(filesystem_effects, "write_file_effect", write_then_disconnect)
    first, _ = gateway.execute(
        permit_token=permit["token"], request=request,
        context=ExecutionContext(manager=manager),
    )
    target = tmp_path / "notes" / "reconcile.txt"
    assert first["block_code"] == "pipeline_outcome_unknown"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "desired-state"

    plan.steps[0].status = "pending"
    plan.steps[0].block_reason = ""
    plan.steps[0].block_code = ""
    retry_request = _request(plan)
    retry_permit = _permit(boundary, retry_request, "interaction-reconcile-retry")
    monkeypatch.setattr(filesystem_effects, "write_file_effect", original_write)
    second, _ = gateway.execute(
        permit_token=retry_permit["token"], request=retry_request,
        context=ExecutionContext(manager=manager),
    )

    outcome = next(iter(plan.governed_work["outcomes"].values()))
    from execution_operations import SQLiteExecutionOperationStore

    operation = SQLiteExecutionOperationStore(
        manager.state_root / "execution_claims.sqlite3"
    ).get(outcome["step_idempotency_key"])
    assert second["ok"] is True
    assert target.read_text(encoding="utf-8") == "desired-state"
    assert outcome["outcome_status"] == "COMMITTED"
    assert operation["status"] == "COMMITTED"
    assert operation["receipt"]["receipt_id"] == outcome["outcome_receipt_ref"]


def test_concurrent_duplicate_parent_authorizations_materialize_one_child(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine, plan, manager = _registered_plan(
        tmp_path,
        "1. Crear archivo notes/concurrent.txt con contenido: once",
    )
    boundary = AuthorizationBoundary()
    gateway = ExecutionGateway(boundary)
    requests = [_request(plan), _request(plan)]
    permits = [
        _permit(boundary, request, f"interaction-concurrent-{index}")
        for index, request in enumerate(requests)
    ]

    def run(index: int):
        return gateway.execute(
            permit_token=permits[index]["token"],
            request=requests[index],
            context=ExecutionContext(manager=manager),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))

    assert sorted(bool(result[0]["executed"]) for result in results) == [False, True]
    assert sum(bool(result[0].get("replayed")) for result in results) == 1
    assert (tmp_path / "notes" / "concurrent.txt").read_text(encoding="utf-8") == "once"
    assert plan.governed_work["budget_consumed"] == 1
    assert len(plan.governed_work["outcomes"]) == 1
    assert next(iter(plan.governed_work["outcomes"].values()))["outcome_status"] == "COMMITTED"


def test_unsupported_child_is_blocked_before_budget_or_authority_expansion(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine, plan, manager = _registered_plan(
        tmp_path,
        "1. Ejecutar echo no debe ejecutarse",
    )
    request = _request(plan)
    boundary = AuthorizationBoundary()
    permit = _permit(boundary, request, "interaction-unsupported-child")

    result, _ = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is False
    assert result["block_code"] == "plan_child_adapter_missing"
    assert plan.steps[0].status == "blocked"
    assert plan.steps[0].block_code == "plan_child_adapter_missing"
    assert plan.governed_work["budget_consumed"] == 0
    assert plan.governed_work["outcomes"] == {}


def test_nested_dispatch_cannot_be_called_without_gateway_owned_context(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    _, plan, _ = _registered_plan(
        tmp_path,
        "1. Crear archivo notes/no-bypass.txt con contenido: no",
    )
    request = _request(plan)
    gateway = ExecutionGateway(AuthorizationBoundary())
    caller_supplied_authorization = {
        "state": "consumed",
        "effect_id": "plan.execute",
        "operation_fingerprint": request.fingerprint,
    }

    with pytest.raises(ExecutionGatewayError) as bypass:
        gateway.execute_nested(
            parent_request=request,
            child_request=request,
            context=ExecutionContext(services={"_authorization": caller_supplied_authorization}),
        )

    assert bypass.value.code == "execution_nested_gateway_context_missing"

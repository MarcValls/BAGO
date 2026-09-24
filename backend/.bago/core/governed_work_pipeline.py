"""04-FIX2 runtime sidecar for bounded PlanEngine work.

This module owns coordination metadata only.  It never creates, expands,
consumes, or revokes authority.  The parent ``plan.execute`` Permit is owned
by 03A/AuthorizationBoundary; material child effects are dispatched by the
ExecutionGateway through its server-owned adapters.
"""

from __future__ import annotations

import hashlib
import json
from threading import RLock
from typing import Any

from effect_registry import REGISTRY
from execution_request import build_execution_request, stable_digest


GOVERNED_WORK_CONTRACT = "bago.governed-work-pipeline/v0.2-FIX2"
WORKFLOW_VERSION = "04-FIX2"
OUTCOME_PENDING = "PENDING"
OUTCOME_COMMITTED = "COMMITTED"
OUTCOME_FAILED = "FAILED"
OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
OUTCOME_STATUSES = frozenset({
    OUTCOME_PENDING,
    OUTCOME_COMMITTED,
    OUTCOME_FAILED,
    OUTCOME_UNKNOWN,
})


class GovernedWorkError(RuntimeError):
    """Fail-closed contract error with a stable code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _json_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _step_id(step: Any) -> str:
    return f"step-{int(getattr(step, 'number', 0) or 0)}"


def _step_definition(step: Any) -> dict[str, Any]:
    return {
        "number": int(getattr(step, "number", 0) or 0),
        "description": str(getattr(step, "description", "") or ""),
        "action": str(getattr(step, "action", "") or ""),
        "action_payload": dict(getattr(step, "action_payload", {}) or {}),
    }


def step_definition_fingerprint(step: Any) -> str:
    return _json_digest(_step_definition(step))


def workflow_definition_fingerprint(plan: Any) -> str:
    definition = {
        "task": str(getattr(plan, "task", "") or ""),
        "steps": [_step_definition(step) for step in list(getattr(plan, "steps", ()) or ())],
    }
    return _json_digest(definition)


def _material_child(step: Any, contract: dict[str, Any]) -> tuple[str | None, dict[str, Any], dict[str, Any]]:
    action = str(getattr(step, "action", "") or "").strip()
    payload = dict(getattr(step, "action_payload", {}) or {})
    pipeline = {
        "pipeline_operation_id": str(contract["pipeline_operation_id"]),
        "step_id": _step_id(step),
    }
    if action == "write_file":
        return (
            "filesystem.write",
            {"path": str(payload.get("path") or ""), "_pipeline": pipeline},
            {"content": str(payload.get("content") or "")},
        )
    if action == "read_file":
        return (
            "filesystem.read",
            {"path": str(payload.get("path") or ""), "_pipeline": pipeline},
            {},
        )
    if action == "run_command":
        return (
            "process.execute",
            {"command": str(payload.get("command") or ""), "_pipeline": pipeline},
            {},
        )
    return None, {}, {}


def _step_descriptor(step: Any, contract: dict[str, Any]) -> dict[str, Any] | None:
    effect_id, target, arguments = _material_child(step, contract)
    if not effect_id:
        return None
    try:
        scope = REGISTRY.get(effect_id).default_scope
    except Exception as exc:  # pragma: no cover - registry is validated at import
        raise GovernedWorkError(
            f"Effect child desconocido: {effect_id}",
            code="pipeline_child_effect_unknown",
        ) from exc
    step_fp = step_definition_fingerprint(step)
    return {
        "step_id": _step_id(step),
        "step_number": int(getattr(step, "number", 0) or 0),
        "effect_id": effect_id,
        "scope": scope,
        "target_digest": stable_digest(target),
        "arguments_digest": stable_digest(arguments),
        "step_definition_fingerprint": step_fp,
        "step_idempotency_key_prefix": (
            f"{contract['pipeline_operation_id']}:{_step_id(step)}:attempt:"
        ),
    }


def _binding_payload(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": contract["contract"],
        "pipeline_budget_envelope_id": contract["pipeline_budget_envelope_id"],
        "budget_limit": contract["budget_limit"],
        "workflow_definition_id": contract["workflow_definition_id"],
        "workflow_version": contract["workflow_version"],
        "workflow_fingerprint": contract["workflow_fingerprint"],
        "step_definition_fingerprints": contract["step_definition_fingerprints"],
        "step_definition_fingerprint": contract["step_definition_fingerprint"],
        "pipeline_operation_id": contract["pipeline_operation_id"],
    }


class GovernedPipelineState:
    """Mutable per-plan 04 sidecar with serialized, inspectable state."""

    def __init__(self, plan: Any) -> None:
        self.plan = plan
        self.lock = RLock()
        self.execution_lock = RLock()

    def _initialize(self) -> dict[str, Any]:
        plan_id = str(getattr(self.plan, "id", "") or "").strip()
        if not plan_id:
            raise GovernedWorkError("El plan necesita id para 04-FIX2", code="pipeline_plan_id_required")
        existing = getattr(self.plan, "governed_work", {})
        existing = dict(existing) if isinstance(existing, dict) else {}
        material_count = sum(
            1
            for step in list(getattr(self.plan, "steps", ()) or ())
            if _material_child(step, {"pipeline_operation_id": "bootstrap"})[0]
        )
        raw_budget_limit = existing["budget_limit"] if "budget_limit" in existing else (material_count or 1)
        try:
            budget_limit = int(raw_budget_limit)
            budget_consumed = int(existing.get("budget_consumed", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise GovernedWorkError("budget_limit inválido", code="pipeline_budget_invalid") from exc
        if budget_limit < 1:
            raise GovernedWorkError("budget_limit debe ser mayor que cero", code="pipeline_budget_invalid")

        step_fps = {
            _step_id(step): step_definition_fingerprint(step)
            for step in list(getattr(self.plan, "steps", ()) or ())
        }
        workflow_fp = workflow_definition_fingerprint(self.plan)
        contract = {
            "contract": GOVERNED_WORK_CONTRACT,
            "pipeline_budget_envelope_id": str(existing.get("pipeline_budget_envelope_id") or f"pipeline-budget:{plan_id}"),
            "budget_limit": budget_limit,
            "budget_consumed": budget_consumed,
            "budget_remaining": 0,
            "budget_state": "AVAILABLE",
            "workflow_definition_id": str(existing.get("workflow_definition_id") or f"workflow:{plan_id}"),
            "workflow_version": str(existing.get("workflow_version") or WORKFLOW_VERSION),
            "workflow_fingerprint": workflow_fp,
            "step_definition_fingerprints": step_fps,
            "step_definition_fingerprint": _json_digest(step_fps),
            "pipeline_operation_id": str(existing.get("pipeline_operation_id") or f"pipeline-operation:{plan_id}"),
            "outcomes": dict(existing.get("outcomes") or {}),
            "last_execution": dict(existing.get("last_execution") or {}),
        }
        if contract["budget_consumed"] < 0 or contract["budget_consumed"] > budget_limit:
            raise GovernedWorkError("budget_consumed fuera de rango", code="pipeline_budget_invalid")
        contract["budget_remaining"] = budget_limit - contract["budget_consumed"]
        contract["budget_state"] = "EXHAUSTED" if contract["budget_consumed"] >= budget_limit else "AVAILABLE"
        contract["binding_digest"] = _json_digest(_binding_payload(contract))
        self.plan.governed_work = contract
        return contract

    def ensure(self) -> dict[str, Any]:
        with self.lock:
            current = getattr(self.plan, "governed_work", {})
            if not isinstance(current, dict) or not current.get("workflow_fingerprint"):
                return self._initialize()
            contract = current
            expected_fp = workflow_definition_fingerprint(self.plan)
            if str(contract.get("workflow_fingerprint") or "") != expected_fp:
                raise GovernedWorkError(
                    "La definición del workflow cambió después del prepare",
                    code="workflow_definition_stale",
                )
            try:
                budget_limit = int(contract["budget_limit"])
                budget_consumed = int(contract["budget_consumed"])
                budget_remaining = int(contract["budget_remaining"])
            except (KeyError, TypeError, ValueError) as exc:
                raise GovernedWorkError(
                    "El envelope de presupuesto está incompleto",
                    code="pipeline_budget_invalid",
                ) from exc
            if budget_limit < 1 or budget_consumed < 0 or budget_consumed > budget_limit:
                raise GovernedWorkError(
                    "El envelope de presupuesto está fuera de rango",
                    code="pipeline_budget_invalid",
                )
            expected_remaining = budget_limit - budget_consumed
            expected_state = "EXHAUSTED" if budget_consumed >= budget_limit else "AVAILABLE"
            if budget_remaining != expected_remaining or str(contract.get("budget_state") or "") != expected_state:
                raise GovernedWorkError(
                    "budget_remaining o budget_state no coincide con el consumo",
                    code="pipeline_budget_invalid",
                )
            if str(contract.get("binding_digest") or "") != _json_digest(_binding_payload(contract)):
                raise GovernedWorkError(
                    "El contrato 04-FIX2 fue alterado fuera de su owner",
                    code="pipeline_contract_tampered",
                )
            return contract

    def public(self) -> dict[str, Any]:
        with self.lock:
            contract = self.ensure()
            return json.loads(json.dumps(contract, ensure_ascii=False, sort_keys=True))

    def begin_attempt(self, step: Any, authority: dict[str, str]) -> dict[str, Any]:
        with self.lock:
            contract = self.ensure()
            step_id = _step_id(step)
            for previous in contract["outcomes"].values():
                if (
                    isinstance(previous, dict)
                    and previous.get("step_id") == step_id
                    and previous.get("outcome_status") == OUTCOME_UNKNOWN
                ):
                    raise GovernedWorkError(
                        "OUTCOME_UNKNOWN requiere resolución explícita antes de retry",
                        code="pipeline_outcome_unknown",
                    )
            attempt = int(getattr(step, "attempt", 0) or 0) + 1
            step_fp = step_definition_fingerprint(step)
            key = f"{contract['pipeline_operation_id']}:{step_id}:attempt:{attempt}:{step_fp[:16]}"
            existing = contract["outcomes"].get(key)
            if isinstance(existing, dict):
                status = str(existing.get("outcome_status") or "")
                if status == OUTCOME_UNKNOWN:
                    raise GovernedWorkError(
                        "OUTCOME_UNKNOWN no puede reintentarse automáticamente",
                        code="pipeline_outcome_unknown",
                    )
                return {"replay": True, "outcome": dict(existing), "step_idempotency_key": key}
            if int(contract.get("budget_consumed", 0) or 0) >= int(contract["budget_limit"]):
                contract["budget_remaining"] = 0
                contract["budget_state"] = "EXHAUSTED"
                raise GovernedWorkError(
                    "PipelineBudgetEnvelope agotado",
                    code="pipeline_budget_exhausted",
                )
            step.attempt = attempt
            contract["budget_consumed"] = int(contract.get("budget_consumed", 0) or 0) + 1
            contract["budget_remaining"] = int(contract["budget_limit"]) - contract["budget_consumed"]
            contract["budget_state"] = (
                "EXHAUSTED"
                if contract["budget_consumed"] >= int(contract["budget_limit"])
                else "AVAILABLE"
            )
            outcome = {
                "pipeline_operation_id": contract["pipeline_operation_id"],
                "step_id": step_id,
                "step_idempotency_key": key,
                "step_definition_fingerprint": step_fp,
                "attempt": attempt,
                "outcome_status": OUTCOME_PENDING,
                "outcome_receipt_ref": "",
                "result": {},
                "evidence": [],
                **authority,
            }
            contract["outcomes"][key] = outcome
            return {"replay": False, "outcome": dict(outcome), "step_idempotency_key": key}

    def commit(self, key: str, *, result: Any, evidence: list[str], receipt_id: str) -> None:
        with self.lock:
            contract = self.ensure()
            record = contract["outcomes"].get(key)
            if not isinstance(record, dict):
                raise GovernedWorkError("Outcome inexistente", code="pipeline_outcome_missing")
            record["outcome_status"] = OUTCOME_COMMITTED
            record["outcome_receipt_ref"] = str(receipt_id or "")
            record["result"] = result if isinstance(result, (dict, list, str, int, float, bool)) or result is None else str(result)
            record["evidence"] = list(evidence)

    def fail(self, key: str, *, result: Any, evidence: list[str], error: str) -> None:
        with self.lock:
            contract = self.ensure()
            record = contract["outcomes"].get(key)
            if not isinstance(record, dict):
                raise GovernedWorkError("Outcome inexistente", code="pipeline_outcome_missing")
            record["outcome_status"] = OUTCOME_FAILED
            record["result"] = result if isinstance(result, (dict, list, str, int, float, bool)) or result is None else str(result)
            record["error"] = str(error or "")
            record["evidence"] = list(evidence)

    def unknown(self, key: str, *, error: str, evidence: list[str]) -> None:
        with self.lock:
            contract = self.ensure()
            record = contract["outcomes"].get(key)
            if not isinstance(record, dict):
                raise GovernedWorkError("Outcome inexistente", code="pipeline_outcome_missing")
            record["outcome_status"] = OUTCOME_UNKNOWN
            record["error"] = str(error or "")
            record["evidence"] = list(evidence)

    def remember_execution(self, record: dict[str, Any]) -> None:
        with self.lock:
            self.ensure()["last_execution"] = dict(record)


def ensure_pipeline_state(plan: Any) -> GovernedPipelineState:
    runtime = getattr(plan, "_governed_runtime", None)
    if not isinstance(runtime, GovernedPipelineState) or runtime.plan is not plan:
        runtime = GovernedPipelineState(plan)
        setattr(plan, "_governed_runtime", runtime)
    runtime.ensure()
    return runtime


def plan_execution_target(plan: Any) -> dict[str, Any]:
    state = ensure_pipeline_state(plan)
    contract = state.ensure()
    child_effects = [
        descriptor
        for step in list(getattr(plan, "steps", ()) or ())
        if (descriptor := _step_descriptor(step, contract)) is not None
    ]
    return {
        "plan_id": str(getattr(plan, "id", "") or ""),
        "pipeline_budget_envelope_id": contract["pipeline_budget_envelope_id"],
        "budget_limit": contract["budget_limit"],
        "workflow_definition_id": contract["workflow_definition_id"],
        "workflow_version": contract["workflow_version"],
        "workflow_fingerprint": contract["workflow_fingerprint"],
        "step_definition_fingerprint": contract["step_definition_fingerprint"],
        "pipeline_operation_id": contract["pipeline_operation_id"],
        "child_effects": child_effects,
    }


def validate_plan_execution_target(plan: Any, target: dict[str, Any]) -> GovernedPipelineState:
    state = ensure_pipeline_state(plan)
    contract = state.ensure()
    expected = plan_execution_target(plan)
    if not isinstance(target, dict):
        raise GovernedWorkError("Target de plan inválido", code="pipeline_target_invalid")
    for key in (
        "plan_id",
        "pipeline_budget_envelope_id",
        "budget_limit",
        "workflow_definition_id",
        "workflow_version",
        "workflow_fingerprint",
        "step_definition_fingerprint",
        "pipeline_operation_id",
    ):
        if target.get(key) != expected.get(key):
            raise GovernedWorkError(
                f"Binding 04-FIX2 stale en {key}",
                code="pipeline_precondition_stale",
            )
    if target.get("child_effects") != expected.get("child_effects"):
        raise GovernedWorkError(
            "La definición de steps cambió después del prepare",
            code="workflow_definition_stale",
        )
    return state


def authority_references(request: Any, authorization: dict[str, Any]) -> dict[str, str]:
    if not isinstance(authorization, dict) or str(authorization.get("state") or "") != "consumed":
        raise GovernedWorkError(
            "04-FIX2 requiere referencias de autoridad consumida por 03A",
            code="authority_reference_missing",
        )
    proof = authorization.get("proof") if isinstance(authorization.get("proof"), dict) else {}
    provenance = proof.get("provenance") if isinstance(proof.get("provenance"), dict) else {}
    grant_id = str(provenance.get("grant_id") or getattr(request, "delegation_id", "") or "").strip()
    proof_id = str(authorization.get("proof_id") or proof.get("proof_id") or "").strip()
    decision_id = str(authorization.get("decision_id") or (authorization.get("decision") or {}).get("decision_id") or "").strip()
    permit_id = str(authorization.get("permit_id") or "").strip()
    if not proof_id or not decision_id or not permit_id:
        raise GovernedWorkError(
            "Las referencias de autoridad del attempt están incompletas",
            code="authority_reference_incomplete",
        )
    chain = f"delegation:{grant_id}" if grant_id else f"direct:{proof_id}"
    snapshot = _json_digest({
        "operation_fingerprint": str(authorization.get("operation_fingerprint") or ""),
        "permit_id": permit_id,
        "decision_id": decision_id,
        "proof_id": proof_id,
        "delegation_id": str(getattr(request, "delegation_id", "") or ""),
    })
    return {
        "delegation_chain_ref": chain,
        "authority_snapshot_fingerprint": snapshot,
        "attempt_permit_ref": permit_id,
        "attempt_decision_ref": decision_id,
    }


def _replayed_outcome(record: dict[str, Any]) -> dict[str, Any]:
    status = str(record.get("outcome_status") or "")
    ok = status == OUTCOME_COMMITTED
    return {
        "ok": ok,
        "executed": ok,
        "replayed": True,
        "result": record.get("result", {}),
        "error": str(record.get("error") or "") if not ok else "",
        "evidence": list(record.get("evidence") or []) + ["outcome_replayed"],
        "receipt_id": str(record.get("outcome_receipt_ref") or ""),
    }


def execute_plan_through_gateway(
    *,
    plan: Any,
    engine: Any,
    parent_request: Any,
    authorization: dict[str, Any],
    gateway: Any,
    context: Any,
) -> dict[str, Any]:
    """Run a plan under one consumed parent Permit and gateway child dispatch."""

    state = validate_plan_execution_target(plan, parent_request.target)
    contract = state.ensure()
    authority = authority_references(parent_request, authorization)

    def _blocked(error: str, code: str) -> dict[str, Any]:
        return {
            "ok": False,
            "executed": False,
            "result": "",
            "error": error,
            "evidence": ["blocked", f"code:{code}"],
            "receipt_id": "",
            "blocked": True,
            "block_code": code,
        }

    def _executor(action: str, payload: dict[str, Any], step: Any) -> dict[str, Any]:
        effect_id, target, arguments = _material_child(step, contract)
        if not effect_id:
            return _blocked("action_not_material", "non_material_action")
        try:
            gateway.adapters.resolve(effect_id)
        except Exception:
            return _blocked(
                "plan_child_gateway_unavailable",
                "plan_child_adapter_missing",
            )

        try:
            started = state.begin_attempt(step, authority)
        except GovernedWorkError as exc:
            return _blocked(str(exc), exc.code)
        if started.get("replay"):
            return _replayed_outcome(dict(started["outcome"]))

        key = str(started["step_idempotency_key"])
        pipeline_target = dict(target.get("_pipeline") or {})
        preconditions = (
            f"pipeline_operation_id:{contract['pipeline_operation_id']}",
            f"step_id:{_step_id(step)}",
            f"step_idempotency_key:{key}",
            f"step_definition_fingerprint:{step_definition_fingerprint(step)}",
            f"workflow_fingerprint:{contract['workflow_fingerprint']}",
        )
        child_request = build_execution_request(
            effect_id=effect_id,
            actor_kind=str(getattr(parent_request, "actor_kind", "plan") or "plan"),
            principal_id=str(getattr(parent_request, "principal_id", "") or ""),
            session_id=str(getattr(parent_request, "session_id", "") or ""),
            source_surface="plan.runtime",
            target={**target, "_pipeline": pipeline_target},
            arguments=arguments,
            scope=REGISTRY.get(effect_id).default_scope,
            policy_version=str(getattr(parent_request, "policy_version", "") or REGISTRY.digest),
            parent_execution_id=str(getattr(parent_request, "request_id", "") or ""),
            delegation_id=str(getattr(parent_request, "delegation_id", "") or ""),
            preconditions=preconditions,
        )
        try:
            child_result, _ = gateway.execute_nested(
                parent_request=parent_request,
                child_request=child_request,
                context=context,
            )
        except Exception as exc:
            error_code = str(getattr(exc, "code", "") or "")
            if error_code.startswith("authorization_") or error_code.startswith("delegation_"):
                evidence = [
                    "blocked",
                    "authority_revalidation_failed",
                    f"code:{error_code}",
                    f"step_idempotency_key:{key}",
                ]
                state.fail(key, result={}, evidence=evidence, error=str(exc))
                return _blocked(str(exc), error_code)
            evidence = ["blocked", "outcome_status:OUTCOME_UNKNOWN", f"step_idempotency_key:{key}"]
            state.unknown(key, error=str(exc), evidence=evidence)
            return _blocked("plan_child_outcome_unknown", "pipeline_outcome_unknown")

        result = dict(child_result) if isinstance(child_result, dict) else {"result": child_result}
        evidence = [str(item) for item in result.get("evidence", []) if str(item)]
        evidence.extend([
            f"pipeline_operation_id:{contract['pipeline_operation_id']}",
            f"workflow_fingerprint:{contract['workflow_fingerprint']}",
            f"step_idempotency_key:{key}",
            f"delegation_chain_ref:{authority['delegation_chain_ref']}",
        ])
        receipt_id = str(result.get("receipt_id") or "").strip()
        if bool(result.get("ok")) and bool(result.get("executed")) and receipt_id:
            state.commit(key, result=result, evidence=evidence, receipt_id=receipt_id)
            return {
                "ok": True,
                "executed": True,
                "result": result,
                "error": "",
                "evidence": evidence,
                "receipt_id": receipt_id,
            }

        error = str(result.get("error") or "plan_child_failed")
        state.fail(key, result=result, evidence=evidence or ["failed"], error=error)
        return {
            "ok": False,
            "executed": False,
            "result": result,
            "error": error,
            "evidence": evidence or ["failed"],
            "receipt_id": "",
        }

    with state.execution_lock:
        previous_executor = getattr(engine, "_executor", None)
        previous_plan = getattr(engine, "current_plan", None)
        engine.current_plan = plan
        engine.set_executor(_executor)
        try:
            plan_result = engine.execute_plan(plan, stop_on_failure=True)
        finally:
            engine.set_executor(previous_executor)
            engine.current_plan = previous_plan

        prior = contract.get("last_execution") if isinstance(contract.get("last_execution"), dict) else {}
        if plan_result.get("error") == "no_new_actions" and prior:
            replay = dict(prior)
            replay["executed"] = False
            replay["replayed"] = True
            replay["evidence"] = list(replay.get("evidence") or []) + ["no_new_actions"]
            replay["plan_result"] = plan_result
            return replay

        outcome_material = {
            "pipeline_operation_id": contract["pipeline_operation_id"],
            "workflow_fingerprint": contract["workflow_fingerprint"],
            "budget_consumed": contract["budget_consumed"],
            "plan_result": plan_result,
            "outcomes": contract["outcomes"],
        }
        plan_receipt = "plan-execute:sha256:" + _json_digest(outcome_material)
        evidence = [
            f"pipeline_operation_id:{contract['pipeline_operation_id']}",
            f"workflow_fingerprint:{contract['workflow_fingerprint']}",
            f"budget_consumed:{contract['budget_consumed']}",
            f"budget_state:{contract['budget_state']}",
            f"authority_snapshot_fingerprint:{authority['authority_snapshot_fingerprint']}",
        ]
        block_codes = [
            str(getattr(step, "block_code", "") or "")
            for step in list(getattr(plan, "steps", ()) or ())
            if str(getattr(step, "block_code", "") or "")
        ]
        last = {
            "ok": bool(plan_result.get("ok")),
            "executed": bool(plan_result.get("executed")),
            "result": plan_result,
            "plan_result": plan_result,
            "evidence": evidence,
            "receipt_id": plan_receipt,
            "workflow_fingerprint": contract["workflow_fingerprint"],
        }
        if block_codes:
            last["block_code"] = block_codes[-1]
        state.remember_execution(last)
        return last


__all__ = [
    "GOVERNED_WORK_CONTRACT",
    "GovernedPipelineState",
    "GovernedWorkError",
    "OUTCOME_COMMITTED",
    "OUTCOME_FAILED",
    "OUTCOME_PENDING",
    "OUTCOME_UNKNOWN",
    "WORKFLOW_VERSION",
    "authority_references",
    "ensure_pipeline_state",
    "execute_plan_through_gateway",
    "plan_execution_target",
    "step_definition_fingerprint",
    "validate_plan_execution_target",
    "workflow_definition_fingerprint",
]

"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from typing import Any
from execution_request import ExecutionRequest


class PlanRuntimeEffectAdapter:
    """Governed 04-FIX2 adapter for PlanEngine execution."""

    effect_ids = frozenset({"plan.execute"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from governed_work_pipeline import GovernedWorkError, execute_plan_through_gateway

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Plan execution requires SessionManager context",
                code="execution_context_manager_required",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict):
            raise ExecutionGatewayError(
                "Plan execution requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        gateway = context.services.get("_gateway")
        if not all(
            callable(getattr(gateway, name, None))
            for name in ("claim_store_for", "execute_nested")
        ) or not callable(getattr(getattr(gateway, "adapters", None), "resolve", None)):
            raise ExecutionGatewayError(
                "Plan execution requires the active ExecutionGateway",
                code="execution_gateway_context_required",
            )
        engine = getattr(manager, "plan_engine", None)
        if engine is None:
            raise ExecutionGatewayError(
                "PlanEngine no disponible",
                code="plan_engine_missing",
            )
        plan_id = str(request.target.get("plan_id") or "").strip()
        plan = engine.get_plan(plan_id)
        if plan is None:
            raise ExecutionGatewayError(
                f"Plan no encontrado: {plan_id}",
                code="plan_not_found",
            )
        try:
            return execute_plan_through_gateway(
                plan=plan,
                engine=engine,
                parent_request=request,
                authorization=authorization,
                gateway=gateway,
                context=context,
            )
        except GovernedWorkError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc

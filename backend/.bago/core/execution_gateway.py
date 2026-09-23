"""Closed execution gateway for governed BAGO effects.

Callers submit an ExecutionRequest plus a Permit. They cannot supply a callable.
The gateway resolves the executable adapter from a server-owned registry keyed
by canonical effect_id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from authorization_boundary import AuthorizationBoundary
from effect_registry import REGISTRY
from execution_request import ExecutionRequest


class ExecutionGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "execution_gateway_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Trusted runtime dependencies, never part of user authority."""

    manager: Any = None
    services: Mapping[str, Any] = field(default_factory=dict)


class EffectAdapter(Protocol):
    effect_ids: frozenset[str]

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        ...


class EffectAdapterRegistry:
    """Server-owned mapping from effect_id to implementation."""

    def __init__(self) -> None:
        self._by_effect: dict[str, EffectAdapter] = {}

    def register(self, adapter: EffectAdapter) -> None:
        effect_ids = getattr(adapter, "effect_ids", frozenset())
        if not effect_ids:
            raise ExecutionGatewayError(
                "Effect adapter must declare at least one effect_id",
                code="execution_adapter_effects_required",
            )
        for effect_id in effect_ids:
            clean = str(effect_id or "").strip()
            if not clean:
                raise ExecutionGatewayError(
                    "Effect adapter contains an empty effect_id",
                    code="execution_adapter_effect_invalid",
                )
            if not REGISTRY.contains(clean):
                raise ExecutionGatewayError(
                    f"Effect adapter declares unknown canonical effect_id {clean}",
                    code="execution_adapter_effect_unknown",
                )
            if clean in self._by_effect:
                raise ExecutionGatewayError(
                    f"Effect adapter already registered for {clean}",
                    code="execution_adapter_duplicate",
                )
        for effect_id in effect_ids:
            self._by_effect[str(effect_id)] = adapter

    def resolve(self, effect_id: str) -> EffectAdapter:
        clean = str(effect_id or "").strip()
        adapter = self._by_effect.get(clean)
        if adapter is None:
            raise ExecutionGatewayError(
                f"No EffectAdapter registered for {clean}",
                code="execution_adapter_missing",
            )
        return adapter

    def registered_effects(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_effect))


class CapabilityRuntimeEffectAdapter:
    """Governed adapter for imported Capability Package runtime."""

    effect_ids = frozenset({"capability.execute", "pipeline.execute"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from capability_packages import (
            CapabilityPackageError,
            execute_package,
            execute_pipeline_package,
            get_package,
        )

        package_id = str(request.target.get("package_id") or "").strip()
        if not package_id:
            raise ExecutionGatewayError(
                "Capability runtime target requires package_id",
                code="execution_target_missing",
            )
        package = get_package(package_id)
        expected_kind = "pipeline" if request.effect_id == "pipeline.execute" else "capability"
        requested_digest = str(request.target.get("package_digest") or "").strip()
        current_digest = str(package.get("digest") or "").strip()
        if requested_digest and requested_digest != current_digest:
            raise ExecutionGatewayError(
                "Package changed after authorization request was constructed",
                code="execution_target_digest_mismatch",
            )
        if str(package.get("kind") or "") != expected_kind:
            raise ExecutionGatewayError(
                f"Effect {request.effect_id} cannot execute package kind {package.get('kind')}",
                code="execution_target_kind_mismatch",
            )
        manager = context.manager
        if manager is not None:
            manager_session = str(getattr(manager, "session_id", "") or "")
            if manager_session and manager_session != request.session_id:
                raise ExecutionGatewayError(
                    "ExecutionContext manager belongs to another session",
                    code="execution_context_session_mismatch",
                )

        permissions = list(package.get("permissions", []))
        if request.effect_id == "pipeline.execute":
            if manager is None:
                raise ExecutionGatewayError(
                    "Pipeline execution requires SessionManager context",
                    code="execution_context_manager_required",
                )
            return execute_pipeline_package(
                package_id,
                inputs=request.arguments,
                confirmed=True,
                approved_permissions=permissions,
                manager=manager,
            )
        return execute_package(
            package_id,
            inputs=request.arguments,
            confirmed=True,
            approved_permissions=permissions,
        )


class FilesystemEffectAdapter:
    """Gateway-owned adapter for one scoped workspace file write."""

    effect_ids = frozenset({"filesystem.write"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from filesystem_effects import FilesystemEffectError, write_file_effect

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Filesystem write requires SessionManager context",
                code="execution_context_manager_required",
            )
        if not isinstance(context.services.get("_authorization"), dict):
            raise ExecutionGatewayError(
                "Filesystem write requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager_session and manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )
        raw_path = str(request.target.get("path") or "").strip()
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        content = str(arguments.get("content") or "")
        try:
            return write_file_effect(manager, raw_path, content)
        except FilesystemEffectError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc



class FilesystemReadEffectAdapter:
    """Gateway-owned adapter for one scoped, read-only plan child."""

    effect_ids = frozenset({"filesystem.read"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from filesystem_effects import FilesystemEffectError, read_file_effect

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Filesystem read requires SessionManager context",
                code="execution_context_manager_required",
            )
        if not isinstance(context.services.get("_authorization"), dict):
            raise ExecutionGatewayError(
                "Filesystem read requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager_session and manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )
        try:
            return read_file_effect(manager, str(request.target.get("path") or ""))
        except FilesystemEffectError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc


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
        if not isinstance(gateway, ExecutionGateway):
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


class DelegationGrantEffectAdapter:
    """Persist an E6 DelegationGrant only after its parent Permit is consumed."""

    effect_ids = frozenset({"schedule.delegate"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from delegation_grant import DelegationGrantRegistry

        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict):
            raise ExecutionGatewayError(
                "Delegation adapter requires gateway-owned authorization context",
                code="execution_delegation_authorization_missing",
            )

        state_dir = context.services.get("state_dir")
        if state_dir is None and context.manager is not None:
            from pathlib import Path

            base_path = Path(getattr(context.manager, "base_path", Path.cwd()))
            state_dir = base_path / ".bago" / "state"
        if state_dir is None:
            raise ExecutionGatewayError(
                "Delegation adapter requires trusted state_dir",
                code="execution_delegation_state_required",
            )

        grant = DelegationGrantRegistry(state_dir).issue_from_authorized_request(
            request,
            authorization,
        )
        return {"ok": True, "delegation_grant": grant}


def build_default_effect_adapter_registry() -> EffectAdapterRegistry:
    registry = EffectAdapterRegistry()
    registry.register(FilesystemEffectAdapter())
    registry.register(FilesystemReadEffectAdapter())
    registry.register(CapabilityRuntimeEffectAdapter())
    registry.register(PlanRuntimeEffectAdapter())
    registry.register(DelegationGrantEffectAdapter())
    return registry


class ExecutionGateway:
    """Consume a Permit and dispatch only through server-owned EffectAdapters."""

    def __init__(
        self,
        boundary: AuthorizationBoundary | None = None,
        adapters: EffectAdapterRegistry | None = None,
    ) -> None:
        self.boundary = boundary or AuthorizationBoundary()
        self.adapters = adapters or build_default_effect_adapter_registry()

    def execute(
        self,
        *,
        permit_token: str,
        request: ExecutionRequest,
        context: ExecutionContext | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        # Resolve first so a configuration error does not consume a valid Permit.
        adapter = self.adapters.resolve(request.effect_id)
        authorization = self.boundary.consume_permit(
            permit_token=permit_token,
            request=request,
        )
        trusted_context = context or ExecutionContext()
        trusted_services = dict(trusted_context.services)
        # Gateway-owned metadata overwrites any caller-supplied value.
        trusted_services["_authorization"] = authorization
        trusted_services["_gateway"] = self
        trusted_context = ExecutionContext(
            manager=trusted_context.manager,
            services=trusted_services,
        )
        result = adapter.execute(request, trusted_context)
        return result, authorization

    def execute_nested(
        self,
        *,
        parent_request: ExecutionRequest,
        child_request: ExecutionRequest,
        context: ExecutionContext,
    ) -> tuple[Any, dict[str, Any]]:
        """Dispatch a declared compound child without minting another Permit.

        The parent ``plan.execute`` Permit is consumed exactly once by
        ``execute``. This method is only an internal gateway dispatch: it
        accepts a child whose effect, target digest, workflow binding and
        idempotency preconditions were declared in the parent request. It
        never creates or consumes authority and rejects child risk above the
        parent's canonical effect.
        """

        if parent_request.effect_id != "plan.execute":
            raise ExecutionGatewayError(
                "Nested dispatch requires a plan.execute parent",
                code="execution_nested_parent_invalid",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or str(authorization.get("state") or "") != "consumed":
            raise ExecutionGatewayError(
                "Nested dispatch requires consumed parent authorization",
                code="execution_nested_authorization_missing",
            )
        if context.services.get("_gateway") is not self:
            raise ExecutionGatewayError(
                "Nested dispatch requires the active gateway context",
                code="execution_nested_gateway_context_missing",
            )
        if str(authorization.get("effect_id") or "") != parent_request.effect_id:
            raise ExecutionGatewayError(
                "Nested authorization effect differs from the parent request",
                code="execution_nested_authorization_effect_mismatch",
            )
        if str(authorization.get("operation_fingerprint") or "") != parent_request.fingerprint:
            raise ExecutionGatewayError(
                "Nested parent authorization fingerprint mismatch",
                code="execution_nested_parent_fingerprint_mismatch",
            )
        if child_request.parent_execution_id != parent_request.request_id:
            raise ExecutionGatewayError(
                "Nested child lineage is not bound to the parent request",
                code="execution_nested_lineage_mismatch",
            )
        if child_request.delegation_id != parent_request.delegation_id:
            raise ExecutionGatewayError(
                "Nested child delegation reference differs from parent",
                code="execution_nested_delegation_mismatch",
            )
        if (
            child_request.session_id != parent_request.session_id
            or child_request.principal_id != parent_request.principal_id
            or child_request.actor_kind != parent_request.actor_kind
        ):
            raise ExecutionGatewayError(
                "Nested child identity exceeds the parent request",
                code="execution_nested_identity_mismatch",
            )
        if child_request.source_surface != "plan.runtime":
            raise ExecutionGatewayError(
                "Nested child must originate in the governed PlanEngine runtime",
                code="execution_nested_surface_invalid",
            )

        parent_target = parent_request.target if isinstance(parent_request.target, dict) else {}
        child_effects = parent_target.get("child_effects")
        if not isinstance(child_effects, list):
            raise ExecutionGatewayError(
                "Parent plan request lacks declared child effects",
                code="execution_nested_children_missing",
            )
        pipeline = child_request.target.get("_pipeline") if isinstance(child_request.target, dict) else None
        if not isinstance(pipeline, dict):
            raise ExecutionGatewayError(
                "Nested child lacks 04-FIX2 pipeline binding",
                code="execution_nested_pipeline_binding_missing",
            )
        operation_id = str(pipeline.get("pipeline_operation_id") or "")
        step_id = str(pipeline.get("step_id") or "")
        if operation_id != str(parent_target.get("pipeline_operation_id") or "") or not step_id:
            raise ExecutionGatewayError(
                "Nested child pipeline binding differs from parent",
                code="execution_nested_pipeline_binding_mismatch",
            )

        preconditions = set(child_request.preconditions)
        idempotency_key = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("step_idempotency_key:")
            ),
            "",
        )
        workflow_fingerprint = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("workflow_fingerprint:")
            ),
            "",
        )
        step_fingerprint = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("step_definition_fingerprint:")
            ),
            "",
        )
        if not idempotency_key or not workflow_fingerprint or not step_fingerprint:
            raise ExecutionGatewayError(
                "Nested child lacks idempotency/version preconditions",
                code="execution_nested_preconditions_missing",
            )

        descriptor = next(
            (
                item
                for item in child_effects
                if isinstance(item, dict)
                and str(item.get("step_id") or "") == step_id
                and str(item.get("effect_id") or "") == child_request.effect_id
            ),
            None,
        )
        if not isinstance(descriptor, dict):
            raise ExecutionGatewayError(
                "Nested child effect is not declared by the parent plan",
                code="execution_nested_child_undeclared",
            )
        if str(descriptor.get("target_digest") or "") != child_request.target_digest:
            raise ExecutionGatewayError(
                "Nested child target differs from the prepared plan",
                code="execution_nested_target_mismatch",
            )
        if str(descriptor.get("arguments_digest") or "") != child_request.arguments_digest:
            raise ExecutionGatewayError(
                "Nested child arguments differ from the prepared plan",
                code="execution_nested_arguments_mismatch",
            )
        if str(descriptor.get("scope") or "") != child_request.scope:
            raise ExecutionGatewayError(
                "Nested child scope differs from the prepared plan",
                code="execution_nested_scope_mismatch",
            )
        if str(descriptor.get("step_definition_fingerprint") or "") != step_fingerprint:
            raise ExecutionGatewayError(
                "Nested child step definition is stale",
                code="execution_nested_step_definition_stale",
            )
        if not idempotency_key.startswith(str(descriptor.get("step_idempotency_key_prefix") or "")):
            raise ExecutionGatewayError(
                "Nested child idempotency key is outside the prepared step",
                code="execution_nested_idempotency_mismatch",
            )
        if workflow_fingerprint != str(parent_target.get("workflow_fingerprint") or ""):
            raise ExecutionGatewayError(
                "Nested child workflow fingerprint is stale",
                code="execution_nested_workflow_stale",
            )

        parent_effect = REGISTRY.get(parent_request.effect_id)
        child_effect = REGISTRY.get(child_request.effect_id)
        if child_effect.risk_rank > parent_effect.risk_rank:
            raise ExecutionGatewayError(
                "Nested child effect exceeds the parent plan risk boundary",
                code="execution_nested_risk_exceeded",
            )
        if child_request.policy_version != parent_request.policy_version or child_request.policy_version != REGISTRY.digest:
            raise ExecutionGatewayError(
                "Nested child policy is stale",
                code="execution_nested_policy_stale",
            )

        adapter = self.adapters.resolve(child_request.effect_id)
        trusted_services = dict(context.services)
        trusted_services["_parent_request"] = parent_request
        nested_context = ExecutionContext(manager=context.manager, services=trusted_services)
        return adapter.execute(child_request, nested_context), authorization


__all__ = [
    "CapabilityRuntimeEffectAdapter",
    "DelegationGrantEffectAdapter",
    "EffectAdapter",
    "EffectAdapterRegistry",
    "ExecutionContext",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "FilesystemEffectAdapter",
    "FilesystemReadEffectAdapter",
    "PlanRuntimeEffectAdapter",
    "build_default_effect_adapter_registry",
]

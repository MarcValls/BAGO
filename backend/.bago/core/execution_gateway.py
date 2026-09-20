"""Closed execution gateway for governed BAGO effects.

Callers submit an ExecutionRequest plus a Permit. They cannot supply a callable.
The gateway resolves the executable adapter from a server-owned registry keyed
by canonical effect_id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from authorization_boundary import AuthorizationBoundary
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


def build_default_effect_adapter_registry() -> EffectAdapterRegistry:
    registry = EffectAdapterRegistry()
    registry.register(CapabilityRuntimeEffectAdapter())
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
        result = adapter.execute(request, context or ExecutionContext())
        return result, authorization


__all__ = [
    "CapabilityRuntimeEffectAdapter",
    "EffectAdapter",
    "EffectAdapterRegistry",
    "ExecutionContext",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "build_default_effect_adapter_registry",
]

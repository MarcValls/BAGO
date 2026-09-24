"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from typing import Any
from execution_request import ExecutionRequest


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

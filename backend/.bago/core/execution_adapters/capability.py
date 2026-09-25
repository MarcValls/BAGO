"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

import subprocess
from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from typing import Any
from execution_request import ExecutionRequest


class CapabilityRuntimeEffectAdapter:
    """Governed adapter for imported Capability Package runtime."""

    effect_ids = frozenset({"capability.execute", "pipeline.execute"})

    @staticmethod
    def _run_process(*args: Any, **kwargs: Any) -> Any:
        return subprocess.run(*args, **kwargs)

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from capability_packages import (
            _execute_package,
            _execute_pipeline_package,
            get_package,
        )

        authorization = context.services.get("_authorization")
        if (not isinstance(authorization, dict) or authorization.get("state") != "consumed"
                or authorization.get("effect_id") != request.effect_id
                or authorization.get("operation_fingerprint") != request.fingerprint
                or authorization.get("session_id") != request.session_id):
            raise ExecutionGatewayError("Capability runtime requires its consumed Permit", code="capability_runtime_authorization_required")

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
        requested_version = str(request.target.get("package_version") or "").strip()
        if requested_version and requested_version != str(package.get("version") or ""):
            raise ExecutionGatewayError(
                "Package version changed after authorization request was constructed",
                code="execution_target_version_mismatch",
            )
        requested_permissions = request.target.get("declared_permissions")
        if isinstance(requested_permissions, list) and sorted(map(str, requested_permissions)) != sorted(map(str, package.get("permissions", []))):
            raise ExecutionGatewayError(
                "Package permissions changed after authorization request was constructed",
                code="execution_target_permissions_mismatch",
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
            return _execute_pipeline_package(
                package_id,
                inputs=request.arguments,
                confirmed=True,
                approved_permissions=permissions,
                manager=manager,
                process_executor=self._run_process,
            )
        return _execute_package(
            package_id,
            inputs=request.arguments,
            confirmed=True,
            approved_permissions=permissions,
            process_executor=self._run_process,
        )

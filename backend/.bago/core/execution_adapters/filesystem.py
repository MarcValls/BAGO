"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from typing import Any
from execution_request import ExecutionRequest


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

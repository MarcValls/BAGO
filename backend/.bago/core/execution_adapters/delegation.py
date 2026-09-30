"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from pathlib import Path
from typing import Any
from execution_request import ExecutionRequest


class DelegationGrantEffectAdapter:
    """Persist an E6 DelegationGrant only after its parent Permit is consumed."""

    effect_ids = frozenset({"schedule.delegate"})

    @staticmethod
    def revalidate_world_state(request: ExecutionRequest, context: ExecutionContext) -> None:
        target = request.target
        if not isinstance(target, dict):
            raise ExecutionGatewayError("Delegation request shape is invalid", code="execution_delegation_request_invalid")
        from delegation_grant import stable_digest
        schedule = target.get("schedule")
        schedule_id = str(target.get("schedule_id") or "").strip()
        if (not isinstance(schedule, dict) or not schedule_id or str(schedule.get("id") or "") != schedule_id
                or stable_digest(schedule) != str(target.get("schedule_digest") or "")):
            raise ExecutionGatewayError("Delegation schedule changed after authorization", code="execution_delegation_schedule_stale")

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

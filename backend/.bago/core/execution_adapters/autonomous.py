"""Operation-bound execution for the autonomous loop's fixed CLI tools."""
from __future__ import annotations

import subprocess
import os
import sys
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


_BACKEND_ROOT = Path(os.environ.get("BAGO_PADRE_PATH") or Path(__file__).resolve().parents[3]).expanduser().resolve()
_READ_ONLY_TOOLS = frozenset({
    "health", "validate", "stale", "audit", "detector", "stability",
    "deps", "sincerity", "dashboard", "ideas",
})
_REPAIR_TOOLS = frozenset({"heal", "doctor"})


class AutonomousToolRunnerEffectAdapter:
    """Shared bounded runner; registered subclasses own distinct policy modes."""

    def _execute(self, request: ExecutionRequest, context: ExecutionContext, *, mutating: bool) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        allowed = _REPAIR_TOOLS if mutating else _READ_ONLY_TOOLS
        expected_effect = "autonomous.repair" if mutating else "autonomous.observe"
        if (not isinstance(authorization, dict)
                or authorization.get("effect_id") != request.effect_id
                or authorization.get("operation_fingerprint") != request.fingerprint
                or authorization.get("session_id") != request.session_id
                or (mutating and authorization.get("state") != "consumed")
                or (not mutating and authorization.get("kind") != "server_policy")
                or request.effect_id != expected_effect):
            raise ExecutionGatewayError("Autonomous tool requires its matching gateway authorization", code="autonomous_tool_authorization_required")

        target = request.target if isinstance(request.target, dict) else {}
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        tool = str(target.get("tool") or "").strip()
        if tool not in allowed:
            raise ExecutionGatewayError("Autonomous tool is outside the fixed allowlist", code="autonomous_tool_not_allowed")
        if str(target.get("backend_root") or "") != str(_BACKEND_ROOT):
            raise ExecutionGatewayError("Autonomous tool backend root changed", code="autonomous_tool_root_mismatch")
        if str(target.get("python_executable") or "") != sys.executable:
            raise ExecutionGatewayError("Autonomous tool interpreter changed", code="autonomous_tool_interpreter_mismatch")
        extra_args = arguments.get("extra_args", [])
        if not isinstance(extra_args, list) or extra_args:
            raise ExecutionGatewayError("Autonomous tool arguments are not approved", code="autonomous_tool_arguments_invalid")
        try:
            timeout = float(target.get("timeout_seconds", 60))
        except (TypeError, ValueError) as exc:
            raise ExecutionGatewayError("Autonomous tool timeout is invalid", code="autonomous_tool_timeout_invalid") from exc
        if timeout <= 0 or timeout > 60:
            raise ExecutionGatewayError("Autonomous tool timeout exceeds the 60 second bound", code="autonomous_tool_timeout_invalid")

        try:
            completed = subprocess.run(
                [sys.executable, str(_BACKEND_ROOT / "bago"), tool],
                capture_output=True, text=True, timeout=timeout,
                cwd=str(_BACKEND_ROOT), shell=False,
            )
            return {
                "ok": completed.returncode == 0,
                "returncode": int(completed.returncode),
                "output": str(completed.stdout or "") + str(completed.stderr or ""),
                "effect_id": request.effect_id,
                "receipt_id": f"{request.effect_id}:{request.fingerprint}",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": -1, "output": f"[TIMEOUT] bago {tool} exceeded {timeout}s", "effect_id": request.effect_id}
        except OSError as exc:
            return {"ok": False, "returncode": -1, "output": f"[ERROR] {exc}", "effect_id": request.effect_id}


class AutonomousObservationEffectAdapter(AutonomousToolRunnerEffectAdapter):
    effect_ids = frozenset({"autonomous.observe"})
    server_policy_only = True

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        return self._execute(request, context, mutating=False)


class AutonomousRepairEffectAdapter(AutonomousToolRunnerEffectAdapter):
    effect_ids = frozenset({"autonomous.repair"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        return self._execute(request, context, mutating=True)

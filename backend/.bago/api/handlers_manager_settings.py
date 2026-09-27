"""Challenge/approve/execute facade for bounded Electron manager settings."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle_write(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None = None) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_adapters.manager_settings import ManagerSettingsWriteEffectAdapter
    from execution_gateway import ExecutionGateway
    from execution_request import ExecutionRequestError, build_execution_request

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible", "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    try:
        resource = str(payload.get("resource") or "").strip()
        arguments: dict[str, Any]
        if resource == "install_selection":
            arguments = {"resource": resource, "role": payload.get("role"), "install_dir": payload.get("install_dir")}
        elif resource == "chain_registry":
            arguments = {"resource": resource, "chains": payload.get("chains")}
        else:
            arguments = {"resource": resource}
        target = ManagerSettingsWriteEffectAdapter.prepare_target(arguments)
        request = build_execution_request(
            effect_id="manager.settings.write", actor_kind="user",
            principal_id="interactive-local-user", session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="api.manager.settings.write", target=target, arguments=arguments, scope="persistent",
        )
        boundary = AuthorizationBoundary()
        action = str(payload.get("authorization_action") or "").strip().lower()
        interaction_id = str(payload.get("interaction_id") or "").strip()
        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            send_json(handler, 200, {"ok": True, "authorization": {"state": "challenge", "challenge": challenge}})
            return
        if action == "approve":
            if str(payload.get("user_decision") or "").strip().lower() != "approve":
                raise AuthorizationError("La decisión explícita debe ser approve", code="authorization_user_decision_required")
            headers = getattr(handler, "headers", {}) or {}
            channel = headers.get("X-Bago-Channel", "") if hasattr(headers, "get") else ""
            result = boundary.approve_challenge(
                challenge_id=str(payload.get("challenge_id") or ""), interaction_id=interaction_id,
                session_id=request.session_id, channel=channel,
            )
            send_json(handler, 200, {"ok": True, "authorization": {"state": "authorized", **result}})
            return
        if action != "execute":
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_invalid")
        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""), request=request,
            context=ExecutionContext(manager=manager),
        )
        result["authorization"] = {"state": "consumed", "permit_id": authorization.get("permit_id"),
                                   "operation_fingerprint": authorization.get("operation_fingerprint")}
        send_json(handler, 200, result)
    except AuthorizationError as exc:
        send_json(handler, 409 if "challenge" in exc.code or "permit" in exc.code else 403,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionRequestError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})

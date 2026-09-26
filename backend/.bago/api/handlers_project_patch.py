"""Explicit authorization boundary for atomic workspace patch application."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None, *, rollback: bool) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext
    from execution_adapters.project import ProjectWriteEffectAdapter
    from execution_gateway import ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    diffs = payload.get("patches")
    snapshot = str(payload.get("snapshot") or "").strip()
    try:
        if rollback:
            request = ProjectWriteEffectAdapter.build_patch_rollback_request(manager, snapshot)
        else:
            request = ProjectWriteEffectAdapter.build_patch_request(manager, diffs)
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
            authorization = boundary.approve_challenge(
                challenge_id=str(payload.get("challenge_id") or ""),
                interaction_id=interaction_id,
                session_id=request.session_id,
                channel=channel,
            )
            send_json(handler, 200, {"ok": True, "authorization": {"state": "authorized", **authorization}})
            return
        if action != "execute":
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_required")
        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""),
            request=request,
            context=ExecutionContext(manager=manager),
        )
        result["authorization"] = {
            "state": "consumed",
            "permit_id": authorization.get("permit_id"),
            "decision_id": authorization.get("decision_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        }
        send_json(handler, 200 if result.get("ok") else 409, result)
    except AuthorizationError as exc:
        send_json(handler, 409 if "challenge" in exc.code or "permit" in exc.code or "operation_mismatch" in exc.code else 403,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionRequestError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        code = str(getattr(exc, "code", "") or "workspace_patch_preflight_failed")
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": code})


def handle_apply(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None = None) -> None:
    _handle(handler, body, rollback=False)


def handle_rollback(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None = None) -> None:
    _handle(handler, body, rollback=True)

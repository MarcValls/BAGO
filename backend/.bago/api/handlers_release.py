"""Endpoints de actualización integrada."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle_check(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from update_manager import check
    result = check()
    send_json(handler, 200 if "error" not in result else 502, result)


def handle_status(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from update_manager import status
    send_json(handler, 200, status())


def handle_update(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    from api_serializers import send_json
    from update_manager import start_update
    tag = str((body or {}).get("tag", "")).strip()
    result = start_update(tag)
    send_json(handler, 202 if result.get("ok") else 409, result)


def handle_apply(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    from api_serializers import send_json
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_gateway import ExecutionContext, ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError, build_execution_request
    from api_state import get_mgr
    from update_manager import update_apply_descriptor

    mgr = get_mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error_code": "SESSION_MANAGER_MISSING"})
        return
    try:
        target = update_apply_descriptor()
        request = build_execution_request(
            effect_id="system.update.apply",
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(mgr, "session_id", "") or ""),
            source_surface="api.release.apply",
            target=target,
            arguments={},
            scope="system",
        )
        boundary = AuthorizationBoundary()
        payload = dict(body or {})
        action = str(payload.get("authorization_action") or "").strip().lower()
        interaction_id = str(payload.get("interaction_id") or "").strip()
        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            send_json(handler, 200, {"ok": True, "authorization": {"state": "challenge", "challenge": challenge}})
            return
        if action == "approve":
            if str(payload.get("user_decision") or "").strip().lower() != "approve":
                raise AuthorizationError("La decisión explícita del usuario debe ser approve", code="authorization_user_decision_required")
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
        if action not in {"", "execute"}:
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_invalid")
        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""),
            request=request,
            context=ExecutionContext(manager=mgr),
        )
        result["authorization"] = {
            "state": "consumed",
            "permit_id": authorization.get("permit_id"),
            "decision_id": authorization.get("decision_id"),
            "proof_id": authorization.get("proof_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        }
        send_json(handler, 202 if result.get("ok") else 409, result)
    except AuthorizationError as exc:
        send_json(handler, 409 if exc.code.startswith("authorization_permit") else 403,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionRequestError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except Exception as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "update_apply_preflight_failed"})

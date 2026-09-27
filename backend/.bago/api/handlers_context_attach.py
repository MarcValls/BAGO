"""Explicit authorization endpoint for materializing a session context bundle."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext
    from execution_gateway import ContextAttachEffectAdapter, ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError, build_execution_request

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    payload = dict(body or {})
    paths = payload.get("paths", [])
    if not isinstance(paths, list) or len(paths) > 32 or any(
        not isinstance(item, str) or len(item) > 4096 for item in paths
    ):
        send_json(handler, 400, {
            "ok": False,
            "error": "paths debe ser una lista de hasta 32 rutas de texto",
            "code": "context_attach_paths_invalid",
        })
        return
    try:
        source_root, context_root, selected, selection_digest = ContextAttachEffectAdapter.prepare_operation(
            manager, paths
        )
        request = build_execution_request(
            effect_id="workspace.context.attach",
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="api.context.attach",
            target={
                "source_root": str(source_root),
                "context_root": str(context_root),
                "selection": [str(path) for path in selected],
                "selection_digest": selection_digest,
                "resource": "session_context",
                "operation": "attach",
            },
            arguments={"paths": paths},
            scope="workspace",
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
                raise AuthorizationError(
                    "La decisión explícita del usuario debe ser approve",
                    code="authorization_user_decision_required",
                )
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
            raise AuthorizationError(
                "authorization_action must be challenge, approve or execute",
                code="authorization_action_invalid",
            )
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
        send_json(handler, 500 if exc.code.endswith("failed") else 409,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except (OSError, RuntimeError, ValueError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "context_attach_preflight_failed"})

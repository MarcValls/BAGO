"""Direct-user authorization for one prepared system installation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle_apply(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None = None) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext
    from execution_gateway import ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError, build_execution_request
    from install_plan import InstallPlanError, build_install_plan

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible", "code": "SESSION_MANAGER_MISSING"})
        return

    payload = body if isinstance(body, dict) else {}
    configuration = payload.get("configuration")
    options = payload.get("options", {})
    try:
        if not isinstance(configuration, dict) or not isinstance(options, dict):
            raise InstallPlanError("configuration and options must be objects")
        target = build_install_plan(
            action=str(payload.get("action") or ""),
            source_root=str(payload.get("source_root") or ""),
            helper_path=str(payload.get("helper_path") or ""),
            install_dir=str(payload.get("install_dir") or ""),
            mode=str(payload.get("mode") or ""),
            options=options,
            configuration=configuration,
            package_digest=str(payload.get("package_sha256") or ""),
        )
        request = build_execution_request(
            effect_id="system.install.apply",
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="api.install.apply",
            target=target,
            arguments={"configuration": configuration},
            scope="system",
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
        if action != "execute":
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_invalid")
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
    except InstallPlanError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": "system_install_plan_invalid"})
    except AuthorizationError as exc:
        send_json(handler, 409 if "challenge" in exc.code or "permit" in exc.code or "operation_mismatch" in exc.code else 403,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionRequestError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        send_json(handler, 409 if not exc.code.endswith("failed") else 500,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except (OSError, RuntimeError, ValueError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "system_install_preflight_failed"})


def handle_source_update(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None = None) -> None:
    """Challenge, approve, and execute one exact clean-checkout fast-forward."""
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_adapters.source_update import SystemSourceUpdateEffectAdapter
    from execution_gateway import ExecutionGateway
    from execution_request import ExecutionRequestError, build_execution_request

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible", "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    try:
        target = SystemSourceUpdateEffectAdapter.prepare_target(
            str(payload.get("source_root") or ""), str(payload.get("branch") or "main")
        )
        request = build_execution_request(
            effect_id="system.source.update", actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="api.install.source-update", target=target,
            arguments={}, scope="system",
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
                raise AuthorizationError("La decisión explícita del usuario debe ser approve", code="authorization_user_decision_required")
            headers = getattr(handler, "headers", {}) or {}
            channel = headers.get("X-Bago-Channel", "") if hasattr(headers, "get") else ""
            authorization = boundary.approve_challenge(
                challenge_id=str(payload.get("challenge_id") or ""),
                interaction_id=interaction_id, session_id=request.session_id, channel=channel,
            )
            send_json(handler, 200, {"ok": True, "authorization": {"state": "authorized", **authorization}})
            return
        if action != "execute":
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_invalid")
        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""),
            request=request, context=ExecutionContext(manager=manager),
        )
        result["authorization"] = {
            "state": "consumed", "permit_id": authorization.get("permit_id"),
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
        send_json(handler, 409 if not exc.code.endswith("failed") else 500,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except (OSError, RuntimeError, ValueError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "system_source_update_preflight_failed"})


def handle_uninstall(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None = None) -> None:
    """Authorize one install removal and optional user-state purge."""
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_gateway import ExecutionGateway
    from execution_request import ExecutionRequestError, build_execution_request
    from install_uninstall_plan import build_uninstall_target

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible", "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    try:
        target = build_uninstall_target(
            str(payload.get("install_dir") or ""), bool(payload.get("purge_state", False))
        )
        request = build_execution_request(
            effect_id="system.install.uninstall", actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="api.install.uninstall", target=target, arguments={}, scope="system",
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
                raise AuthorizationError("La decisión explícita del usuario debe ser approve", code="authorization_user_decision_required")
            headers = getattr(handler, "headers", {}) or {}
            channel = headers.get("X-Bago-Channel", "") if hasattr(headers, "get") else ""
            authorization = boundary.approve_challenge(
                challenge_id=str(payload.get("challenge_id") or ""),
                interaction_id=interaction_id, session_id=request.session_id, channel=channel,
            )
            send_json(handler, 200, {"ok": True, "authorization": {"state": "authorized", **authorization}})
            return
        if action != "execute":
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_invalid")
        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""),
            request=request, context=ExecutionContext(manager=manager),
        )
        result["authorization"] = {
            "state": "consumed", "permit_id": authorization.get("permit_id"),
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
        send_json(handler, 409 if not exc.code.endswith("failed") else 500,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except (OSError, RuntimeError, ValueError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "system_install_uninstall_preflight_failed"})


def handle_rollback(handler: "BaseHTTPRequestHandler", body: dict[str, Any] | None = None) -> None:
    """Strong-Permit owner for restoring one release-job install target."""
    import os

    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext
    from execution_gateway import ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError, build_execution_request

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible", "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    try:
        install_dir = str(payload.get("install_dir") or "")
        displaced_path = str(payload.get("displaced_path") or "")
        backup_path = str(payload.get("backup_path") or "")
        if not os.path.isabs(install_dir) or not os.path.isabs(displaced_path) or (backup_path and not os.path.isabs(backup_path)):
            raise ValueError("install_dir and displaced_path are required")
        target = {
            "install_dir": os.path.abspath(install_dir),
            "backup_path": os.path.abspath(backup_path) if backup_path else "",
            "displaced_path": os.path.abspath(displaced_path),
        }
        request = build_execution_request(
            effect_id="system.install.rollback",
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="api.install.rollback",
            target=target,
            arguments={},
            scope="system",
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
        if action != "execute":
            raise AuthorizationError("authorization_action must be challenge, approve or execute", code="authorization_action_invalid")
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
        send_json(handler, 409 if not exc.code.endswith("failed") else 500,
                  {"ok": False, "error": str(exc), "code": exc.code})
    except (OSError, RuntimeError, ValueError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "system_install_rollback_preflight_failed"})

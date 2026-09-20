"""HTTP lifecycle for user-installed Capability Packages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _send(handler: "BaseHTTPRequestHandler", operation: Callable[[], Any]) -> None:
    from api_serializers import send_json
    from authorization_boundary import AuthorizationError
    from capability_packages import CapabilityPackageError
    from execution_gateway import ExecutionGatewayError
    from execution_request import ExecutionRequestError

    try:
        payload = operation()
    except (ExecutionGatewayError, ExecutionRequestError) as exc:
        status = 409 if getattr(exc, "code", "") in {
            "execution_adapter_missing",
            "execution_target_kind_mismatch",
            "execution_target_digest_mismatch",
            "execution_context_session_mismatch",
        } else 400
        send_json(handler, status, {"ok": False, "error": str(exc), "code": getattr(exc, "code", "execution_error")})
        return
    except AuthorizationError as exc:
        status = 404 if exc.code == "authorization_challenge_not_found" else 409 if exc.code in {
            "authorization_challenge_not_pending",
            "authorization_challenge_expired",
            "authorization_permit_replay",
            "authorization_permit_expired",
            "authorization_operation_mismatch",
        } else 403
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
        return
    except CapabilityPackageError as exc:
        status = 404 if exc.code == "not_found" else 409 if exc.code == "version_conflict" else 400
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
        return
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"Error interno de Capability Packages: {exc}"})
        return
    send_json(handler, 200, payload)


def handle_list(handler: "BaseHTTPRequestHandler") -> None:
    from capability_packages import list_packages
    _send(handler, lambda: {"ok": True, "packages": list_packages()})


def handle_get(handler: "BaseHTTPRequestHandler", capability_id: str) -> None:
    from capability_packages import get_package
    _send(handler, lambda: {"ok": True, "package": get_package(capability_id)})


def handle_receipts(handler: "BaseHTTPRequestHandler") -> None:
    from capability_packages import list_receipts
    _send(handler, lambda: {"ok": True, "receipts": list_receipts()})


def handle_examples(handler: "BaseHTTPRequestHandler") -> None:
    from capability_packages import list_example_packages
    _send(handler, lambda: {"ok": True, "examples": list_example_packages()})


def handle_install_example(handler: "BaseHTTPRequestHandler", package_id: str, body: dict[str, Any]) -> None:
    from capability_packages import install_example_package
    _send(handler, lambda: install_example_package(package_id))


def handle_import(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from capability_packages import import_package
    _send(handler, lambda: import_package(
        content_base64=str((body or {}).get("content_base64") or ""),
        file_name=str((body or {}).get("file_name") or ""),
        confirm_trust=(body or {}).get("confirm_trust") is True,
    ))


def handle_inspect(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from capability_packages import inspect_package
    _send(handler, lambda: inspect_package(
        content_base64=str((body or {}).get("content_base64") or ""),
        file_name=str((body or {}).get("file_name") or ""),
    ))


def handle_export(handler: "BaseHTTPRequestHandler", capability_id: str) -> None:
    from capability_packages import export_package
    _send(handler, lambda: export_package(capability_id))


def handle_enable(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from capability_packages import set_enabled
    enabled = (body or {}).get("enabled")
    if not isinstance(enabled, bool):
        from api_serializers import send_json
        send_json(handler, 400, {"ok": False, "error": "enabled debe ser boolean", "code": "invalid_request"})
        return
    _send(handler, lambda: {"ok": True, "package": set_enabled(
        capability_id,
        enabled,
        confirm_trust=(body or {}).get("confirm_trust") is True,
    )})


def handle_configure(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from capability_packages import configure_package
    _send(handler, lambda: {"ok": True, "package": configure_package(capability_id, (body or {}).get("config", {}))})


def handle_execute(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    """Governed capability execution.

    Client-supplied `confirmed` and `approved_permissions` fields are deliberately
    ignored as authority. A server-issued one-time Permit is mandatory.
    """

    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary
    from capability_packages import get_package
    from execution_gateway import ExecutionContext, ExecutionGateway
    from execution_request import build_execution_request

    def execute() -> dict[str, Any]:
        payload = body or {}
        mgr = get_mgr(handler)
        package = get_package(capability_id)
        inputs = payload.get("input", {})
        effect_id = "pipeline.execute" if package["kind"] == "pipeline" else "capability.execute"
        request = build_execution_request(
            effect_id=effect_id,
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(mgr, "session_id", "") or ""),
            source_surface="api.capability_packages.execute",
            target={
                "package_id": capability_id,
                "package_kind": package["kind"],
                "package_version": package["version"],
                "package_digest": package["digest"],
                "declared_permissions": list(package.get("permissions", [])),
            },
            arguments=inputs,
        )
        boundary = AuthorizationBoundary()
        action = str(payload.get("authorization_action") or "").strip().lower()
        interaction_id = str(payload.get("interaction_id") or "").strip()

        if action == "challenge":
            challenge = boundary.create_challenge(
                request,
                interaction_id=interaction_id,
            )
            return {
                "ok": True,
                "authorization": {
                    "state": "challenge",
                    "challenge": challenge,
                },
            }

        if action == "approve":
            if str(payload.get("user_decision") or "").strip().lower() != "approve":
                from authorization_boundary import AuthorizationError
                raise AuthorizationError(
                    "La decisión explícita del usuario debe ser approve",
                    code="authorization_user_decision_required",
                )
            channel = str(handler.headers.get("X-Bago-Channel", "") or "")
            authorization = boundary.approve_challenge(
                challenge_id=str(payload.get("challenge_id") or ""),
                interaction_id=interaction_id,
                session_id=request.session_id,
                channel=channel,
            )
            return {
                "ok": True,
                "authorization": {
                    "state": "authorized",
                    **authorization,
                },
            }

        gateway = ExecutionGateway(boundary)
        permit_token = str(payload.get("authorization_permit") or "")

        result, authorization = gateway.execute(
            permit_token=permit_token,
            request=request,
            context=ExecutionContext(manager=mgr),
        )
        if isinstance(result, dict):
            result = dict(result)
            result["authorization"] = {
                "state": "consumed",
                "permit_id": authorization.get("permit_id"),
                "decision_id": authorization.get("decision_id"),
                "proof_id": authorization.get("proof_id"),
                "operation_fingerprint": authorization.get("operation_fingerprint"),
            }
        return result

    _send(handler, execute)

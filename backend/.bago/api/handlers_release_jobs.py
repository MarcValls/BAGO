"""Release-job operations dispatched through the canonical execution gateway."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _dispatch(effect_id: str, source_surface: str, target: dict, manager, arguments: dict | None = None):
    from execution_gateway import ExecutionContext, ExecutionGateway
    from execution_request import build_execution_request

    request = build_execution_request(
        effect_id=effect_id,
        actor_kind="server",
        principal_id="bago-electron-release-manager",
        session_id=str(getattr(manager, "session_id", "") or "release-job-manager"),
        source_surface=source_surface,
        target=target,
        arguments=arguments or {},
        scope="system",
    )
    return ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(manager=manager),
    )


def handle_verify_signature(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from execution_gateway import ExecutionGatewayError
    from execution_request import ExecutionRequestError

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    try:
        result, authorization = _dispatch(
            "release.signature.verify",
            "server.electron.release_job.signature",
            {
                "signature_path": str(payload.get("signature_path") or ""),
                "bundle_path": str(payload.get("bundle_path") or ""),
            },
            manager,
        )
        result["authorization"] = {
            "kind": authorization.get("kind"),
            "decision_id": authorization.get("decision_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        }
        send_json(handler, 200 if result.get("ok") else 409, result)
    except (ExecutionRequestError, ExecutionGatewayError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except Exception as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "release_signature_dispatch_failed"})


def handle_stage_bundle(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from execution_gateway import ExecutionGatewayError
    from execution_request import ExecutionRequestError

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    try:
        result, authorization = _dispatch(
            "release.bundle.stage",
            "server.electron.release_job.stage",
            {
                "job_id": str(payload.get("job_id") or ""),
                "bundle_path": str(payload.get("bundle_path") or ""),
            },
            manager,
        )
        result["authorization"] = {
            "kind": authorization.get("kind"),
            "decision_id": authorization.get("decision_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        }
        send_json(handler, 200 if result.get("ok") else 409, result)
    except (ExecutionRequestError, ExecutionGatewayError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except Exception as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "release_stage_dispatch_failed"})


def handle_download_asset(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    """Fetch one release-job asset through the server-owned release downloader."""
    from api_serializers import send_json
    from api_state import get_mgr
    from execution_gateway import ExecutionGatewayError
    from execution_request import ExecutionRequestError

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    job_id = str(payload.get("job_id") or "")
    filename = str(payload.get("filename") or "")
    asset_kind = str(payload.get("asset_kind") or "")
    try:
        result, authorization = _dispatch(
            "release.download",
            "server.electron.release_job.asset_download",
            {
                "filename": filename,
                "job_id": job_id,
                "asset_kind": asset_kind,
                "resume": bool(payload.get("resume")),
            },
            manager,
            {
                "url": str(payload.get("url") or ""),
                "digest": str(payload.get("digest") or ""),
                "size": payload.get("size"),
            },
        )
        result["authorization"] = {
            "kind": authorization.get("kind"),
            "decision_id": authorization.get("decision_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        }
        send_json(handler, 200 if result.get("ok") else 409, result)
    except (ExecutionRequestError, ExecutionGatewayError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except Exception as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "release_asset_download_dispatch_failed"})


def _handle_storage(handler: "BaseHTTPRequestHandler", body: dict | None, *, effect_id: str, source: str, code: str) -> None:
    from api_serializers import send_json
    from api_state import get_mgr
    from execution_gateway import ExecutionGatewayError
    from execution_request import ExecutionRequestError

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    job_id = str(payload.get("job_id") or "")
    arguments = {"state": payload.get("state")} if effect_id == "release.job.persist" else {"record": payload.get("record")}
    try:
        result, authorization = _dispatch(
            effect_id,
            source,
            {"job_id": job_id},
            manager,
            arguments,
        )
        result["authorization"] = {
            "kind": authorization.get("kind"),
            "decision_id": authorization.get("decision_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        }
        send_json(handler, 200 if result.get("ok") else 409, result)
    except (ExecutionRequestError, ExecutionGatewayError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except Exception as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": code})


def handle_persist_job(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    _handle_storage(
        handler,
        body,
        effect_id="release.job.persist",
        source="server.electron.release_job.persist",
        code="release_job_persist_dispatch_failed",
    )


def handle_append_log(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    _handle_storage(
        handler,
        body,
        effect_id="release.job.log.append",
        source="server.electron.release_job.log",
        code="release_job_log_dispatch_failed",
    )


def handle_archive_job(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    """Challenge, approve and execute one state-bound release-job archive."""
    from api_serializers import send_json
    from api_state import get_mgr
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_adapter_contract import ExecutionContext
    from execution_adapters.release_job_archive import ReleaseJobArchiveEffectAdapter
    from execution_gateway import ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError, build_execution_request
    import hashlib
    import json

    manager = get_mgr(handler)
    if manager is None:
        send_json(handler, 503, {"ok": False, "code": "SESSION_MANAGER_MISSING"})
        return
    payload = body if isinstance(body, dict) else {}
    job_id = str(payload.get("job_id") or "")
    action = str(payload.get("authorization_action") or "").strip().lower()
    interaction_id = str(payload.get("interaction_id") or "").strip()
    try:
        state_path = ReleaseJobArchiveEffectAdapter.state_path(job_id)
        encoded_state = state_path.read_bytes()
        state = json.loads(encoded_state.decode("utf-8"))
        if not isinstance(state, dict) or str(state.get("id") or "") != job_id:
            raise ValueError("Persisted release job identity does not match")
        request = build_execution_request(
            effect_id="release.job.archive",
            actor_kind="user",
            principal_id="interactive-local-user",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="api.release.jobs.archive",
            target={"job_id": job_id, "state_sha256": hashlib.sha256(encoded_state).hexdigest()},
            arguments={"archived_at": str(payload.get("archived_at") or "")},
            scope="system",
        )
        boundary = AuthorizationBoundary()
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
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionRequestError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc), "code": exc.code})
    except ExecutionGatewayError as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": exc.code})
    except (OSError, ValueError, TypeError) as exc:
        send_json(handler, 409, {"ok": False, "error": str(exc), "code": "release_job_archive_preflight_failed"})

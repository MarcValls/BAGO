"""Governed schedule CRUD and delegated execution handlers."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def _state_dir(mgr) -> Path:
    base_path = Path(getattr(mgr, "base_path", Path.cwd()))
    return base_path / ".bago" / "state"


def _registry(mgr):
    from schedule_registry import ScheduleRegistry
    return ScheduleRegistry(_state_dir(mgr))


def _grants(mgr):
    from delegation_grant import DelegationGrantRegistry
    return DelegationGrantRegistry(_state_dir(mgr))


def _send_operation(handler: "BaseHTTPRequestHandler", operation) -> None:
    from api_serializers import send_json
    from authorization_boundary import AuthorizationError
    from delegation_grant import DelegationError
    from execution_gateway import ExecutionGatewayError
    from execution_request import ExecutionRequestError
    from schedule_registry import ScheduleError

    try:
        payload = operation()
    except ScheduleError as exc:
        status = 404 if exc.code == "not_found" else 409 if exc.code in {
            "conflict",
            "running",
            "delegation_required",
            "delegation_reauthorization_required",
        } else 400
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
        return
    except DelegationError as exc:
        status = 404 if exc.code == "delegation_not_found" else 409 if exc.code in {
            "delegation_revoked",
            "delegation_expired",
            "delegation_exhausted",
            "delegation_not_active",
            "delegation_policy_stale",
            "delegation_schedule_digest_mismatch",
            "delegation_effect_exceeds_grant",
            "delegation_target_exceeds_grant",
            "delegation_arguments_exceed_grant",
            "delegation_scope_exceeds_grant",
        } else 400
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
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
    except (ExecutionGatewayError, ExecutionRequestError) as exc:
        status = 409 if getattr(exc, "code", "") in {
            "execution_adapter_missing",
            "execution_target_kind_mismatch",
            "execution_target_digest_mismatch",
            "execution_context_session_mismatch",
        } else 400
        send_json(handler, status, {"ok": False, "error": str(exc), "code": getattr(exc, "code", "execution_error")})
        return
    send_json(handler, 200, payload)


def _serialised_jobs(mgr) -> list[dict[str, Any]]:
    return _registry(mgr).list()


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    jobs = _serialised_jobs(mgr)
    send_json(handler, 200, {"ok": True, "jobs": jobs, "count": len(jobs)})


def _schedule_draft(mgr, raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    from schedule_registry import ScheduleError

    payload = dict(raw or {})
    schedule_id = str(payload.get("id") or f"schedule-{uuid.uuid4().hex[:12]}").strip()
    if not schedule_id or "/" in schedule_id or "\\" in schedule_id:
        raise ScheduleError("id de programación inválido")
    requested_enabled = bool(payload.get("enabled", False))
    # Validate all schedule semantics without pretending that a bool is authority.
    validation = {
        **payload,
        "id": schedule_id,
        "enabled": False,
        "delegation_id": "",
    }
    clean = _registry(mgr)._validate(validation, creating=True)
    draft = {
        **clean,
        "id": schedule_id,
        "enabled": requested_enabled,
        "delegation_id": "",
    }
    return draft, requested_enabled


def _child_semantics(mgr, schedule: dict[str, Any]) -> tuple[str, dict[str, Any], Any, str]:
    from delegation_grant import DelegationError
    from effect_registry import REGISTRY

    target_type = str(schedule.get("target_type") or "").strip()
    raw_target = schedule.get("target")
    target = raw_target if isinstance(raw_target, dict) else {}

    if target_type in {"capability", "pipeline"}:
        from capability_packages import get_package

        package_id = str(
            target.get("capability_id")
            or target.get("pipeline_id")
            or target.get("package_id")
            or ""
        ).strip()
        if not package_id:
            raise DelegationError("Scheduled package id is required", code="delegation_target_invalid")
        package = get_package(package_id)
        expected_kind = "pipeline" if target_type == "pipeline" else "capability"
        if str(package.get("kind") or "") != expected_kind:
            raise DelegationError(
                f"Scheduled target {package_id} is not a {expected_kind}",
                code="delegation_target_kind_mismatch",
            )
        effect_id = "pipeline.execute" if expected_kind == "pipeline" else "capability.execute"
        normalized_target = {
            "package_id": package_id,
            "package_kind": package["kind"],
            "package_version": package["version"],
            "package_digest": package["digest"],
            "declared_permissions": list(package.get("permissions", [])),
        }
        arguments = target.get("input", {})
        return effect_id, normalized_target, arguments, REGISTRY.get(effect_id).default_scope

    if target_type == "plan":
        plan_id = str(target.get("plan_id") or "").strip()
        if not plan_id:
            raise DelegationError("Scheduled plan_id is required", code="delegation_target_invalid")
        effect_id = "plan.execute"
        return effect_id, {"plan_id": plan_id}, {}, REGISTRY.get(effect_id).default_scope

    if target_type == "task":
        raise DelegationError(
            "Dynamic task schedules cannot be pre-authorized; materialize a fixed plan or package first",
            code="delegation_target_dynamic",
        )

    raise DelegationError(
        f"Unsupported scheduled target: {target_type}",
        code="delegation_target_invalid",
    )


def _delegation_request(mgr, raw: dict[str, Any]):
    from delegation_grant import DelegationError, schedule_descriptor_digest
    from effect_registry import REGISTRY
    from execution_request import build_execution_request, stable_digest

    draft, requested_enabled = _schedule_draft(mgr, raw)
    effect_id, child_target, child_arguments, child_scope = _child_semantics(mgr, draft)
    delegation = raw.get("delegation")
    if not isinstance(delegation, dict):
        raise DelegationError(
            "Creating delegated schedule authority requires delegation constraints",
            code="delegation_constraints_required",
        )
    expires_at = str(delegation.get("expires_at") or "").strip()
    if not expires_at:
        raise DelegationError("delegation.expires_at is required", code="delegation_expiry_required")
    try:
        max_runs = int(delegation.get("max_runs"))
    except (TypeError, ValueError) as exc:
        raise DelegationError("delegation.max_runs must be an integer", code="delegation_max_runs_invalid") from exc
    if max_runs < 1:
        raise DelegationError("delegation.max_runs must be greater than zero", code="delegation_max_runs_invalid")

    schedule_digest = schedule_descriptor_digest(draft)
    grant_seed = {
        "schedule_id": draft["id"],
        "schedule_digest": schedule_digest,
        "effect_id": effect_id,
        "target_digest": stable_digest(child_target),
        "arguments_digest": stable_digest(child_arguments),
        "scope": child_scope,
        "expires_at": expires_at,
        "max_runs": max_runs,
        "policy_version": REGISTRY.digest,
    }
    grant_id = str(delegation.get("grant_id") or f"delegation-{stable_digest(grant_seed)[:24]}").strip()

    request = build_execution_request(
        effect_id="schedule.delegate",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=str(getattr(mgr, "session_id", "") or ""),
        source_surface="api.schedule.create",
        target={
            "schedule_id": draft["id"],
            "schedule_digest": schedule_digest,
            "delegation": {
                "grant_id": grant_id,
                "allowed_effects": [effect_id],
                "target_digest": stable_digest(child_target),
                "arguments_digest": stable_digest(child_arguments),
                "scope": child_scope,
                "policy_version": REGISTRY.digest,
                "expires_at": expires_at,
                "max_runs": max_runs,
                "child_actor_kind": "scheduler",
                "child_source_surface": "scheduler",
            },
        },
        arguments={},
        scope="persistent",
        policy_version=REGISTRY.digest,
    )
    return request, draft, requested_enabled, grant_id


def handle_create(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    mgr = _mgr(handler)
    if mgr is None:
        from api_serializers import send_json
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return

    def create() -> dict[str, Any]:
        from authorization_boundary import AuthorizationBoundary, AuthorizationError
        from execution_gateway import ExecutionContext, ExecutionGateway

        payload = dict(body or {})
        action = str(payload.get("authorization_action") or "").strip().lower()

        # A paused draft carries no authority and can be persisted without a grant.
        if not action and not bool(payload.get("enabled", False)):
            draft, _ = _schedule_draft(mgr, payload)
            return {"ok": True, "schedule": _registry(mgr).create(draft)}

        request, draft, requested_enabled, grant_id = _delegation_request(mgr, payload)
        boundary = AuthorizationBoundary()
        interaction_id = str(payload.get("interaction_id") or "").strip()

        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            return {
                "ok": True,
                "schedule_id": draft["id"],
                "delegation_id": grant_id,
                "authorization": {
                    "state": "challenge",
                    "challenge": challenge,
                },
            }

        if action == "approve":
            if str(payload.get("user_decision") or "").strip().lower() != "approve":
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
                "schedule_id": draft["id"],
                "delegation_id": grant_id,
                "authorization": {
                    "state": "authorized",
                    **authorization,
                },
            }

        if action not in {"execute", ""}:
            raise AuthorizationError(
                "authorization_action must be challenge, approve or execute",
                code="authorization_action_invalid",
            )

        permit_token = str(payload.get("authorization_permit") or "").strip()
        gateway = ExecutionGateway(boundary)
        result, authorization = gateway.execute(
            permit_token=permit_token,
            request=request,
            context=ExecutionContext(
                manager=mgr,
                services={"state_dir": _state_dir(mgr)},
            ),
        )
        grant = result.get("delegation_grant") if isinstance(result, dict) else None
        if not isinstance(grant, dict):
            raise RuntimeError("schedule.delegate did not materialize DelegationGrant")

        schedule_payload = {
            **draft,
            "enabled": requested_enabled,
            "delegation_id": str(grant.get("grant_id") or ""),
        }
        try:
            schedule = _registry(mgr).create(schedule_payload)
        except Exception:
            _grants(mgr).revoke(
                str(grant.get("grant_id") or ""),
                reason="schedule_creation_failed_after_grant_issue",
            )
            raise

        return {
            "ok": True,
            "schedule": schedule,
            "delegation_grant": grant,
            "authorization": {
                "state": "consumed",
                "permit_id": authorization.get("permit_id"),
                "decision_id": authorization.get("decision_id"),
                "proof_id": authorization.get("proof_id"),
                "operation_fingerprint": authorization.get("operation_fingerprint"),
            },
        }

    _send_operation(handler, create)


def handle_get(handler: "BaseHTTPRequestHandler", schedule_id: str) -> None:
    mgr = _mgr(handler)
    _send_operation(handler, lambda: {"ok": True, "schedule": _registry(mgr).get(schedule_id)})


def _validated_child_for_schedule(mgr, schedule: dict[str, Any]):
    from delegation_grant import schedule_descriptor_digest
    from execution_request import build_execution_request

    grant_id = str(schedule.get("delegation_id") or "").strip()
    grant = _grants(mgr).get(grant_id)
    effect_id, target, arguments, scope = _child_semantics(mgr, schedule)
    request = build_execution_request(
        effect_id=effect_id,
        actor_kind="scheduler",
        principal_id=str(grant.get("principal_id") or ""),
        session_id=str(getattr(mgr, "session_id", "") or ""),
        source_surface="scheduler",
        target=target,
        arguments=arguments,
        scope=scope,
        policy_version=str(grant.get("policy_version") or ""),
        parent_execution_id=f"schedule:{schedule.get('id')}",
        delegation_id=grant_id,
    )
    schedule_digest = schedule_descriptor_digest(schedule)
    return request, grant, schedule_digest


def handle_update(handler: "BaseHTTPRequestHandler", schedule_id: str, body: dict[str, Any]) -> None:
    mgr = _mgr(handler)

    def update() -> dict[str, Any]:
        from schedule_registry import ScheduleError

        registry = _registry(mgr)
        current = registry.get(schedule_id)
        patch = dict(body or {})
        patch.pop("confirmed", None)
        patch.pop("approved_permissions", None)
        candidate_input = {**current, **patch}
        candidate = registry._validate(candidate_input, creating=False)
        candidate_record = {**current, **candidate}

        from delegation_grant import schedule_descriptor_digest

        if schedule_descriptor_digest(candidate_record) != schedule_descriptor_digest(current):
            raise ScheduleError(
                "Cambiar target o cadencia requiere un nuevo DelegationGrant",
                code="delegation_reauthorization_required",
            )
        if str(candidate_record.get("delegation_id") or "") != str(current.get("delegation_id") or ""):
            raise ScheduleError(
                "delegation_id no puede sustituirse mediante update",
                code="delegation_reauthorization_required",
            )

        if candidate_record.get("enabled"):
            request, grant, schedule_digest = _validated_child_for_schedule(mgr, candidate_record)
            _grants(mgr).validate_child(
                str(grant.get("grant_id") or ""),
                request,
                schedule_id=schedule_id,
                schedule_digest=schedule_digest,
            )

        schedule = registry.update(schedule_id, patch)
        return {"ok": True, "schedule": schedule}

    _send_operation(handler, update)


def handle_delete(handler: "BaseHTTPRequestHandler", schedule_id: str) -> None:
    mgr = _mgr(handler)

    def delete() -> dict[str, Any]:
        from delegation_grant import DelegationError

        registry = _registry(mgr)
        current = registry.get(schedule_id)
        result = registry.delete(schedule_id)
        grant_id = str(current.get("delegation_id") or "").strip()
        if grant_id:
            try:
                grant = _grants(mgr).revoke(grant_id, reason=f"schedule_deleted:{schedule_id}")
            except DelegationError as exc:
                if exc.code != "delegation_not_found":
                    raise
                grant = None
        else:
            grant = None
        return {"ok": True, **result, "delegation_grant": grant}

    _send_operation(handler, delete)


def _execute_target(mgr, schedule: dict[str, Any]) -> dict[str, Any]:
    from authorization_boundary import AuthorizationBoundary
    from execution_gateway import ExecutionContext, ExecutionGateway

    request, grant, schedule_digest = _validated_child_for_schedule(mgr, schedule)
    boundary = AuthorizationBoundary()
    gateway = ExecutionGateway(boundary)

    # Configuration/adapter failure must not consume a DelegationGrant run.
    gateway.adapters.resolve(request.effect_id)

    delegated = boundary.issue_delegated_permit(
        request=request,
        state_dir=_state_dir(mgr),
        schedule_id=str(schedule.get("id") or ""),
        schedule_digest=schedule_digest,
    )
    result, authorization = gateway.execute(
        permit_token=str(delegated["permit"]["token"]),
        request=request,
        context=ExecutionContext(manager=mgr),
    )

    result_dict = dict(result) if isinstance(result, dict) else {"result": result}
    receipt = result_dict.get("receipt")
    receipt_id = ""
    if isinstance(receipt, dict):
        receipt_id = str(receipt.get("receipt_id") or "")
    if not receipt_id:
        receipt_id = str(result_dict.get("receipt_id") or authorization.get("permit_id") or "")

    return {
        "ok": bool(result_dict.get("ok", True)),
        "receipt_id": receipt_id,
        "result": result_dict,
        "authorization": {
            "state": "consumed",
            "delegation_id": str(grant.get("grant_id") or ""),
            "delegation_claim_id": str((delegated.get("delegation") or {}).get("claim_id") or ""),
            "permit_id": authorization.get("permit_id"),
            "decision_id": authorization.get("decision_id"),
            "proof_id": authorization.get("proof_id"),
            "operation_fingerprint": authorization.get("operation_fingerprint"),
        },
    }


def run_schedule(mgr, schedule_id: str) -> dict[str, Any]:
    registry = _registry(mgr)
    schedule = registry.claim(schedule_id)
    try:
        result = _execute_target(mgr, schedule)
    except Exception as exc:
        registry.finish(schedule_id, ok=False, error=str(exc))
        raise
    final = registry.finish(
        schedule_id,
        ok=bool(result.get("ok")),
        receipt_id=str(result.get("receipt_id") or ""),
        error="" if result.get("ok") else str(result.get("result") or "La ejecución falló"),
    )
    return {"ok": bool(result.get("ok")), "schedule": final, "execution": result}


def run_due_schedules(mgr) -> list[dict[str, Any]]:
    registry = _registry(mgr)
    results: list[dict[str, Any]] = []
    for schedule in registry.claim_due():
        schedule_id = str(schedule["id"])
        try:
            result = _execute_target(mgr, schedule)
            final = registry.finish(
                schedule_id,
                ok=bool(result.get("ok")),
                receipt_id=str(result.get("receipt_id") or ""),
                error="" if result.get("ok") else str(result.get("result") or "La ejecución falló"),
            )
            results.append({"ok": bool(result.get("ok")), "schedule": final})
        except Exception as exc:
            final = registry.finish(schedule_id, ok=False, error=str(exc))
            results.append({"ok": False, "schedule": final, "error": str(exc)})
    return results


def handle_run(handler: "BaseHTTPRequestHandler", schedule_id: str) -> None:
    from api_serializers import send_json
    mgr = _mgr(handler)
    try:
        result = run_schedule(mgr, schedule_id)
    except Exception as exc:
        send_json(
            handler,
            409,
            {
                "ok": False,
                "error": str(exc),
                "code": getattr(exc, "code", "schedule_execution_failed"),
            },
        )
        return
    send_json(handler, 200, result)


__all__ = [
    "handle",
    "handle_create",
    "handle_delete",
    "handle_get",
    "handle_run",
    "handle_update",
    "run_due_schedules",
    "run_schedule",
]

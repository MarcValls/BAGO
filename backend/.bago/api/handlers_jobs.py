"""handlers_jobs.py - Pipeline/job endpoints for the BAGO HTTP bridge."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr

    return get_mgr(handler)


def _plan_payload(mgr: Any) -> dict[str, Any]:
    plan = getattr(getattr(mgr, "plan_engine", None), "current_plan", None)
    if not plan:
        return {}
    return {
        "execution_id": f"plan:{getattr(mgr, 'session_id', 'session')}:{str(getattr(plan, 'task', '')).strip().replace(' ', '_')[:48]}",
        "task": plan.task,
        "status": plan.status,
        "started_at": getattr(mgr, "created_at", ""),
        "updated_at": getattr(mgr, "last_switch_at", "") or "",
        "steps": [
            {
                "step_id": f"step-{step.number}",
                "label": step.description,
                "status": step.status,
                "started_at": "",
                "ended_at": "",
                "evidence_id": step.evidence[0] if step.evidence else "",
                "receipt_id": step.receipt_id if step.status == "done" else "",
                "result": step.result,
                "block_reason": step.block_reason,
                "block_code": step.block_code,
            }
            for step in plan.steps
        ],
        "evidence": [
            {"id": step.evidence[0], "type": "step_evidence", "state": step.status}
            for step in plan.steps
            if step.evidence
        ],
    }


def _scheduled_jobs(mgr: Any) -> list[dict[str, Any]]:
    try:
        from handlers_schedule import _serialised_jobs
    except ImportError:
        return []
    try:
        jobs = _serialised_jobs(mgr)
    except (OSError, ValueError):
        return []
    return [{**job, "execution_id": str(job.get("id") or ""), "kind": "schedule", "prompt": str(job.get("name") or "")} for job in jobs]


def _job_list(mgr: Any) -> list[dict[str, Any]]:
    jobs = _scheduled_jobs(mgr)
    plan = _plan_payload(mgr)
    if plan:
        jobs.insert(0, {
            "execution_id": plan["execution_id"],
            "kind": "pipeline",
            "prompt": plan.get("task", ""),
            "status": plan.get("status", ""),
            "started_at": plan.get("started_at", ""),
            "updated_at": plan.get("updated_at", ""),
            "steps": plan.get("steps", []),
            "evidence": plan.get("evidence", []),
        })
    return jobs


def _job_summary(mgr: Any) -> dict[str, Any]:
    jobs = _job_list(mgr)
    counts: dict[str, int] = {}
    for job in jobs:
        key = str(job.get("status") or "unknown").lower()
        counts[key] = counts.get(key, 0) + 1
    scheduled = [job for job in jobs if str(job.get("kind")) == "schedule"]
    pipeline = next((job for job in jobs if str(job.get("kind")) == "pipeline"), {})
    return {
        "ok": True,
        "summary": {
            "total": len(jobs),
            "scheduled": len(scheduled),
            "pipeline": 1 if pipeline else 0,
            "states": counts,
        },
        "active_pipeline": pipeline,
        "jobs": jobs,
    }


def handle_list(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    jobs = _job_list(mgr)
    send_json(handler, 200, {"ok": True, "jobs": jobs, "count": len(jobs)})


def handle_get(handler: "BaseHTTPRequestHandler", execution_id: str) -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    target = str(execution_id or "").strip()
    for job in _job_list(mgr):
        if str(job.get("execution_id") or "") == target:
            send_json(handler, 200, {"ok": True, "job": job})
            return
    send_json(handler, 404, {"ok": False, "state": "blocked", "error_code": "JOB_NOT_FOUND", "message": f"No existe el job {target}"})


def handle_cancel(handler: "BaseHTTPRequestHandler", execution_id: str) -> None:
    from api_serializers import send_json
    from event_bus import emit

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    plan = getattr(getattr(mgr, "plan_engine", None), "current_plan", None)
    if not plan or str(_plan_payload(mgr).get("execution_id", "")) != str(execution_id or "").strip():
        send_json(handler, 409, {"ok": False, "state": "blocked", "error_code": "JOB_CANCEL_UNAVAILABLE", "message": "No hay un pipeline activo cancelable"})
        return
    if hasattr(mgr.plan_engine, "reset"):
        mgr.plan_engine.reset()
    send_json(handler, 200, {"ok": True, "state": "done", "execution_id": execution_id, "message": "Pipeline cancelado"})
    emit("job.cancelled", {"execution_id": execution_id})


def handle_retry(handler: "BaseHTTPRequestHandler", execution_id: str) -> None:
    from api_serializers import send_json
    from event_bus import emit

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    target = str(execution_id or "").strip()
    plan = getattr(getattr(mgr, "plan_engine", None), "current_plan", None)
    if not plan or str(_plan_payload(mgr).get("execution_id", "")) != target:
        send_json(handler, 404, {"ok": False, "state": "blocked", "error_code": "JOB_NOT_FOUND", "message": f"No existe el job {target}"})
        return
    for step in plan.steps:
        if step.status in {"failed", "blocked"}:
            step.status = "pending"
            step.block_reason = ""
            step.block_code = ""
            step.result = ""
    plan.status = "pending"
    send_json(handler, 200, {"ok": True, "state": "done", "execution_id": target, "job": _plan_payload(mgr), "message": "Pipeline preparado para reintento"})
    emit("job.retried", {"execution_id": target})


def handle_summary(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "state": "blocked", "error_code": "SESSION_MANAGER_MISSING", "message": "SessionManager no disponible"})
        return
    send_json(handler, 200, _job_summary(mgr))


# ─── Plan execution API (extends PlanEngine with action execution) ────────

def _plan_executor(mgr: Any):
    """Construye un executor que el PlanEngine invoca para cada step.

    Firma: (action, payload, step) -> resultado estructurado con recibo propio.
    El step lleva model_hint / model_provider / model_name para routing.
    """
    import hashlib
    import json
    def _resolve_model(step: Any) -> dict:
        """Resuelve qué provider/modelo usar para un step.

        Prioridad:
          1. model_provider + model_name explícitos en el step
          2. model_hint que coincide con un provider/modelo activo
          3. provider/modelo activo del SessionManager
        Devuelve dict con {provider, model, source} para diagnóstico.
        """
        explicit_provider = getattr(step, "model_provider", "") or ""
        explicit_model = getattr(step, "model_name", "") or ""
        hint = getattr(step, "model_hint", "") or ""

        # 1) Explícitos
        if explicit_provider or explicit_model:
            return {
                "provider": explicit_provider or getattr(mgr, "provider_name", "default"),
                "model": explicit_model or getattr(mgr, "active_model", "default"),
                "source": "explicit",
            }

        # 2) Hint
        if hint:
            # Si el hint es un perfil del router (fast/balanced/capable/...)
            profile_map = {
                "fast": "llama3.2:1b",           # rápido, barato
                "balanced": "llama3.2:3b",        # medio
                "capable": "qwen3.6:latest",      # capaz pero lento
                "code-reviewer": "bago-orchestrator:latest",
            }
            if hint in profile_map:
                target_model = profile_map[hint]
                return {
                    "provider": "ollama-local",
                    "model": target_model,
                    "source": f"hint:{hint}",
                }
            # Si el hint es un nombre de modelo, usarlo directo
            if ":" in hint or "-" in hint or "." in hint:
                return {
                    "provider": "ollama-local",
                    "model": hint,
                    "source": f"hint:model={hint}",
                }
            # Si no matchea nada, caemos al provider activo

        # 3) Provider activo
        return {
            "provider": getattr(mgr, "provider_name", "default"),
            "model": getattr(mgr, "active_model", "default"),
            "source": "active",
        }

    def _receipt(action: str, payload: dict, evidence: list[str]) -> str:
        material = json.dumps(
            {"action": action, "payload": payload, "evidence": evidence},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        return f"plan-step:sha256:{hashlib.sha256(material).hexdigest()}"

    def _success(action: str, payload: dict, result: str, evidence: list[str]) -> dict[str, Any]:
        return {
            "ok": True,
            "executed": True,
            "result": result,
            "error": "",
            "evidence": evidence,
            "receipt_id": _receipt(action, payload, evidence),
        }

    def _failure(error: str, *, blocked: bool = False, code: str = "") -> dict[str, Any]:
        return {
            "ok": False,
            "executed": False,
            "result": "",
            "error": error,
            "evidence": ["blocked" if blocked else "failed"],
            "receipt_id": "",
            "blocked": blocked,
            "block_code": code,
        }

    def _exec(action: str, payload: dict, step: Any = None) -> dict[str, Any]:
        try:
            if action == "write_file":
                return _failure(
                    "plan_execution_gateway_unavailable",
                    blocked=True,
                    code="plan_execution_gateway_missing",
                )

            if action == "read_file":
                return _failure(
                    "plan_execution_gateway_unavailable",
                    blocked=True,
                    code="plan_execution_gateway_missing",
                )

            if action == "run_command":
                cmd = str(payload.get("command", "")).strip()
                if not cmd:
                    return _failure("command vacío")
                # ``mgr.send`` es conversación, no ejecución de comandos.
                # Hasta que exista un gateway de comandos con política y recibo
                # material, este tipo de paso debe quedar bloqueado.
                return _failure(
                    "command_execution_gateway_unavailable",
                    blocked=True,
                    code="command_gateway_missing",
                )

            if action == "request_approval":
                return _failure("approval_required", blocked=True, code="approval_required")

            if action == "noop" or not action:
                return _failure("no_executable_action", blocked=True, code="noop_not_execution")

            return _failure(f"acción no soportada: {action}", blocked=True, code="unsupported_action")
        except Exception as exc:
            return _failure(f"excepción: {exc}")

    return _exec


def handle_plans_list(handler: "BaseHTTPRequestHandler") -> None:
    """GET /plans — lista todos los planes de la sesión."""
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    engine = getattr(mgr, "plan_engine", None)
    if engine is None:
        send_json(handler, 200, {"ok": True, "plans": []})
        return
    plans = [engine.to_dict(p) for p in engine.list_plans()]
    send_json(handler, 200, {"ok": True, "plans": plans})


def handle_plans_get(handler: "BaseHTTPRequestHandler", plan_id: str) -> None:
    """GET /plans/<id> — devuelve un plan con su estado actual."""
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    engine = getattr(mgr, "plan_engine", None)
    plan = engine.get_plan(plan_id) if engine else None
    if plan is None:
        send_json(handler, 404, {"ok": False, "error": f"plan {plan_id} no encontrado"})
        return
    send_json(handler, 200, {"ok": True, "plan": engine.to_dict(plan)})


def _plan_execution_request(mgr: Any, plan: Any):
    from execution_request import build_execution_request
    from governed_work_pipeline import plan_execution_target
    from effect_registry import REGISTRY

    return build_execution_request(
        effect_id="plan.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=str(getattr(mgr, "session_id", "") or ""),
        source_surface="api.plans.execute",
        target=plan_execution_target(plan),
        arguments={},
        scope=REGISTRY.get("plan.execute").default_scope,
        policy_version=REGISTRY.digest,
    )


def handle_plans_execute(handler: "BaseHTTPRequestHandler", plan_id: str, body: dict) -> None:
    """POST /plans/<id>/execute — challenge/approve/execute through the gateway."""
    from api_serializers import send_json
    from authorization_boundary import AuthorizationBoundary, AuthorizationError
    from execution_gateway import ExecutionContext, ExecutionGateway, ExecutionGatewayError
    from execution_request import ExecutionRequestError
    from governed_work_pipeline import GovernedWorkError

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    engine = getattr(mgr, "plan_engine", None)
    plan = engine.get_plan(plan_id) if engine else None
    if plan is None:
        send_json(handler, 404, {"ok": False, "error": f"plan {plan_id} no encontrado"})
        return

    try:
        request = _plan_execution_request(mgr, plan)
        boundary = AuthorizationBoundary()
        payload = dict(body or {})
        action = str(payload.get("authorization_action") or "").strip().lower()
        interaction_id = str(payload.get("interaction_id") or "").strip()

        if action == "challenge":
            challenge = boundary.create_challenge(request, interaction_id=interaction_id)
            send_json(handler, 200, {
                "ok": True,
                "plan_id": plan_id,
                "authorization": {"state": "challenge", "challenge": challenge},
            })
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
            send_json(handler, 200, {
                "ok": True,
                "plan_id": plan_id,
                "authorization": {"state": "authorized", **authorization},
            })
            return

        if action not in {"", "execute"}:
            raise AuthorizationError(
                "authorization_action must be challenge, approve or execute",
                code="authorization_action_invalid",
            )

        result, authorization = ExecutionGateway(boundary).execute(
            permit_token=str(payload.get("authorization_permit") or ""),
            request=request,
            context=ExecutionContext(manager=mgr),
        )
        response = dict(result) if isinstance(result, dict) else {"result": result}
        response.update({
            "plan_id": plan_id,
            "plan": engine.to_dict(plan),
            "authorization": {
                "state": "consumed",
                "permit_id": authorization.get("permit_id"),
                "decision_id": authorization.get("decision_id"),
                "proof_id": authorization.get("proof_id"),
                "operation_fingerprint": authorization.get("operation_fingerprint"),
            },
        })
        send_json(handler, 200 if bool(response.get("ok")) else 409, response)
    except AuthorizationError as exc:
        status = 409 if exc.code in {
            "authorization_challenge_not_pending",
            "authorization_challenge_expired",
            "authorization_permit_replay",
            "authorization_permit_expired",
            "authorization_operation_mismatch",
        } else 403
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code, "plan_id": plan_id})
    except (ExecutionRequestError, GovernedWorkError) as exc:
        send_json(handler, 400 if isinstance(exc, ExecutionRequestError) else 409, {
            "ok": False,
            "error": str(exc),
            "code": getattr(exc, "code", "plan_contract_invalid"),
            "plan_id": plan_id,
        })
    except ExecutionGatewayError as exc:
        send_json(handler, 409, {
            "ok": False,
            "error": str(exc),
            "code": exc.code,
            "plan_id": plan_id,
        })


def handle_plans_create(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /plans — crea un plan a partir de un task.

    Body: {"task": "descripción", "auto_execute": false}
    Si auto_execute=true, ejecuta el plan tras crearlo.
    """
    from api_serializers import send_json
    from event_bus import emit
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    if not isinstance(body, dict) or not str(body.get("task", "")).strip():
        send_json(handler, 400, {"ok": False, "error": "task requerido"})
        return

    task = str(body["task"]).strip()
    engine = getattr(mgr, "plan_engine", None)
    if engine is None:
        send_json(handler, 503, {"ok": False, "error": "PlanEngine no disponible"})
        return

    # Genera el plan con el LLM (mismo flujo que /plan)
    prompt = engine.generate_prompt(task)
    try:
        response = mgr.send(prompt)
    except Exception as exc:
        send_json(handler, 504, {"ok": False, "error": f"modelo no respondió: {exc}"})
        return
    plan = engine.create_plan_with_actions(task, response)
    plan_id = engine.register_plan(plan)

    emit("plan.created", {"plan_id": plan_id, "task": task})

    if bool(body.get("auto_execute")):
        send_json(handler, 409, {
            "ok": False,
            "state": "blocked",
            "error_code": "PLAN_EXECUTION_AUTHORIZATION_REQUIRED",
            "message": "El plan se ha creado; auto_execute requiere challenge/approve y ejecución por POST /plans/<id>/execute.",
            "plan_id": plan_id,
            "plan": engine.to_dict(plan),
        })
        return

    send_json(handler, 200, {"ok": True, "plan_id": plan_id, "plan": engine.to_dict(plan)})

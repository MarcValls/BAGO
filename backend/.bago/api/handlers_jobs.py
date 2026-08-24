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
                "receipt_id": getattr(getattr(mgr, "last_receipt", None), "envelope_id", "") if step.status == "done" else "",
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

    Firma: (action, payload, step) -> (ok, result, error)
    El step lleva model_hint / model_provider / model_name para routing.
    """
    import os
    from pathlib import Path

    base = Path(getattr(mgr, "base_path", Path.cwd())).resolve()

    def _safe_path(rel: str) -> Path:
        """Resuelve un path relativo al workspace, sin escapar del sandbox.

        Si el path es absoluto (Linux-style /home/... o Windows-style
        C:\\...), se trata como relativo al workspace: se quita la raiz
        y se resuelve dentro del sandbox.
        """
        # Quitar raiz absoluta (Linux /home/x/foo → foo, Windows C:\x\foo → x\foo)
        normalized = rel.strip()
        # Linux absolute: /home/user/foo, /tmp/foo, /etc/foo → foo
        if normalized.startswith("/"):
            parts = [p for p in Path(normalized).parts if p and p not in ("/", "home", "tmp", "etc", "var", "usr", "opt", "root", "Users")]
            normalized = str(Path(*parts)) if parts else Path(normalized).name
        # Windows absolute: C:\Users\x\foo, D:/x/foo → x\foo
        if len(normalized) >= 2 and normalized[1] == ":":
            normalized = normalized[2:].lstrip("/\\")
        # Quitar prefijos comunes
        for prefix in ("home/user/", "home/admin/", "Users/user/", "Documents/"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        candidate = (base / normalized).resolve() if normalized else base
        # Permitir dentro del sandbox; bloquear escapes
        if base in candidate.parents or candidate == base or normalized == "":
            return candidate
        # Fallback seguro: solo el nombre del archivo en el root
        return (base / Path(rel).name).resolve()

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

    def _exec(action: str, payload: dict, step: Any = None) -> tuple[bool, str, str]:
        try:
            if action == "write_file":
                rel = str(payload.get("path", "")).strip()
                content = str(payload.get("content", ""))
                if not rel:
                    return False, "", "path vacío"
                p = _safe_path(rel)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                return True, f"escrito: {rel} ({len(content)} bytes)", ""

            if action == "read_file":
                rel = str(payload.get("path", "")).strip()
                if not rel:
                    return False, "", "path vacío"
                p = _safe_path(rel)
                if not p.exists():
                    return False, "", f"no existe: {rel}"
                content = p.read_text(encoding="utf-8", errors="replace")
                return True, content[:500], ""

            if action == "run_command":
                cmd = str(payload.get("command", "")).strip()
                if not cmd:
                    return False, "", "command vacío"
                # Resolver modelo via routing si el step lo declara
                routing = _resolve_model(step) if step is not None else None
                routing_info = f" [modelo: {routing['model']} via {routing['source']}]" if routing else ""
                # Ejecuta con el modelo resuelto. Si mgr.chat lo soporta,
                # usa el modelo del step; si no, usa el provider activo.
                result = None
                if routing and hasattr(mgr, "send_with_model"):
                    result = mgr.send_with_model(cmd, routing["provider"], routing["model"])
                elif hasattr(mgr, "send"):
                    result = mgr.send(cmd)
                if result is None:
                    return False, "", "send no disponible"
                msg = str(result)[:500]
                return True, msg + routing_info, ""

            if action == "request_approval":
                return False, "", "approval_required"

            if action == "noop" or not action:
                return True, "noop", ""

            return False, "", f"acción no soportada: {action}"
        except Exception as exc:
            return False, "", f"excepción: {exc}"

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


def handle_plans_execute(handler: "BaseHTTPRequestHandler", plan_id: str, body: dict) -> None:
    """POST /plans/<id>/execute — ejecuta el plan paso a paso.

    Body opcional: {"stop_on_failure": bool} (default True)
    """
    from api_serializers import send_json
    from event_bus import emit
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    engine = getattr(mgr, "plan_engine", None)
    plan = engine.get_plan(plan_id) if engine else None
    if plan is None:
        send_json(handler, 404, {"ok": False, "error": f"plan {plan_id} no encontrado"})
        return

    # Inyecta el executor (idempotente)
    engine.set_executor(_plan_executor(mgr))

    stop_on_failure = True
    if isinstance(body, dict) and "stop_on_failure" in body:
        stop_on_failure = bool(body["stop_on_failure"])

    emit("plan.execution.started", {"plan_id": plan_id, "task": plan.task})
    result = engine.execute_plan(plan, stop_on_failure=stop_on_failure)
    emit("plan.execution.completed", {
        "plan_id": plan_id,
        "ok": result["ok"],
        "completed": result["completed"],
        "failed": result["failed"],
        "executed": result.get("executed", result["completed"]),
        "informational": result.get("informational", 0),
    })
    send_json(handler, 200, {
        "ok": result["ok"],
        "plan_id": plan_id,
        "completed": result["completed"],
        "failed": result["failed"],
        "executed": result.get("executed", result["completed"]),
        "informational": result.get("informational", 0),
        "status": result.get("status", plan.status),
        "error": result.get("error", ""),
        "results": result["results"]
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
        engine.set_executor(_plan_executor(mgr))
        exec_result = engine.execute_plan(plan)
        emit("plan.execution.completed", {"plan_id": plan_id, "ok": exec_result["ok"]})
        send_json(handler, 200, {
            "ok": exec_result["ok"],
            "plan_id": plan_id,
            "plan": engine.to_dict(plan),
            "execution": exec_result
        })
        return

    send_json(handler, 200, {"ok": True, "plan_id": plan_id, "plan": engine.to_dict(plan)})

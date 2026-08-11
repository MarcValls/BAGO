"""Persistent schedule CRUD and execution handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _mgr(handler):
    from api_state import get_mgr
    return get_mgr(handler)


def _registry(mgr):
    from schedule_registry import ScheduleRegistry
    base_path = Path(getattr(mgr, "base_path", Path.cwd()))
    return ScheduleRegistry(base_path / ".bago" / "state")


def _send_operation(handler: "BaseHTTPRequestHandler", operation) -> None:
    from api_serializers import send_json
    from schedule_registry import ScheduleError
    try:
        payload = operation()
    except ScheduleError as exc:
        status = 404 if exc.code == "not_found" else 409 if exc.code in {"conflict", "running", "confirmation_required"} else 400
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
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


def handle_create(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    mgr = _mgr(handler)
    if mgr is None:
        from api_serializers import send_json
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    _send_operation(handler, lambda: {"ok": True, "schedule": _registry(mgr).create(body or {})})


def handle_get(handler: "BaseHTTPRequestHandler", schedule_id: str) -> None:
    mgr = _mgr(handler)
    _send_operation(handler, lambda: {"ok": True, "schedule": _registry(mgr).get(schedule_id)})


def handle_update(handler: "BaseHTTPRequestHandler", schedule_id: str, body: dict[str, Any]) -> None:
    mgr = _mgr(handler)
    _send_operation(handler, lambda: {"ok": True, "schedule": _registry(mgr).update(schedule_id, body or {})})


def handle_delete(handler: "BaseHTTPRequestHandler", schedule_id: str) -> None:
    mgr = _mgr(handler)
    _send_operation(handler, lambda: {"ok": True, **_registry(mgr).delete(schedule_id)})


def _execute_target(mgr, schedule: dict[str, Any]) -> dict[str, Any]:
    target_type = schedule["target_type"]
    target = schedule["target"]
    if target_type == "task":
        from handlers_jobs import _plan_executor
        task = str(target.get("task") or "").strip()
        if not task:
            raise ValueError("La programación no contiene target.task")
        engine = mgr.plan_engine
        response = mgr.send(engine.generate_prompt(task))
        plan = engine.create_plan_with_actions(task, response)
        plan_id = engine.register_plan(plan)
        engine.set_executor(_plan_executor(mgr))
        result = engine.execute_plan(plan)
        return {"ok": bool(result["ok"]), "receipt_id": f"plan:{plan_id}", "result": result}
    if target_type == "plan":
        from handlers_jobs import _plan_executor
        plan_id = str(target.get("plan_id") or "").strip()
        plan = mgr.plan_engine.get_plan(plan_id)
        if plan is None:
            raise ValueError(f"Plan no encontrado: {plan_id}")
        mgr.plan_engine.set_executor(_plan_executor(mgr))
        result = mgr.plan_engine.execute_plan(plan)
        return {"ok": bool(result["ok"]), "receipt_id": f"plan:{plan_id}", "result": result}
    if target_type == "capability":
        from capability_packages import execute_package
        capability_id = str(target.get("capability_id") or "").strip()
        result = execute_package(
            capability_id,
            inputs=target.get("input", {}),
            confirmed=True,
            approved_permissions=schedule.get("approved_permissions", []),
        )
        receipt = result.get("receipt", {})
        return {"ok": bool(result.get("ok")), "receipt_id": str(receipt.get("receipt_id") or ""), "result": result}
    if target_type == "pipeline":
        try:
            from package_contract import execute_pipeline_package
        except ImportError as exc:
            raise ValueError("El runtime de paquetes Pipeline no está disponible") from exc
        result = execute_pipeline_package(
            str(target.get("pipeline_id") or ""),
            inputs=target.get("input", {}),
            confirmed=True,
            approved_permissions=schedule.get("approved_permissions", []),
            manager=mgr,
        )
        return {"ok": bool(result.get("ok")), "receipt_id": str(result.get("receipt_id") or ""), "result": result}
    raise ValueError(f"Target no soportado: {target_type}")


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
        send_json(handler, 409, {"ok": False, "error": str(exc)})
        return
    send_json(handler, 200, result)

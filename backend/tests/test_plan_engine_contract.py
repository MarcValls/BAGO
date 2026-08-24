from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"


def test_plan_engine_done_requires_evidence_and_blocked_is_structured():
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan("Cerrar requisito", "1. Ejecutar paso\n2. Bloquear paso")
    step1 = plan.steps[0]
    step2 = plan.steps[1]

    try:
        engine.mark_step(step1, "done", "resultado sin evidencia")
        raise AssertionError("done sin evidencia debía fallar")
    except ValueError as exc:
        assert "evidencia" in str(exc)

    engine.mark_step(step1, "done", "resultado", evidence=("prueba:ok",))
    assert step1.status == "done"
    assert engine.current_plan.status == "pending"

    engine.block_step(step2, "dependencia ausente", code="dep_missing")
    assert step2.status == "blocked"
    assert step2.block_reason == "dependencia ausente"
    assert step2.block_code == "dep_missing"
    assert engine.current_plan.status == "blocked"


def test_plan_engine_rejects_invalid_status():
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan("Validar estado", "1. Paso")

    try:
        engine.mark_step(plan.steps[0], "certified")
        raise AssertionError("estado inválido debía fallar")
    except ValueError as exc:
        assert "Estado inválido" in str(exc)


def test_plan_step_parser_handles_repeated_prefixes_linearly():
    from plan_engine import PlanEngine

    adversarial = "Paso 1: " + ("99.paso " * 10_000) + "terminar comprobacion"
    steps = PlanEngine.parse_steps(adversarial)

    assert len(steps) == 1
    assert steps[0].description.endswith("terminar comprobacion")


def test_informational_plan_never_reports_execution_success():
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Crear una aplicación",
        "1. Definir los datos\n2. Diseñar la interfaz\n3. Revisar el resultado",
    )

    result = engine.execute_plan(plan)

    assert result["ok"] is False
    assert result["executed"] == 0
    assert result["completed"] == 0
    assert result["failed"] == 0
    assert result["informational"] == 3
    assert result["error"] == "no_executable_actions"
    assert plan.status == "pending"
    assert all(step.status == "pending" for step in plan.steps)
    assert all(step.evidence == () for step in plan.steps)
    assert all(item["executed"] is False for item in result["results"])
    rendered = json.dumps(result, ensure_ascii=False).casefold()
    assert "plan ejecutado" not in rendered
    assert "ejecución completada" not in rendered


def test_empty_plan_is_not_reported_as_execution_success():
    from plan_engine import Plan, PlanEngine

    engine = PlanEngine()
    plan = Plan(task="Petición sin pasos")

    result = engine.execute_plan(plan)

    assert result == {
        "ok": False,
        "completed": 0,
        "failed": 0,
        "executed": 0,
        "informational": 0,
        "status": "pending",
        "error": "no_executable_actions",
        "results": [],
    }
    assert plan.steps == []
    rendered = json.dumps(result, ensure_ascii=False).casefold()
    assert "plan ejecutado" not in rendered
    assert "ejecución completada" not in rendered


def test_mixed_plan_counts_only_material_actions_as_completed():
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Preparar y verificar un archivo",
        "1. Revisar el objetivo\n2. Ejecutar echo verificado",
    )
    engine.set_executor(lambda action, payload, step: {
        "ok": True,
        "executed": True,
        "result": "verificado",
        "error": "",
        "evidence": ["command_exit:0"],
        "receipt_id": "receipt:step-2",
    })

    result = engine.execute_plan(plan)

    assert result["ok"] is False
    assert result["executed"] == 1
    assert result["completed"] == 1
    assert result["informational"] == 1
    assert result["partial"] is True
    assert result["error"] == "partial_execution"
    assert plan.steps[0].status == "pending"
    assert plan.steps[1].status == "done"
    assert plan.steps[1].receipt_id == "receipt:step-2"


def test_legacy_executor_success_without_receipt_is_rejected():
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan_with_actions("Ejecutar build", "1. Ejecutar npm run build")
    engine.set_executor(lambda action, payload, step: (True, "Te explico cómo hacerlo", ""))

    result = engine.execute_plan(plan)

    assert result["ok"] is False
    assert result["executed"] == 0
    assert result["failed"] == 1
    assert plan.steps[0].status == "failed"
    assert plan.steps[0].receipt_id == ""
    assert result["results"][0]["error"] == "missing_execution_receipt"


def test_completed_steps_are_not_counted_as_new_execution_on_retry():
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan_with_actions("Leer archivo", "1. Leer archivo README.md")
    engine.set_executor(lambda action, payload, step: {
        "ok": True,
        "executed": True,
        "result": "contenido",
        "error": "",
        "evidence": ["file_sha256:abc"],
        "receipt_id": "receipt:read-1",
    })

    first = engine.execute_plan(plan)
    second = engine.execute_plan(plan)

    assert first["ok"] is True
    assert first["executed"] == 1
    assert second["ok"] is False
    assert second["executed"] == 0
    assert second["completed"] == 0
    assert second["already_completed"] == 1
    assert second["total_completed"] == 1
    assert second["error"] == "no_new_actions"


def test_job_executor_does_not_treat_model_reply_as_command_execution(tmp_path):
    from handlers_jobs import _plan_executor
    from plan_engine import PlanEngine

    class FakeManager:
        base_path = tmp_path

        def send(self, command):
            return f"Te explico cómo ejecutar {command}"

    engine = PlanEngine()
    plan = engine.create_plan_with_actions("Build", "1. Ejecutar npm run build")
    engine.set_executor(_plan_executor(FakeManager()))

    result = engine.execute_plan(plan)

    assert result["ok"] is False
    assert result["executed"] == 0
    assert result["blocked"] == 1
    assert plan.steps[0].status == "blocked"
    assert plan.steps[0].block_code == "command_gateway_missing"
    assert plan.steps[0].receipt_id == ""

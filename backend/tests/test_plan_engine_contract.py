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


def test_mixed_plan_counts_only_material_actions_as_completed():
    from plan_engine import PlanEngine

    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Preparar y verificar un archivo",
        "1. Revisar el objetivo\n2. Ejecutar echo verificado",
    )
    engine.set_executor(lambda action, payload, step: (True, "verificado", ""))

    result = engine.execute_plan(plan)

    assert result["ok"] is True
    assert result["executed"] == 1
    assert result["completed"] == 1
    assert result["informational"] == 1
    assert plan.steps[0].status == "pending"
    assert plan.steps[1].status == "done"

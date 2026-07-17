from __future__ import annotations

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

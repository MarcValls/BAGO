#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
plan_engine.py â€” BAGO 4.1.5 Plan Engine

Genera y ejecuta planes paso a paso usando el provider activo.
Mantiene el plan en la sesiÃ³n para ejecuciÃ³n progresiva.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    """Un paso de un plan."""
    number: int
    description: str
    status: str = "pending"  # pending | running | done | failed
    result: str = ""


@dataclass
class Plan:
    """Plan generado con pasos numerados."""
    task: str
    steps: list[Step] = field(default_factory=list)
    status: str = "draft"  # draft | running | done | failed

    def to_text(self) -> str:
        lines = [f"ðŸ“‹ Plan: {self.task}", ""]
        for step in self.steps:
            icon = {
                "pending": "â—‹",
                "running": "â—",
                "done": "âœ“",
                "failed": "âœ—",
            }.get(step.status, "â—‹")
            lines.append(f"  {icon} {step.number}. {step.description}")
        return "\n".join(lines)


class PlanEngine:
    """Genera planes usando el provider activo y los ejecuta paso a paso."""

    def __init__(self) -> None:
        self.current_plan: Plan | None = None

    @staticmethod
    def parse_steps(text: str) -> list[Step]:
        """Extrae pasos numerados de una respuesta de modelo."""
        steps: list[Step] = []
        # Busca lÃ­neas que empiecen con nÃºmero + punto o guiÃ³n
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Patrones: "1. Paso", "1) Paso", "- Paso", "Step 1: Paso"
            match = re.match(r"^(?:\d+[.\)]\s*|[-*]\s+|(?:Paso\s+|Step\s+)\d+[:.]?\s*)*(.+)$", line, re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if desc and len(desc) > 5:
                    steps.append(Step(number=len(steps) + 1, description=desc))
        return steps

    def generate_prompt(self, task: str) -> str:
        """Prompt para pedir un plan paso a paso al modelo."""
        return (
            f"Genera un plan paso a paso conciso para esta tarea: {task}\n\n"
            "Responde SOLO con una lista numerada de pasos. "
            "Cada paso debe ser una acciÃ³n concreta y ejecutable. "
            "No incluyas explicaciones adicionales."
        )

    def create_plan(self, task: str, model_response: str) -> Plan:
        """Crea un Plan a partir de la respuesta del modelo."""
        steps = self.parse_steps(model_response)
        if not steps:
            # Fallback: si no parseÃ³ bien, crea un paso con todo el texto
            steps = [Step(number=1, description=model_response.strip()[:200])]
        plan = Plan(task=task, steps=steps)
        self.current_plan = plan
        return plan

    def get_next_step(self) -> Step | None:
        """Retorna el siguiente paso pendiente."""
        if not self.current_plan:
            return None
        for step in self.current_plan.steps:
            if step.status == "pending":
                return step
        return None

    def mark_step(self, step: Step, status: str, result: str = "") -> None:
        step.status = status
        if result:
            step.result = result
        # Actualizar estado del plan
        if self.current_plan:
            if all(s.status in ("done", "failed") for s in self.current_plan.steps):
                self.current_plan.status = "done" if any(s.status == "done" for s in self.current_plan.steps) else "failed"
            elif any(s.status == "running" for s in self.current_plan.steps):
                self.current_plan.status = "running"

    def reset(self) -> None:
        self.current_plan = None


def _run_tests() -> int:
    engine = PlanEngine()

    # Test parse_steps
    text = """1. Instalar dependencias
    2. Crear archivo main.py
    3. Ejecutar tests
    4. Revisar resultados"""
    steps = engine.parse_steps(text)
    assert len(steps) == 4
    assert steps[0].description == "Instalar dependencias"
    assert steps[3].number == 4

    # Test plan creation
    plan = engine.create_plan("Crear una API", text)
    assert plan.task == "Crear una API"
    assert len(plan.steps) == 4
    assert "Crear una API" in plan.to_text()

    # Test next step
    next_step = engine.get_next_step()
    assert next_step and next_step.number == 1

    engine.mark_step(next_step, "done", "ok")
    next_step = engine.get_next_step()
    assert next_step and next_step.number == 2

    print("plan_engine.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

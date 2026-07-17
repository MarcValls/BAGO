#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
plan_engine.py — BAGO 4.1.5 Plan Engine

Genera y ejecuta planes paso a paso usando el provider activo.
Mantiene el plan en la sesión para ejecución progresiva.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Any

VALID_STEP_STATUSES = ("pending", "running", "done", "failed", "blocked")
VALID_PLAN_STATUSES = VALID_STEP_STATUSES


@dataclass
class Step:
    """Un paso de un plan."""
    number: int
    description: str
    status: str = "pending"  # pending | running | done | failed | blocked
    result: str = ""
    required_evidence: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    block_reason: str = ""
    block_code: str = ""
    # Acción ejecutable asociada. Si action es None, el step es solo
    # informativo (descripción humana sin acción automática).
    action: str | None = None
    action_payload: dict = field(default_factory=dict)
    # Routing por step: qué provider/modelo usar para este step concreto.
    # Si está vacío, se usa el provider activo del SessionManager.
    # model_hint: "fast" | "balanced" | "capable" | "code-reviewer" | ...
    #   o un nombre de perfil del router. El executor lo traduce.
    # model_provider: provider_id concreto ("ollama-local", "anthropic", ...)
    # model_name: modelo concreto ("qwen3.6:latest", "claude-3-5-sonnet")
    # Si model_provider está pero no model_name, se usa el default del provider.
    model_hint: str = ""
    model_provider: str = ""
    model_name: str = ""


@dataclass
class Plan:
    """Plan generado con pasos numerados."""
    task: str
    steps: list[Step] = field(default_factory=list)
    status: str = "pending"  # pending | running | done | failed | blocked
    id: str = ""  # uuid; lo asigna PlanEngine al crear
    created_at: str = ""  # ISO timestamp

    def to_text(self) -> str:
        lines = [f"📋 Plan: {self.task}", ""]
        for step in self.steps:
            icon = {
                "pending": "○",
                "running": "◐",
                "done": "✓",
                "failed": "✗",
                "blocked": "⧖",
            }.get(step.status, "○")
            extra = []
            if step.required_evidence:
                extra.append(f"evidencia={len(step.required_evidence)}")
            if step.evidence:
                extra.append(f"aportes={len(step.evidence)}")
            if step.block_reason:
                extra.append(f"bloqueo={step.block_reason}")
            suffix = f" [{' | '.join(extra)}]" if extra else ""
            lines.append(f"  {icon} {step.number}. {step.description}{suffix}")
        return "\n".join(lines)


class PlanEngine:
    """Genera planes usando el provider activo y los ejecuta paso a paso."""

    # Tipos de acción que un step puede llevar a cabo
    VALID_ACTIONS = (
        "write_file",     # escribe un archivo en disco
        "read_file",      # lee un archivo y devuelve su contenido
        "run_command",    # ejecuta un comando del backend (via runCommand)
        "request_approval",  # pide aprobación humana antes de continuar
        "noop",           # paso informativo, no ejecuta nada
    )

    def __init__(self) -> None:
        self.current_plan: Plan | None = None
        # Historial de planes en esta sesión: {id: Plan}
        self.plans: dict[str, Plan] = {}
        # Hooks para ejecutar (inyectados desde SessionManager o tests)
        self._executor = None  # type: ignore[assignment]

    @staticmethod
    def parse_steps(text: str) -> list[Step]:
        """Extrae pasos numerados de una respuesta de modelo."""
        steps: list[Step] = []
        # Busca líneas que empiecen con número + punto o guión
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
        """Prompt para pedir un plan paso a paso al modelo.

        El prompt le dice al LLM que es un orquestador y que el plan
        se ejecutará automáticamente. El motor parsea las acciones
        con interpret_step (reconoce 'Crear archivo X con contenido Y',
        'Leer archivo X', 'Ejecutar X', 'Pedir aprobación').
        """
        return (
            f"Tarea: {task}\n\n"
            "Eres el orquestador de BAGO. Genera un plan numerado y ejecutable.\n"
            "Cada paso debe ser una acción concreta en uno de estos formatos EXACTOS:\n"
            "- 'Crear archivo <ruta> con contenido: <contenido>'\n"
            "- 'Leer archivo <ruta>'\n"
            "- 'Ejecutar <comando>'\n"
            "- 'Pedir aprobación <descripción>'\n\n"
            "Si el paso es informativo (no ejecutable), usa lenguaje natural\n"
            "sin esos prefijos. Añade 'con modelo <nombre>' o 'rápido'/'capaz'\n"
            "al final del paso para asignar el modelo.\n\n"
            "Responde SOLO con la lista numerada. Sin explicaciones.\n"
        )

    def create_plan(self, task: str, model_response: str) -> Plan:
        """Crea un Plan a partir de la respuesta del modelo."""
        steps = self.parse_steps(model_response)
        if not steps:
            # Fallback: si no parseó bien, crea un paso con todo el texto
            steps = [Step(number=1, description=model_response.strip()[:200])]
        plan = Plan(task=task, steps=steps)
        self.current_plan = plan
        return plan

    @staticmethod
    def _coerce_status(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized not in VALID_STEP_STATUSES:
            raise ValueError(f"Estado inválido: {status}")
        return normalized

    def get_next_step(self) -> Step | None:
        """Retorna el siguiente paso pendiente."""
        if not self.current_plan:
            return None
        for step in self.current_plan.steps:
            if step.status == "pending":
                return step
        return None

    def mark_step(
        self,
        step: Step,
        status: str,
        result: str = "",
        *,
        evidence: tuple[str, ...] | list[str] | None = None,
        block_reason: str = "",
        block_code: str = "",
    ) -> None:
        normalized = self._coerce_status(status)
        evidence_tuple = tuple(str(item) for item in (evidence or ()))
        if normalized == "done" and not evidence_tuple:
            raise ValueError("done requiere evidencia")
        step.status = normalized
        if result:
            step.result = result
        step.evidence = evidence_tuple
        step.block_reason = block_reason if normalized == "blocked" else ""
        step.block_code = block_code if normalized == "blocked" else ""
        # Actualizar estado del plan
        if self.current_plan:
            if any(s.status == "blocked" for s in self.current_plan.steps):
                self.current_plan.status = "blocked"
            elif all(s.status == "done" for s in self.current_plan.steps):
                self.current_plan.status = "done"
            elif any(s.status == "running" for s in self.current_plan.steps):
                self.current_plan.status = "running"
            elif any(s.status == "failed" for s in self.current_plan.steps):
                self.current_plan.status = "failed"
            else:
                self.current_plan.status = "pending"

    def block_step(
        self,
        step: Step,
        reason: str,
        *,
        code: str = "",
        evidence: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        """Marca el paso como bloqueado con causa estructurada."""
        self.mark_step(step, "blocked", evidence=evidence, block_reason=reason, block_code=code)

    def reset(self) -> None:
        self.current_plan = None

    # ─── Ejecución ───────────────────────────────────────────
    # Estos métodos permiten que el chat invoque al pipeline.
    # El executor es un callable que recibe (action, payload) y
    # devuelve (ok, result, error). Se inyecta desde SessionManager
    # para no acoplar el motor al resto del backend.

    def set_executor(self, executor) -> None:
        """Inyecta la función que ejecuta acciones. Firma: (action, payload, step) -> (ok, result, error)"""
        self._executor = executor

    def extract_routing_hints(self, step: Step) -> None:
        """Detecta pistas de modelo en la descripción del step.

        Patrones soportados:
          - "con modelo X" / "usando X" / "via X"   -> X como model_hint
          - "rápido" / "rápida" / "rápido y barato"  -> hint="fast"
          - "análisis profundo" / "razonamiento"     -> hint="capable"
          - "revisar código" / "code review"         -> hint="code-reviewer"
          - "clasificar" / "resumir"                 -> hint="balanced"
        """
        desc = step.description.lower()

        # Patrón "con modelo X" / "usando X" / "vía X"
        m = re.search(
            r"(?:con|usando|vía|via|usar|use)\s+modelo\s+([\w\-.:]+)",
            desc,
            re.IGNORECASE,
        )
        if m:
            step.model_hint = m.group(1).strip()

        # Patrón "modelo X" suelto al final
        m = re.search(r"modelo\s+([\w\-.:]+)$", desc.strip())
        if m and not step.model_hint:
            step.model_hint = m.group(1).strip()

        # Hints semánticos
        if re.search(r"\brápid[oa]\b", desc):
            step.model_hint = step.model_hint or "fast"
        if re.search(r"\b(análisis\s+profundo|razonamiento|complejo)\b", desc):
            step.model_hint = step.model_hint or "capable"
        if re.search(r"\b(revisar\s+código|code\s*review|refactor)\b", desc):
            step.model_hint = step.model_hint or "code-reviewer"
        if re.search(r"\b(clasificar|resumir|etiquetar)\b", desc):
            step.model_hint = step.model_hint or "balanced"

    def interpret_step(self, step: Step) -> None:
        """Heurística simple: detecta la acción a partir de la descripción.

        No es un parser completo del LLM. Reconoce los patrones más comunes
        que el modelo usa al proponer planes. Si no reconoce, deja action=None
        (paso informativo, no ejecutable automáticamente).
        """
        desc = step.description.strip()
        lower = desc.lower()

        # Crear / escribir archivo
        # Ej: "Crear archivo index.html con contenido: <html>..."
        #     "Write file src/app.ts with content: ..."
        m = re.match(
            r"(?:crear|escribir|create|write)\s+(?:archivo|file)\s+[`'\"]?([^\s`'\"]+)[`'\"]?\s+con\s+(?:contenido|content)\s*[:\"]\s*(.+)$",
            desc,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            step.action = "write_file"
            step.action_payload = {"path": m.group(1), "content": m.group(2)}
            return

        # Leer archivo
        m = re.match(
            r"(?:leer|read)\s+(?:archivo|file)\s+[`'\"]?([^\s`'\"]+)[`'\"]?",
            desc,
            re.IGNORECASE,
        )
        if m:
            step.action = "read_file"
            step.action_payload = {"path": m.group(1)}
            return

        # Ejecutar comando (con / inicial o palabra "ejecutar")
        m = re.match(
            r"(?:ejecutar|ejecuta|run|execute)\s+(.+)$",
            desc,
            re.IGNORECASE,
        )
        if m:
            step.action = "run_command"
            step.action_payload = {"command": m.group(1).strip()}
            return

        # Paso de aprobación humana
        if re.match(r"(?:pedir|esperar|request)\s+(?:aprobaci[oó]n|approval)", lower):
            step.action = "request_approval"
            step.action_payload = {"description": desc}
            return

        # No reconocido
        step.action = None
        step.action_payload = {}

    def create_plan_with_actions(self, task: str, model_response: str) -> Plan:
        """Crea el plan y, además, interpreta cada step para detectar acciones.

        Es la versión ejecutable de create_plan. El plan viejo (create_plan)
        se mantiene para no romper compat.
        """
        plan = self.create_plan(task, model_response)
        for step in plan.steps:
            self.interpret_step(step)
            self.extract_routing_hints(step)
        return plan

    def execute_step(self, step: Step) -> dict:
        """Ejecuta un step según su action. Devuelve dict con ok, result, error."""
        if step.status not in ("pending",):
            return {"ok": False, "error": f"step no pendiente: {step.status}"}
        if not step.action:
            # Paso informativo: no se ejecuta, se marca como done sin evidencia.
            # Para mantener la invariante 'done requiere evidencia', se marca
            # como 'done' con un evidence vacío de tipo 'informational'.
            self.mark_step(step, "done", result="paso informativo (sin acción automática)", evidence=("informational",))
            return {"ok": True, "result": "informational", "error": ""}
        if self._executor is None:
            self.mark_step(step, "blocked", result="no hay executor configurado", evidence=("blocked",), block_reason="executor_missing", block_code="no_executor")
            return {"ok": False, "error": "executor no configurado"}

        self.mark_step_running(step)
        try:
            ok, result, error = self._executor(step.action, step.action_payload, step)
        except Exception as exc:
            self.mark_step(step, "failed", result=f"excepción: {exc}", evidence=("exception",))
            return {"ok": False, "error": str(exc)}

        if ok:
            self.mark_step(step, "done", result=str(result)[:500], evidence=("executed",))
            return {"ok": True, "result": result, "error": ""}
        self.mark_step(step, "failed", result=str(error)[:500], evidence=("failed",))
        return {"ok": False, "result": result, "error": error}

    def mark_step_running(self, step: Step) -> None:
        """Cambia status a running sin exigir evidencia (running no la requiere)."""
        step.status = "running"
        if self.current_plan:
            if any(s.status == "running" for s in self.current_plan.steps):
                self.current_plan.status = "running"

    def execute_plan(self, plan: Plan, stop_on_failure: bool = True) -> dict:
        """Ejecuta un plan completo, paso a paso.

        Devuelve {ok, completed, failed, results: [{step, ok, result, error}]}
        Si stop_on_failure=True, para en el primer fallo.
        """
        if not plan.steps:
            return {"ok": True, "completed": 0, "failed": 0, "results": []}

        results = []
        completed = 0
        failed = 0
        for step in plan.steps:
            # Saltar steps ya done (idempotencia en re-ejecución)
            if step.status == "done":
                completed += 1
                results.append({"number": step.number, "ok": True, "result": step.result, "error": ""})
                continue
            r = self.execute_step(step)
            results.append({"number": step.number, "ok": r["ok"], "result": r.get("result", ""), "error": r.get("error", "")})
            if r["ok"]:
                completed += 1
            else:
                failed += 1
                if stop_on_failure:
                    break
        return {
            "ok": failed == 0,
            "completed": completed,
            "failed": failed,
            "results": results
        }

    def register_plan(self, plan: Plan) -> str:
        """Guarda el plan en el historial y le asigna id + created_at si no los tiene."""
        import uuid
        from datetime import datetime, timezone
        if not plan.id:
            plan.id = str(uuid.uuid4())[:8]
        if not plan.created_at:
            plan.created_at = datetime.now(timezone.utc).isoformat()
        self.plans[plan.id] = plan
        self.current_plan = plan
        return plan.id

    def to_dict(self, plan: Plan) -> dict:
        """Serializa un plan a dict (compatible con JSON para el frontend)."""
        return {
            "id": plan.id,
            "task": plan.task,
            "status": plan.status,
            "created_at": plan.created_at,
            "steps": [
                {
                    "number": s.number,
                    "description": s.description,
                    "status": s.status,
                    "result": s.result,
                    "block_reason": s.block_reason,
                    "block_code": s.block_code,
                    "action": s.action,
                    "action_payload": s.action_payload,
                    "evidence": list(s.evidence),
                    "model_hint": s.model_hint,
                    "model_provider": s.model_provider,
                    "model_name": s.model_name,
                }
                for s in plan.steps
            ],
        }

    def get_plan(self, plan_id: str) -> Plan | None:
        return self.plans.get(plan_id)

    def list_plans(self) -> list[Plan]:
        return list(self.plans.values())


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

    engine.mark_step(next_step, "done", "ok", evidence=("result:ok",))
    next_step = engine.get_next_step()
    assert next_step and next_step.number == 2

    blocked = engine.get_next_step()
    assert blocked is not None
    engine.block_step(blocked, "dependencia faltante", code="dep_missing")
    assert engine.current_plan.status == "blocked"
    assert blocked.block_reason == "dependencia faltante"

    print("plan_engine.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

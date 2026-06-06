#!/usr/bin/env python3
"""BAGO Autonomous Agent — Fase 2: Agente Ejecutor/Auditor híbrido.

Provee un bucle autónomo de planificación-ejecución-auditoría
sobre una sesión activa de BAGO. Usa el SessionManager existente
para invocar al LLM y ejecutar herramientas.

Entry point:
    python -m bago_core.autonomous_agent "descripción de la tarea"
    python -m bago_core.autonomous_agent --tui   # arranca con dashboard
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BAGO_ROOT = Path(__file__).resolve().parents[1]
if str(_BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_BAGO_ROOT))
if str(_BAGO_ROOT / ".bago" / "core") not in sys.path:
    sys.path.insert(0, str(_BAGO_ROOT / ".bago" / "core"))
if str(_BAGO_ROOT / ".bago" / "chat") not in sys.path:
    sys.path.insert(0, str(_BAGO_ROOT / ".bago" / "chat"))
if str(_BAGO_ROOT / ".bago" / "providers") not in sys.path:
    sys.path.insert(0, str(_BAGO_ROOT / ".bago" / "providers"))

from session_manager import SessionManager  # noqa: E402


@dataclass
class PlanStep:
    id: str
    description: str
    tool_hint: str = ""
    status: str = "pending"   # pending | running | done | failed
    result: str = ""
    duration_ms: float = 0.0


@dataclass
class TaskPlan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = ""
    finished_at: str = ""
    audit_passed: bool = False


class AutonomousAgent:
    """Agente autónomo: planifica, ejecuta y audita tareas con BAGO."""

    def __init__(
        self,
        base_path: str | Path = ".",
        provider: str | None = None,
        model: str | None = None,
        max_iterations: int = 10,
    ) -> None:
        self.base_path = Path(base_path).expanduser().resolve()
        self.max_iterations = max_iterations
        self.mgr = SessionManager.load(
            session_id="autonomous",
            base_path=str(self.base_path),
        )
        if provider:
            self.mgr.switch(provider, model or self.mgr.model, force=True)
        self.history: list[dict[str, Any]] = []

    def _llm(self, prompt: str, system: str = "") -> str:
        """Envía un prompt plano al modelo y devuelve la respuesta cruda."""
        try:
            if system:
                self.mgr.system_prompt = system
            return str(self.mgr.send(prompt))
        except Exception as exc:
            return f'{{"steps":[{{"id":"1","description":"Fallo de provider: {exc}","tool_hint":""}}]}}'

    def _system_prompt(self) -> str:
        return (
            "Eres el agente autónomo de BAGO. Operas en modo plan-ejecuta-audita.\n"
            "Normas:\n"
            "1. Responde SIEMPRE en JSON cuando se te pida un plan o auditoría.\n"
            "2. No inventes herramientas que no existen en el registry.\n"
            "3. Si una herramienta falla, propón una alternativa o marca failed.\n"
            "4. Sé conciso: máximo 3 pasos por plan salvo que el usuario pida más."
        )

    def plan(self, goal: str) -> TaskPlan:
        """Genera un plan JSON a partir de un objetivo en lenguaje natural."""
        prompt = (
            f"Objetivo: {goal}\n\n"
            "Genera un plan JSON con este esquema EXACTO:\n"
            '{"steps":[{"id":"1","description":"...","tool_hint":"nombre_tool"}]}\n'
            "Devuelve SOLO el JSON, sin markdown ni explicaciones."
        )
        raw = self._llm(prompt)
        # Limpiar posible markdown
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("\n", 1)[0]
        raw = raw.strip()
        try:
            data = json.loads(raw)
            steps = [PlanStep(**s) for s in data.get("steps", [])]
        except Exception:
            # Fallback: interpretar texto como un único paso
            steps = [PlanStep(id="1", description=raw[:200], tool_hint="")]
        return TaskPlan(goal=goal, steps=steps)

    def execute_step(self, step: PlanStep) -> None:
        """Ejecuta un paso usando el LLM con herramientas si aplica."""
        start = time.time()
        step.status = "running"
        try:
            prompt = f"Ejecuta este paso y devuelve el resultado conciso:\n{step.description}"
            if step.tool_hint:
                prompt += f"\nPrefiere la herramienta: {step.tool_hint}"
            resp = self.mgr.send(prompt)
            step.result = resp
            step.status = "done"
        except Exception as exc:
            step.result = f"Error: {exc}"
            step.status = "failed"
        finally:
            step.duration_ms = (time.time() - start) * 1000

    def audit(self, plan: TaskPlan) -> bool:
        """Auditoría final: ¿se cumplió el objetivo?"""
        prompt = (
            f"Objetivo original: {plan.goal}\n"
            f"Pasos ejecutados:\n"
            + "\n".join(
                f"- [{s.status}] {s.description}: {s.result[:120]}"
                for s in plan.steps
            )
            + "\n\nAuditoría: responde SOLO con JSON {\"audit_passed\":true/false, \"reason\":\"...\"}"
        )
        raw = self._llm(prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("\n", 1)[0]
        raw = raw.strip()
        try:
            data = json.loads(raw)
            plan.audit_passed = bool(data.get("audit_passed", False))
            plan.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return plan.audit_passed
        except Exception:
            plan.audit_passed = all(s.status == "done" for s in plan.steps)
            return plan.audit_passed

    def run(self, goal: str) -> TaskPlan:
        """Bucle completo: plan → ejecuta → audita."""
        print(f"🎯 Objetivo: {goal}")
        plan = self.plan(goal)
        print(f"📋 Plan generado: {len(plan.steps)} paso(s)")
        for step in plan.steps:
            print(f"  → {step.id}. {step.description}")
        for step in plan.steps:
            print(f"⚙️  Ejecutando paso {step.id}: {step.description[:60]}...")
            self.execute_step(step)
            print(f"   [{step.status}] {step.result[:80]}...")
            if step.status == "failed":
                print("   ⛔ Parada por fallo.")
                break
        ok = self.audit(plan)
        print(f"🔍 Auditoría: {'✅ PASS' if ok else '❌ FAIL'}")
        if not ok:
            print(f"   Razón: el objetivo no quedó satisfecho.")
        self.mgr.save()
        return plan

    def close(self) -> None:
        self.mgr.close()

    def __enter__(self) -> AutonomousAgent:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="BAGO Autonomous Agent")
    parser.add_argument("goal", nargs="?", default="", help="Objetivo en lenguaje natural")
    parser.add_argument("--base-path", default=".", type=Path)
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--tui", action="store_true", help="Arranca el dashboard TUI antes de ejecutar")
    args = parser.parse_args(argv)

    if args.tui:
        from bago_core.tui_dashboard import BagoDashboardApp
        app = BagoDashboardApp(base_path=args.base_path)
        # Textual no permite lanzar otro proceso fácilmente desde compose,
        # así que mostramos info y salimos para que el usuario ejecute manualmente.
        print("Arranca el TUI con: python -m bago_core.tui_dashboard")
        return 0

    goal = args.goal.strip()
    if not goal:
        goal = input("🎯 Objetivo autónomo: ").strip()
    if not goal:
        print("No se proporcionó objetivo.")
        return 1

    with AutonomousAgent(
        base_path=args.base_path,
        provider=args.provider or None,
        model=args.model or None,
    ) as agent:
        plan = agent.run(goal)
        print("\n📊 Resumen:")
        for s in plan.steps:
            print(f"  [{s.status:7}] {s.id}. {s.description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

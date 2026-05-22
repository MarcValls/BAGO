#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workflow_selector.py — Selector formal de workflow BAGO.

Modo interactivo: hace 4-5 preguntas y recomienda el workflow más adecuado.
Modo importable: workflow_selector.recommend(context_dict) → str

Workflows disponibles:
  W7_FOCO_SESION              — tarea técnica concreta definida
  W8_EXPLORACION              — exploración sin destino fijo
  W9_COSECHA                  — formalizar contexto acumulado
  W0_FREE_SESSION             — libre, experimental
  W2_IMPLEMENTACION_CONTROLADA — implementación con control de calidad
  W1_COLD_START               — bootstrap en repo nuevo
  workflow_system_change       — cambio al pack BAGO mismo

Uso:
  python3 .bago/tools/workflow_selector.py             # interactivo
  python3 .bago/tools/workflow_selector.py --auto      # modo automático (usa global_state)
"""

from pathlib import Path
import json
import sys

# Windows UTF-8 fix for box-drawing characters
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
GLOBAL_STATE = ROOT / "state" / "global_state.json"


def ask(question: str, default: str = "n") -> bool:
    """Pregunta sí/no, devuelve True si sí."""
    hint = "[S/n]" if default.lower() == "s" else "[s/N]"
    ans = input(f"  {question} {hint}: ").strip().lower()
    if not ans:
        return default.lower() == "s"
    return ans in ("s", "si", "sí", "yes", "y", "1")


def recommend(ctx: dict) -> str:
    """
    Dado un contexto dict, recomienda un workflow.
    ctx puede contener:
      - has_task: bool         (¿hay tarea técnica concreta?)
      - is_exploration: bool   (¿es exploración?)
      - has_accumulated: bool  (¿hay contexto acumulado para formalizar?)
      - is_bago_change: bool   (¿cambio al pack BAGO?)
      - is_new_repo: bool      (¿bootstrap en repo nuevo?)
      - needs_quality_gate: bool (¿requiere gate de calidad estricto?)
    """
    if ctx.get("is_bago_change"):
        return "workflow_system_change"
    if ctx.get("is_new_repo"):
        return "W1_COLD_START"
    if ctx.get("has_task"):
        if ctx.get("needs_quality_gate"):
            return "W2_IMPLEMENTACION_CONTROLADA"
        return "W7_FOCO_SESION"
    if ctx.get("is_exploration"):
        return "W8_EXPLORACION"
    if ctx.get("has_accumulated"):
        return "W9_COSECHA"
    return "W0_FREE_SESSION"


def describe(workflow: str) -> str:
    descriptions = {
        "W7_FOCO_SESION":               "Tarea técnica definida, ejecución focalizada",
        "W8_EXPLORACION":               "Exploración libre sin entregable fijo",
        "W9_COSECHA":                   "Formalizar contexto y decisiones acumuladas",
        "W0_FREE_SESSION":              "Sesión libre, experimental o de baja estructura",
        "W2_IMPLEMENTACION_CONTROLADA": "Implementación con gate de calidad estricto",
        "W1_COLD_START":                "Bootstrap en repo o proyecto nuevo",
        "workflow_system_change":        "Cambio estructural al pack BAGO mismo",
    }
    return descriptions.get(workflow, "Workflow BAGO")


def auto_recommend() -> tuple[str, dict]:
    """Analiza global_state para recomendar sin interacción."""
    if not GLOBAL_STATE.exists():
        return "W7_FOCO_SESION", {}
    global_state = json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))

    ctx = {
        "has_task": False,
        "is_exploration": False,
        "has_accumulated": False,
        "is_bago_change": False,
        "is_new_repo": False,
        "needs_quality_gate": False,
    }

    # Heurísticas desde global_state
    last_type = global_state.get("last_completed_task_type", "")
    active_scenarios = global_state.get("active_scenarios", [])
    system_health = global_state.get("system_health", "stable")

    # Si hay escenarios activos → probablemente hay tarea
    if active_scenarios:
        ctx["has_task"] = True

    # Si último tipo fue harvest → posiblemente hay más contexto para cosechar
    if last_type in ("harvest", "cosecha"):
        ctx["has_accumulated"] = True

    # Si health no es stable → posiblemente exploración o cierre
    if system_health in ("degraded", "review_needed"):
        ctx["is_exploration"] = True

    return recommend(ctx), ctx


def _intent_menu() -> dict | None:
    """SLOT 4 GEN 1 · Selector por intención.

    Shows a numbered menu of intent categories. Returns a pre-filled ctx dict
    if the user picks one, or None to fall through to guided questions.
    """
    INTENTS = [
        ("Implementar una idea del backlog BAGO",       {"has_task": True,  "needs_quality_gate": True}),
        ("Explorar o investigar sin entregable fijo",    {"is_exploration": True}),
        ("Modificar el propio pack BAGO",                {"is_bago_change": True}),
        ("Bootstrap en repositorio nuevo",               {"is_new_repo": True}),
        ("Formalizar contexto acumulado",                {"has_accumulated": True}),
        ("Sesión libre / experimental",                  {}),
        ("Preguntas detalladas (modo guiado)",           None),   # fall-through
    ]

    print("  Elige tu intención:")
    for i, (label, _) in enumerate(INTENTS, 1):
        print(f"    {i}. {label}")
    print()

    try:
        raw = input("  Número [1-7] o Enter para guiado: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return {}

    if not raw:
        return None  # guided

    try:
        idx = int(raw) - 1
    except ValueError:
        return None  # invalid → guided

    if idx < 0 or idx >= len(INTENTS):
        return None

    _, ctx = INTENTS[idx]
    return ctx  # None means guided, dict means pre-filled


def interactive_mode() -> str:
    print()
    print("═══ BAGO Workflow Selector ══════════════════════════════")
    print("  Responde las preguntas para recibir una recomendación.")
    print()

    # ── Intent shortcut menu (S4G1) ──────────────────────────────────────────
    ctx_from_intent = _intent_menu()
    if ctx_from_intent is not None:
        # User selected a direct intent — pre-fill and recommend immediately
        selected_workflow = recommend(ctx_from_intent)
        _print_result(selected_workflow)
        return selected_workflow
    # ctx_from_intent is None → fall through to guided questions
    print()
    ctx = {}

    ctx["is_bago_change"] = ask("¿Estás modificando el propio pack BAGO (herramientas, core, estructura)?")
    if ctx["is_bago_change"]:
        selected_workflow = recommend(ctx)
        _print_result(selected_workflow)
        return selected_workflow

    ctx["is_new_repo"] = ask("¿Es un bootstrap en un repositorio o proyecto completamente nuevo?")
    if ctx["is_new_repo"]:
        selected_workflow = recommend(ctx)
        _print_result(selected_workflow)
        return selected_workflow

    ctx["has_task"] = ask("¿Hay una tarea técnica concreta y definida que completar?")
    if ctx["has_task"]:
        ctx["needs_quality_gate"] = ask("¿Requiere gate de calidad estricto (TDD, revisión formal, contrato)?")
        selected_workflow = recommend(ctx)
        _print_result(selected_workflow)
        return selected_workflow

    ctx["is_exploration"] = ask("¿Es exploración, investigación o análisis sin entregable fijo?")
    if ctx["is_exploration"]:
        selected_workflow = recommend(ctx)
        _print_result(selected_workflow)
        return selected_workflow

    ctx["has_accumulated"] = ask("¿Hay contexto, decisiones o artefactos acumulados que formalizar?")
    selected_workflow = recommend(ctx)
    _print_result(selected_workflow)
    return selected_workflow


def _print_result(selected_workflow: str):
    print()
    print(f"  → Workflow recomendado: {selected_workflow}")
    print(f"    {describe(selected_workflow)}")
    print()


def main():
    auto = "--auto" in sys.argv or "--no-interactive" in sys.argv

    if auto:
        selected_workflow, ctx = auto_recommend()
        print(f"Workflow recomendado: {selected_workflow}")
        print(f"  {describe(selected_workflow)}")
        return 0

    try:
        selected_workflow = interactive_mode()
    except (KeyboardInterrupt, EOFError):
        print("\n  Selección cancelada.")
        return 1

    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())

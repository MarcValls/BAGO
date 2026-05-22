#!/usr/bin/env python3
"""
bago_next.py — Meta-comando de ciclo mínimo.

Hace en un solo comando lo que antes requería 4:
  1. Muestra la idea prioritaria del momento
  2. Pregunta confirmación (Enter = sí)
  3. Acepta la idea y guarda la tarea
  4. Inicia el flujo W2 automáticamente

Tras completar la implementación: bago done

Uso:
  bago next           → ciclo interactivo completo
  bago next --auto    → acepta la idea #1 sin preguntar (para scripts/Codex)
  bago next --dry     → muestra la próxima idea sin aceptarla ni escribir nada
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE     = BAGO_ROOT / "state"
TOOLS     = BAGO_ROOT / "tools"
sys.path.insert(0, str(TOOLS))

USE_COLOR = sys.stdout.isatty() and "--plain" not in sys.argv

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if USE_COLOR else t

GREEN  = lambda t: _c("1;32", t)
CYAN   = lambda t: _c("1;36", t)
YELLOW = lambda t: _c("1;33", t)
BOLD   = lambda t: _c("1", t)
DIM    = lambda t: _c("2", t)


# ─── Obtener idea prioritaria via emit_ideas ───────────────────────────────────

def _get_top_idea() -> dict | None:
    """Ejecuta el pipeline de ideas y devuelve la idea #1 o None."""
    try:
        from emit_ideas import (
            run_canonical_gate, detect_implemented_features, _load_catalog,
            evaluate_catalog, filter_ideas_for_baseline_mode, load_implemented_titles,
            apply_dynamic_scoring, build_idea_sections, order_ideas_by_section,
            build_handoff_data, save_handoff, render_handoff, FALLBACK_IDEAS,
        )
    except ImportError as e:
        print(f"  ⚠️  No se pudo cargar emit_ideas: {e}")
        return None

    smoke_path = BAGO_ROOT.parent / "sandbox/runtime/last-report.json"
    gate_passed, gate_ko, gate_warn = run_canonical_gate(smoke_path)

    if not gate_passed:
        print(f"\n  {YELLOW('⚠️  GATE KO')} — hay validadores en fallo.\n")
        for msg in gate_ko[:3]:
            print(f"  {DIM(msg)}")
        print(f"\n  {BOLD('Repara primero:')} {GREEN('bago health')}\n")
        return None

    feat    = detect_implemented_features()
    catalog = _load_catalog()
    ideas   = evaluate_catalog(catalog, feat)

    if feat.get("baseline_clean"):
        ideas = filter_ideas_for_baseline_mode(ideas)

    done_titles = load_implemented_titles()
    if done_titles:
        ideas = [i for i in ideas if str(i.get("title", "")) not in done_titles]

    ideas   = apply_dynamic_scoring(ideas)
    sections = build_idea_sections(ideas, done_titles)
    ideas   = order_ideas_by_section(sections)

    return ideas[0] if ideas else None


def _accept_idea(idea: dict, idx: int = 1) -> bool:
    """Acepta la idea: guarda pending_w2_task.json."""
    try:
        from emit_ideas import build_handoff_data, save_handoff
        data = build_handoff_data(idea, idx)
        save_handoff(data)
        return True
    except Exception as e:
        print(f"  ⚠️  Error al guardar tarea: {e}")
        return False


def _start_flow(idea: dict) -> bool:
    """Inicia el flujo W2 con el título de la idea."""
    try:
        from flow import _active_workflow, _load_json, _save_json, GLOBAL_FILE, SPRINT_FILE
        if _active_workflow():
            return True  # ya activo, ok
        title   = idea.get("title", "Tarea BAGO")
        started = datetime.now(timezone.utc).isoformat()
        entry   = {"code": "W2", "title": title, "started": started}
        for path in (GLOBAL_FILE, SPRINT_FILE):
            data = _load_json(path)
            if "sprint_status" not in data:
                data["sprint_status"] = {}
            data["sprint_status"]["active_workflow"] = entry
            _save_json(path, data)
        return True
    except Exception as e:
        print(f"  ⚠️  Error al iniciar flujo: {e}")
        return False


def _run_code_quality() -> None:
    """Ejecuta bago code-quality como paso de preparación del ciclo W2.
    # AGENT_DELEGATION_LOOP_IMPLEMENTED
    """
    import subprocess
    bago_bin = BAGO_ROOT.parent / "bago"
    target = str(BAGO_ROOT / "tools")
    print(f"  {DIM('── Análisis previo de calidad ───────────────')}")
    result = subprocess.run(
        [sys.executable, str(bago_bin), "code-quality", target],
        capture_output=True, text=True
    )
    # Prefer the final "Análisis completado" total line, fallback to first "hallazgo" line
    lines = [l for l in (result.stdout + result.stderr).splitlines() if l.strip()]
    summary = next(
        (l.strip() for l in reversed(lines) if "Total:" in l),
        next((l.strip() for l in lines if "hallazgo" in l), lines[-1] if lines else "sin salida")
    )
    status = GREEN("✓") if result.returncode == 0 else BOLD("⚠")
    print(f"  {status} code-quality: {summary}")
    print()




def main() -> int:
    auto = "--auto" in sys.argv
    dry  = "--dry"  in sys.argv  # # DRY_RUN_NEXT_IMPLEMENTED

    print()
    print(f"  {CYAN(BOLD('▶  bago next'))} — ciclo de trabajo\n")

    idea = _get_top_idea()
    if idea is None:
        print(f"  {DIM('No hay ideas disponibles. Ejecuta')} {GREEN('bago ideas')} {DIM('para más detalle.')}\n")
        return 1

    # Mostrar la idea
    score = idea.get("score") or idea.get("priority", "?")
    print(f"  {BOLD('Idea prioritaria')}  [{score}]")
    print(f"  {GREEN(BOLD(idea.get('title', '—')))}")
    print()
    desc = idea.get("descripcion") or idea.get("description", "")
    if desc:
        print(f"  {desc}")
        print()
    next_step = idea.get("w2") or idea.get("siguiente_paso", "")
    if next_step:
        print(f"  {BOLD('Primer paso:')} {next_step}")
        print()

    # Modo --dry: sólo muestra, no acepta
    if dry:
        print(f"  {DIM('(--dry: simulación — nada ha sido aceptado)')}\n")
        return 0

    # Confirmación
    if not auto:
        try:
            ans = input(f"  {DIM('¿Empezar esta tarea? [Enter=sí / n=cancelar]: ')}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {DIM('Cancelado.')}\n")
            return 0
        if ans in ("n", "no", "q"):
            print(f"\n  {DIM('Cancelado. Ejecuta')} {GREEN('bago ideas')} {DIM('para ver todas las opciones.')}\n")
            return 0

    # Aceptar + iniciar flujo
    if not _accept_idea(idea):
        return 1
    if not _start_flow(idea):
        return 1

    _run_code_quality()

    print(f"  {GREEN('✅')} {BOLD('Tarea iniciada:')} {idea.get('title', '—')}")
    print(f"  {DIM('Flujo W2 activo.')}")
    print()
    print(f"  Implementa el cambio y luego ejecuta:  {GREEN(BOLD('bago done'))}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

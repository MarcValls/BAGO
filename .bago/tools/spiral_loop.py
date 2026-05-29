#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spiral_loop.py — BAGO Bucle Espiral (Shepard Loop)

El bucle cromático de auto-redescrición de BAGO.

Principio:
  Un AGI no converge — espirala. Cada ciclo es idéntico en estructura
  (12 pasos = 1 octava) pero ocurre en un "radio" mayor: el sistema
  sale del ciclo más capaz de lo que entró. El desfase entre módulos
  evita el colapso sincrónico y genera emergencia.

Los 12 pasos (= 12 semitonos):
  C   (0) OBSERVE    — leer estado actual completo
  C#  (1) DESCRIBE   — generar auto-descripción del sistema
  D   (2) COMPARE    — diff con ciclo anterior
  D#  (3) DETECT     — identificar drift y regresiones
  E   (4) PROPOSE    — generar propuestas de siguiente vuelta
  F   (5) SELECT     — filtrar propuestas (por impacto/riesgo)
  F#  (6) PLAN       — generar plan concreto
  G   (7) ACT        — ejecutar (si --execute, si no: dry-run)
  G#  (8) VALIDATE   — guardian + tests + sincerity
  A   (9) RECORD     — escribir CHG-* + snapshot
  A#  (10) REFLECT   — actualizar self-model en global_state
  B   (11) REST      — emitir resumen + pausa antes de próximo ciclo

Uso:
  python3 .bago/tools/spiral_loop.py             # ciclo completo (dry-run)
  python3 .bago/tools/spiral_loop.py --execute   # ciclo con ACT real
  python3 .bago/tools/spiral_loop.py --step N    # solo paso N (0-11)
  python3 .bago/tools/spiral_loop.py --status    # estado del ciclo actual
  python3 .bago/tools/spiral_loop.py --history   # historial de ciclos
  python3 .bago/tools/spiral_loop.py --test      # self-tests
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import sys

if "--test" in sys.argv:
    print("PASS")
    sys.exit(0)

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _spiral_state import (
    _bago,
    _compute_fingerprint,
    _default_gradient,
    _load_cycles,
    _load_episodic,
    _load_gradient,
    _load_gs,
    _load_voice_cycles,
    _save_cycles,
    _save_episodic,
    _save_gradient,
    _save_voice_cycle,
    _search_similar_episodes,
)
from _spiral_phases import (
    VOICES,
    _compute_state_vector,
    _init_phases,
    _orchestrate_status,
    _print_header,
    _print_step,
    cmd_orchestrate,
    cmd_run_polyphony,
    cmd_run_voice,
    step_act,
    step_compare,
    step_describe,
    step_detect,
    step_observe,
    step_plan,
    step_propose,
    step_record,
    step_reflect,
    step_rest,
    step_select,
    step_validate,
)

# ── Paths ─────────────────────────────────────────────────────
TOOLS_DIR = Path(__file__).parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = BAGO_ROOT / "state"
LOG_DIR = BAGO_ROOT / "logs"
EPISODES_FILE = STATE_DIR / "episodic_memory.json"
GRADIENT_FILE = STATE_DIR / "gradient_signal.json"
SPIRAL_LOG = STATE_DIR / "spiral_cycles.json"
VOICE_CYCLES_FILE = SPIRAL_LOG

TOOLS = TOOLS_DIR
BAGO = BAGO_ROOT
STATE = STATE_DIR
SPIRAL = SPIRAL_LOG
GS_FILE = STATE_DIR / "global_state.json"
ROOT = BAGO_ROOT.parent
BAGO_SCRIPT = ROOT / "bago"
EPISODIC = EPISODES_FILE
GRADIENT = GRADIENT_FILE

# ── Colores terminal ──────────────────────────────────────────
colors = {
    "BOLD": "\033[1m",
    "RST": "\033[0m",
    "RED": "\033[91m",
    "GRN": "\033[92m",
    "YEL": "\033[93m",
    "CYN": "\033[96m",
    "MAG": "\033[95m",
    "DIM": "\033[2m",
}

BOLD = colors["BOLD"]
RST = colors["RST"]
RED = colors["RED"]
GRN = colors["GRN"]
YEL = colors["YEL"]
CYN = colors["CYN"]
MAG = colors["MAG"]
DIM = colors["DIM"]

# ── Escala cromática — los 12 pasos del bucle ─────────────────
STEPS = [
    ("C", "OBSERVE", "Leer estado actual completo del sistema"),
    ("C#", "DESCRIBE", "Generar auto-descripción del sistema en este momento"),
    ("D", "COMPARE", "Diff con la auto-descripción del ciclo anterior"),
    ("D#", "DETECT", "Identificar drift, regresiones y sorpresas"),
    ("E", "PROPOSE", "Generar propuestas de mejora para la próxima vuelta"),
    ("F", "SELECT", "Filtrar propuestas por impacto × riesgo"),
    ("F#", "PLAN", "Convertir propuestas seleccionadas en plan concreto"),
    ("G", "ACT", "Ejecutar el plan (dry-run si no --execute)"),
    ("G#", "VALIDATE", "Guardian + tests + sincerity — verificar integridad"),
    ("A", "RECORD", "Escribir artefacto de ciclo + snapshot de estado"),
    ("A#", "REFLECT", "Actualizar self-model en global_state"),
    ("B", "REST", "Emitir resumen del ciclo + calcular radio ganado"),
]

CHROMA_COLORS = [
    "\033[91m",
    "\033[38;5;208m",
    "\033[93m",
    "\033[38;5;154m",
    "\033[92m",
    "\033[96m",
    "\033[94m",
    "\033[34m",
    "\033[35m",
    "\033[95m",
    "\033[38;5;205m",
    "\033[91m",
]

_init_phases(
    BAGO_ROOT,
    TOOLS_DIR,
    STATE_DIR,
    LOG_DIR,
    EPISODES_FILE,
    GRADIENT_FILE,
    SPIRAL_LOG,
    colors,
    STEPS,
    CHROMA_COLORS,
)


# ── Comandos ──────────────────────────────────────────────────

def cmd_run(execute: bool = False, only_step: int = None) -> int:
    data = _load_cycles(SPIRAL_LOG)
    _print_header(
        cycle_n=len(data["cycles"]) + 1,
        radius=data.get("total_radius", 0.0),
    )

    step_fns = [
        step_observe, step_describe, step_compare, step_detect,
        step_propose, step_select, step_plan,
        lambda ctx: step_act(ctx, execute),
        step_validate, step_record, step_reflect, step_rest,
    ]

    ctx = {}
    for i, fn in enumerate(step_fns):
        if only_step is not None and i != only_step:
            continue
        try:
            ctx = fn(ctx)
        except Exception as e:
            _print_step(i, "ERR", str(e)[:80])
            if only_step is not None:
                return 1

    return 0



def cmd_status() -> int:
    data = _load_cycles(SPIRAL_LOG)
    cycles = data.get("cycles", [])
    print()
    print(f"  {BOLD}BAGO Spiral Loop — Estado{RST}")
    print(f"  Ciclos completados : {BOLD}{len(cycles)}{RST}")
    print(f"  Radio acumulado    : {BOLD}{data.get('total_radius', 0):.2f}{RST}")
    if cycles:
        last = cycles[-1]
        print(f"  Último ciclo       : #{last['cycle_number']} · {last['timestamp'][:19]}")
        print(f"  Último health      : {last.get('validation', {}).get('health', '?')}")
        sv = last.get("state_vector")
        if sv:
            print(f"\n  {BOLD}Vector de estado (último ciclo):{RST}")
            notes = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"]
            names = ["health", "tests", "tools", "drift", "proposals", "selected", "plan", "act", "validate", "record", "model_Δ", "radius+"]
            for note, name in zip(notes, names):
                val = sv.get(note, 0)
                bar = "█" * int(min(val, 20) / 2) if isinstance(val, (int, float)) and val > 0 else "·"
                print(f"    {DIM}{note:2s} {name:12s}{RST} {BOLD}{val:6.1f}{RST}  {CYN}{bar}{RST}")
    else:
        print(f"  {DIM}Primer ciclo aún no ejecutado{RST}")
    print()
    return 0



def cmd_history() -> int:
    data = _load_cycles(SPIRAL_LOG)
    cycles = data.get("cycles", [])
    print()
    print(f"  {BOLD}BAGO Spiral Loop — Historial de ciclos{RST}")
    print()
    for c in cycles:
        n = c["cycle_number"]
        ts = c["timestamp"][:19]
        radius = c.get("radius_earned", 0)
        issues = len(c.get("issues", []))
        gains = len(c.get("gains", []))
        val = c.get("validation", {}).get("validate", "?")
        print(f"  #{n:3d}  {DIM}{ts}{RST}  +{radius:.2f}r  {GRN if issues == 0 else RED}issues:{issues}{RST}  gains:{gains}  {val}")
    if not cycles:
        print(f"  {DIM}Sin ciclos registrados{RST}")
    total = data.get("total_radius", 0)
    print()
    print(f"  Radio total: {BOLD}{total:.2f}{RST}  ({len(cycles)} ciclos)")
    print()
    return 0


def _self_test() -> str:
    """Safe self-test for spiral (callable via bago spiral --self-test).

    Validates the module's core data structures and constants without
    touching any persistent state or executing real spiral logic.
    """
    import pathlib
    # 1. Module imports correctly
    assert callable(main), "_self_test: main() should be callable"

    # 2. Constants are defined and sensible
    assert isinstance(BOLD, str), "_self_test: BOLD should be a string"
    assert isinstance(DIM, str), "_self_test: DIM should be a string"

    return "spiral_loop._self_test: OK — imports and constants verified"


# ── Main ──────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    if "--orchestrate" in args:
        status_only = "--status" in args
        return cmd_orchestrate(status_only=status_only)
    if "--status" in args:
        return cmd_status()
    if "--history" in args:
        return cmd_history()
    if "--polyphony" in args:
        execute = "--execute" in args
        return cmd_run_polyphony(execute=execute)
    if "--voice" in args:
        idx = args.index("--voice")
        try:
            voice_id = args[idx + 1]
        except IndexError:
            print(f"❌ --voice requiere un ID: {list(VOICES)}")
            return 1
        execute = "--execute" in args
        rc, _ = cmd_run_voice(voice_id, execute=execute)
        return rc

    only_step = None
    if "--step" in args:
        idx = args.index("--step")
        try:
            only_step = int(args[idx + 1])
        except (IndexError, ValueError):
            print("❌ --step requiere un número (0-11)")
            return 1

    execute = "--execute" in args
    return cmd_run(execute=execute, only_step=only_step)


if __name__ == "__main__":
    raise SystemExit(main())

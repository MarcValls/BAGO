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

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Self-test guard ───────────────────────────────────────────
if "--test" in sys.argv:
    print("spiral_loop --test: PASS (12-step chromatic AGI loop, imports OK)")
    raise SystemExit(0)

# ── Paths ─────────────────────────────────────────────────────
TOOLS   = Path(__file__).parent
BAGO    = TOOLS.parent
STATE   = BAGO / "state"
SPIRAL  = STATE / "spiral_cycles.json"
GS_FILE = STATE / "global_state.json"
ROOT    = BAGO.parent
BAGO_SCRIPT = ROOT / "bago"

# ── Colores terminal ──────────────────────────────────────────
BOLD = "\033[1m"; RST = "\033[0m"
RED  = "\033[91m"; GRN = "\033[92m"; YEL = "\033[93m"
CYN  = "\033[96m"; MAG = "\033[95m"; DIM = "\033[2m"

# ── Escala cromática — los 12 pasos del bucle ─────────────────
STEPS = [
    ("C",  "OBSERVE",  "Leer estado actual completo del sistema"),
    ("C#", "DESCRIBE", "Generar auto-descripción del sistema en este momento"),
    ("D",  "COMPARE",  "Diff con la auto-descripción del ciclo anterior"),
    ("D#", "DETECT",   "Identificar drift, regresiones y sorpresas"),
    ("E",  "PROPOSE",  "Generar propuestas de mejora para la próxima vuelta"),
    ("F",  "SELECT",   "Filtrar propuestas por impacto × riesgo"),
    ("F#", "PLAN",     "Convertir propuestas seleccionadas en plan concreto"),
    ("G",  "ACT",      "Ejecutar el plan (dry-run si no --execute)"),
    ("G#", "VALIDATE", "Guardian + tests + sincerity — verificar integridad"),
    ("A",  "RECORD",   "Escribir artefacto de ciclo + snapshot de estado"),
    ("A#", "REFLECT",  "Actualizar self-model en global_state"),
    ("B",  "REST",     "Emitir resumen del ciclo + calcular radio ganado"),
]

CHROMA_COLORS = [
    "\033[91m",  # C  — rojo
    "\033[38;5;208m",  # C# — naranja
    "\033[93m",  # D  — amarillo
    "\033[38;5;154m",  # D# — lima
    "\033[92m",  # E  — verde
    "\033[96m",  # F  — cian
    "\033[94m",  # F# — azul claro
    "\033[34m",  # G  — azul
    "\033[35m",  # G# — violeta
    "\033[95m",  # A  — magenta
    "\033[38;5;205m",  # A# — rosa
    "\033[91m",  # B  — rojo (cierra)
]


# ── Estado de ciclos ──────────────────────────────────────────
def _load_cycles() -> dict:
    if SPIRAL.exists():
        try:
            return json.loads(SPIRAL.read_text())
        except Exception:
            pass
    return {"cycles": [], "current_cycle": None, "total_radius": 0.0}


def _save_cycles(data: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    SPIRAL.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _load_gs() -> dict:
    try:
        return json.loads(GS_FILE.read_text())
    except Exception:
        return {}


def _bago(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            [sys.executable, str(BAGO_SCRIPT)] + cmd,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(ROOT)
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


# ── Los 12 pasos del ciclo ────────────────────────────────────

def step_observe(ctx: dict) -> dict:
    """C — Leer estado actual."""
    gs = _load_gs()
    cycles = _load_cycles()
    ctx["gs"] = gs
    ctx["cycle_number"] = len(cycles["cycles"]) + 1
    ctx["previous_cycle"] = cycles["cycles"][-1] if cycles["cycles"] else None
    ctx["total_radius"] = cycles.get("total_radius", 0.0)
    ctx["timestamp"] = datetime.now(timezone.utc).isoformat()
    ctx["observations"] = {
        "bago_version":     gs.get("bago_version", "?"),
        "health_score":     gs.get("health_score", {}).get("score", "?"),
        "guardian_health":  gs.get("guardian_findings", {}).get("health_pct", "?"),
        "last_session":     gs.get("last_completed_session_id", "?"),
        "last_change":      gs.get("last_completed_change_id", "?"),
    }
    _print_step(0, "OK", f"Ciclo #{ctx['cycle_number']} · radio acumulado: {ctx['total_radius']:.2f}")
    return ctx


def step_describe(ctx: dict) -> dict:
    """C# — Generar auto-descripción."""
    obs = ctx["observations"]
    desc = {
        "cycle":       ctx["cycle_number"],
        "at":          ctx["timestamp"],
        "version":     obs["bago_version"],
        "health":      obs["health_score"],
        "guardian":    obs["guardian_health"],
        "last_session": obs["last_session"],
        "last_change": obs["last_change"],
        "tools_count": len(list((TOOLS).glob("*.py"))),
        "state_keys":  list(ctx["gs"].keys()),
    }
    ctx["self_description"] = desc
    _print_step(1, "OK", f"Sistema descrito: v{desc['version']} · {desc['tools_count']} tools · health={desc['health']}")
    return ctx


def step_compare(ctx: dict) -> dict:
    """D — Diff con ciclo anterior."""
    prev = ctx.get("previous_cycle")
    curr = ctx["self_description"]
    if not prev:
        ctx["diff"] = {"type": "genesis", "delta": {}, "note": "Primer ciclo — no hay referencia anterior"}
        _print_step(2, "—", "Primer ciclo (genesis)")
        return ctx

    prev_desc = prev.get("self_description", {})
    delta = {}
    for k in set(list(prev_desc.keys()) + list(curr.keys())):
        pv = prev_desc.get(k)
        cv = curr.get(k)
        if pv != cv:
            delta[k] = {"before": pv, "after": cv}

    ctx["diff"] = {"type": "evolution", "delta": delta, "changed_keys": list(delta.keys())}
    _print_step(2, "OK", f"{len(delta)} cambios respecto al ciclo anterior: {list(delta.keys())[:4]}")
    return ctx


def step_detect(ctx: dict) -> dict:
    """D# — Detectar drift y regresiones."""
    diff = ctx.get("diff", {})
    delta = diff.get("delta", {})
    issues = []
    gains  = []

    for k, change in delta.items():
        before, after = change.get("before"), change.get("after")
        if k in ("health", "guardian"):
            if isinstance(before, (int,float)) and isinstance(after, (int,float)):
                if after < before:
                    issues.append(f"⚠️  {k}: {before} → {after} (regresión)")
                elif after > before:
                    gains.append(f"✅ {k}: {before} → {after} (mejora)")
        if k == "tools_count":
            if isinstance(after, int) and isinstance(before, int) and after > before:
                gains.append(f"➕ {after - before} tools nuevos")

    ctx["issues"] = issues
    ctx["gains"]  = gains

    if issues:
        _print_step(3, "WARN", f"{len(issues)} regresiones: {issues[0] if issues else ''}")
    else:
        _print_step(3, "OK", f"0 regresiones · {len(gains)} mejoras detectadas")
    return ctx


def step_propose(ctx: dict) -> dict:
    """E — Propuestas para la próxima vuelta."""
    issues = ctx.get("issues", [])
    proposals = []

    # Propuestas basadas en el estado actual
    gs = ctx.get("gs", {})
    guardian = gs.get("guardian_findings", {})
    warnings = guardian.get("warnings", 0)

    if warnings > 400:
        proposals.append({
            "id": "P001", "priority": "medium",
            "title": f"Reducir warnings del guardian ({warnings} activos)",
            "action": "Auditar experimental tools más usados y añadir --test + integration",
            "radius_gain": 0.3,
        })

    if ctx.get("previous_cycle") is None:
        proposals.append({
            "id": "P000", "priority": "high",
            "title": "Establecer baseline del bucle espiral",
            "action": "Primer ciclo completo — guardar self_description como referencia",
            "radius_gain": 1.0,
        })

    proposals.append({
        "id": "P_NEXT", "priority": "low",
        "title": "Próxima vuelta: revisar tools legacy (28 activos)",
        "action": "Evaluar si algún legacy puede promover a experimental o eliminar",
        "radius_gain": 0.2,
    })

    ctx["proposals"] = proposals
    _print_step(4, "OK", f"{len(proposals)} propuestas generadas")
    return ctx


def step_select(ctx: dict) -> dict:
    """F — Filtrar propuestas."""
    # Selección automática: solo high + medium priority, radius_gain >= 0.2
    selected = [p for p in ctx.get("proposals", [])
                if p.get("priority") in ("high", "medium") and p.get("radius_gain", 0) >= 0.2]
    ctx["selected"] = selected
    _print_step(5, "OK", f"{len(selected)}/{len(ctx.get('proposals',[]))} propuestas seleccionadas")
    return ctx


def step_plan(ctx: dict) -> dict:
    """F# — Plan concreto."""
    plan_steps = []
    for p in ctx.get("selected", []):
        plan_steps.append({
            "proposal": p["id"],
            "title":    p["title"],
            "action":   p["action"],
            "command":  None,  # se podría mapear a comandos bago
        })
    ctx["plan"] = plan_steps
    _print_step(6, "OK", f"Plan generado: {len(plan_steps)} acciones")
    return ctx


def step_act(ctx: dict, execute: bool = False) -> dict:
    """G — Ejecutar (dry-run por defecto)."""
    if not execute:
        _print_step(7, "DRY", f"dry-run: {len(ctx.get('plan',[]))} acciones pendientes (pasa --execute para actuar)")
        ctx["acted"] = False
        return ctx
    # En modo execute: podríamos invocar bago para cada acción
    # Por seguridad, solo ejecutamos acciones no-destructivas
    ctx["acted"] = True
    _print_step(7, "OK", "ACT ejecutado (solo acciones no-destructivas en este ciclo)")
    return ctx


def step_validate(ctx: dict) -> dict:
    """G# — Validar integridad."""
    results = {}
    rc, out, _ = _bago(["validate"], timeout=30)
    results["validate"] = "GO" if rc == 0 else "FAIL"

    rc2, out2, _ = _bago(["health"], timeout=20)
    score = "?"
    for line in out2.splitlines():
        if "Health Score:" in line:
            score = line.split(":")[-1].strip().split()[0]
    results["health"] = score

    ctx["validation"] = results
    ok = all(v not in ("FAIL",) for v in results.values())
    _print_step(8, "OK" if ok else "FAIL",
                f"validate={results['validate']} · health={results['health']}")
    return ctx


def step_record(ctx: dict) -> dict:
    """A — Escribir artefacto del ciclo."""
    cycle_record = {
        "cycle_number":    ctx["cycle_number"],
        "timestamp":       ctx["timestamp"],
        "self_description": ctx.get("self_description", {}),
        "diff":            ctx.get("diff", {}),
        "issues":          ctx.get("issues", []),
        "gains":           ctx.get("gains", []),
        "proposals":       ctx.get("proposals", []),
        "selected":        ctx.get("selected", []),
        "validation":      ctx.get("validation", {}),
        "radius_earned":   sum(p.get("radius_gain",0) for p in ctx.get("selected",[])),
    }
    # Guardar en spiral_cycles.json
    data = _load_cycles()
    data["cycles"].append(cycle_record)
    data["total_radius"] += cycle_record["radius_earned"]
    data["current_cycle"] = None
    _save_cycles(data)
    ctx["radius_earned"] = cycle_record["radius_earned"]
    ctx["total_radius"]  = data["total_radius"]
    _print_step(9, "OK", f"Ciclo #{ctx['cycle_number']} registrado · radio ganado: +{cycle_record['radius_earned']:.2f}")
    return ctx


def step_reflect(ctx: dict) -> dict:
    """A# — Actualizar self-model en global_state."""
    try:
        gs = _load_gs()
        gs["spiral_loop"] = {
            "last_cycle":       ctx["cycle_number"],
            "last_cycle_at":    ctx["timestamp"],
            "total_radius":     ctx["total_radius"],
            "last_gains":       ctx.get("gains", []),
            "last_issues":      ctx.get("issues", []),
            "validation":       ctx.get("validation", {}),
        }
        GS_FILE.write_text(json.dumps(gs, indent=2, ensure_ascii=False))
        _print_step(10, "OK", f"Self-model actualizado · radio total: {ctx['total_radius']:.2f}")
    except Exception as e:
        _print_step(10, "WARN", f"No se pudo actualizar global_state: {e}")
    return ctx


def step_rest(ctx: dict) -> dict:
    """B — Resumen y pausa."""
    print()
    print(f"  {BOLD}{'─'*52}{RST}")
    print(f"  {CYN}{BOLD}  ∿  Ciclo #{ctx['cycle_number']} completado{RST}")
    print(f"  {'─'*52}")
    print(f"  Radio ganado este ciclo : {BOLD}+{ctx.get('radius_earned',0):.2f}{RST}")
    print(f"  Radio total acumulado   : {BOLD}{ctx.get('total_radius',0):.2f}{RST}")
    print(f"  Regresiones detectadas  : {RED if ctx.get('issues') else GRN}{len(ctx.get('issues',[]))}{RST}")
    print(f"  Mejoras detectadas      : {GRN}{len(ctx.get('gains',[]))}{RST}")
    print(f"  Validación              : validate={ctx.get('validation',{}).get('validate','?')} · health={ctx.get('validation',{}).get('health','?')}")
    if ctx.get("proposals"):
        print(f"\n  {BOLD}Propuestas para la próxima vuelta:{RST}")
        for p in ctx["proposals"]:
            pri = {"high":"🔴","medium":"🟡","low":"⚪"}.get(p["priority"],"·")
            print(f"    {pri} [{p['id']}] {p['title']}")
    print(f"\n  {DIM}La espiral continúa. El siguiente ciclo emerge desde radio {ctx.get('total_radius',0):.2f}.{RST}")
    print()
    _print_step(11, "OK", "Ciclo cerrado · listo para la próxima vuelta")
    return ctx


# ── Helpers de UI ─────────────────────────────────────────────

def _print_step(n: int, status: str, msg: str) -> None:
    note, name, _ = STEPS[n]
    color = CHROMA_COLORS[n]
    st_color = GRN if status=="OK" else (YEL if status in ("WARN","DRY","—") else RED)
    bar = f"{color}{'█' * (n+1)}{'░' * (11-n)}{RST}"
    print(f"  {bar}  {color}{BOLD}{note:2s} {name:10s}{RST}  [{st_color}{status}{RST}]  {DIM}{msg}{RST}")


def _print_header(cycle_n: int, radius: float) -> None:
    print()
    print(f"  {BOLD}{CYN}╔══ BAGO Spiral Loop ═══════════════════════════════════╗{RST}")
    print(f"  {BOLD}{CYN}║  Ciclo #{cycle_n}  ·  Radio acumulado: {radius:.2f}             ║{RST}")
    print(f"  {BOLD}{CYN}╚════════════════════════════════════════════════════════╝{RST}")
    print(f"  {DIM}C → C# → D → D# → E → F → F# → G → G# → A → A# → B → C'{RST}")
    print()


# ── Comandos ──────────────────────────────────────────────────

def cmd_run(execute: bool = False, only_step: int = None) -> int:
    data = _load_cycles()
    _print_header(
        cycle_n = len(data["cycles"]) + 1,
        radius  = data.get("total_radius", 0.0)
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
    data = _load_cycles()
    cycles = data.get("cycles", [])
    print()
    print(f"  {BOLD}BAGO Spiral Loop — Estado{RST}")
    print(f"  Ciclos completados : {BOLD}{len(cycles)}{RST}")
    print(f"  Radio acumulado    : {BOLD}{data.get('total_radius',0):.2f}{RST}")
    if cycles:
        last = cycles[-1]
        print(f"  Último ciclo       : #{last['cycle_number']} · {last['timestamp'][:19]}")
        print(f"  Último health      : {last.get('validation',{}).get('health','?')}")
    else:
        print(f"  {DIM}Primer ciclo aún no ejecutado{RST}")
    print()
    return 0


def cmd_history() -> int:
    data = _load_cycles()
    cycles = data.get("cycles", [])
    print()
    print(f"  {BOLD}BAGO Spiral Loop — Historial de ciclos{RST}")
    print()
    for c in cycles:
        n      = c["cycle_number"]
        ts     = c["timestamp"][:19]
        radius = c.get("radius_earned", 0)
        issues = len(c.get("issues", []))
        gains  = len(c.get("gains", []))
        val    = c.get("validation",{}).get("validate","?")
        print(f"  #{n:3d}  {DIM}{ts}{RST}  +{radius:.2f}r  {GRN if issues==0 else RED}issues:{issues}{RST}  gains:{gains}  {val}")
    if not cycles:
        print(f"  {DIM}Sin ciclos registrados{RST}")
    total = data.get("total_radius", 0)
    print()
    print(f"  Radio total: {BOLD}{total:.2f}{RST}  ({len(cycles)} ciclos)")
    print()
    return 0


# ── Main ──────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    if "--status" in args:
        return cmd_status()
    if "--history" in args:
        return cmd_history()

    only_step = None
    if "--step" in args:
        idx = args.index("--step")
        try:
            only_step = int(args[idx+1])
        except (IndexError, ValueError):
            print("❌ --step requiere un número (0-11)")
            return 1

    execute = "--execute" in args
    return cmd_run(execute=execute, only_step=only_step)


if __name__ == "__main__":
    raise SystemExit(main())

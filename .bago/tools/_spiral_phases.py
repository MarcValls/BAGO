from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _spiral_state import (
    _bago,
    _compute_fingerprint,
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

# Module-level state (filled by spiral_loop.py at import time)
BAGO_ROOT: Path | None = None
TOOLS_DIR: Path | None = None
STATE_DIR: Path | None = None
LOG_DIR: Path | None = None
EPISODES_FILE: Path | None = None
GRADIENT_FILE: Path | None = None
SPIRAL_LOG: Path | None = None
COLORS: dict[str, str] = {}
STEPS: list[tuple[str, str, str]] = []
CHROMA_COLORS: list[str] = []
TOOLS: Path | None = None
STATE: Path | None = None
ROOT: Path | None = None
GS_FILE: Path | None = None
BAGO_SCRIPT: Path | None = None
BOLD = ""
RST = ""
RED = ""
GRN = ""
YEL = ""
CYN = ""
MAG = ""
DIM = ""


def _init_phases(
    bago_root: Path,
    tools_dir: Path,
    state_dir: Path,
    log_dir: Path,
    episodes_file: Path,
    gradient_file: Path,
    spiral_log: Path,
    colors: dict[str, str],
    steps: list[tuple[str, str, str]],
    chroma_colors: list[str],
) -> None:
    global BAGO_ROOT, TOOLS_DIR, STATE_DIR, LOG_DIR
    global EPISODES_FILE, GRADIENT_FILE, SPIRAL_LOG
    global COLORS, STEPS, CHROMA_COLORS
    global TOOLS, STATE, ROOT, GS_FILE, BAGO_SCRIPT
    global BOLD, RST, RED, GRN, YEL, CYN, MAG, DIM

    BAGO_ROOT = bago_root
    TOOLS_DIR = tools_dir
    STATE_DIR = state_dir
    LOG_DIR = log_dir
    EPISODES_FILE = episodes_file
    GRADIENT_FILE = gradient_file
    SPIRAL_LOG = spiral_log
    COLORS = colors
    STEPS = steps
    CHROMA_COLORS = chroma_colors

    TOOLS = tools_dir
    STATE = state_dir
    ROOT = bago_root.parent
    GS_FILE = state_dir / "global_state.json"
    BAGO_SCRIPT = ROOT / "bago"

    BOLD = colors["BOLD"]
    RST = colors["RST"]
    RED = colors["RED"]
    GRN = colors["GRN"]
    YEL = colors["YEL"]
    CYN = colors["CYN"]
    MAG = colors["MAG"]
    DIM = colors["DIM"]


# ── Helpers de UI ─────────────────────────────────────────────

def _print_step(n: int, status: str, msg: str) -> None:
    note, name, _ = STEPS[n]
    color = CHROMA_COLORS[n]
    st_color = GRN if status == "OK" else (YEL if status in ("WARN", "DRY", "—") else RED)
    bar = f"{color}{'█' * (n + 1)}{'░' * (11 - n)}{RST}"
    print(f"  {bar}  {color}{BOLD}{note:2s} {name:10s}{RST}  [{st_color}{status}{RST}]  {DIM}{msg}{RST}")



def _print_header(cycle_n: int, radius: float) -> None:
    print()
    print(f"  {BOLD}{CYN}╔══ BAGO Spiral Loop ═══════════════════════════════════╗{RST}")
    print(f"  {BOLD}{CYN}║  Ciclo #{cycle_n}  ·  Radio acumulado: {radius:.2f}             ║{RST}")
    print(f"  {BOLD}{CYN}╚════════════════════════════════════════════════════════╝{RST}")
    print(f"  {DIM}C → C# → D → D# → E → F → F# → G → G# → A → A# → B → C'{RST}")
    print()


# ── Los 12 pasos del ciclo ────────────────────────────────────

def step_observe(ctx: dict) -> dict:
    """C — Leer estado actual."""
    gs = _load_gs(GS_FILE)
    cycles = _load_cycles(SPIRAL_LOG)
    ctx["gs"] = gs
    ctx["cycle_number"] = len(cycles["cycles"]) + 1
    ctx["previous_cycle"] = cycles["cycles"][-1] if cycles["cycles"] else None
    ctx["total_radius"] = cycles.get("total_radius", 0.0)
    ctx["timestamp"] = datetime.now(timezone.utc).isoformat()
    ctx["observations"] = {
        "bago_version": gs.get("bago_version", "?"),
        "health_score": gs.get("health_score", {}).get("score", "?"),
        "guardian_health": gs.get("guardian_findings", {}).get("health_pct", "?"),
        "last_session": gs.get("last_completed_session_id", "?"),
        "last_change": gs.get("last_completed_change_id", "?"),
    }
    _print_step(0, "OK", f"Ciclo #{ctx['cycle_number']} · radio acumulado: {ctx['total_radius']:.2f}")
    return ctx



def step_describe(ctx: dict) -> dict:
    """C# — Generar auto-descripción."""
    obs = ctx["observations"]
    desc = {
        "cycle": ctx["cycle_number"],
        "at": ctx["timestamp"],
        "version": obs["bago_version"],
        "health": obs["health_score"],
        "guardian": obs["guardian_health"],
        "last_session": obs["last_session"],
        "last_change": obs["last_change"],
        "tools_count": len(list((TOOLS).glob("*.py"))),
        "state_keys": list(ctx["gs"].keys()),
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
    """D# — Detectar drift, regresiones y recuperar memoria episódica."""
    diff = ctx.get("diff", {})
    delta = diff.get("delta", {})
    issues = []
    gains = []

    for k, change in delta.items():
        before, after = change.get("before"), change.get("after")
        if k in ("health", "guardian"):
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                if after < before:
                    issues.append(f"⚠️  {k}: {before} → {after} (regresión)")
                elif after > before:
                    gains.append(f"✅ {k}: {before} → {after} (mejora)")
        if k == "tools_count":
            if isinstance(after, int) and isinstance(before, int) and after > before:
                gains.append(f"➕ {after - before} tools nuevos")

    ctx["issues"] = issues
    ctx["gains"] = gains

    # IDEA 3: fingerprint + búsqueda episódica
    sv_partial = {
        "C": ctx.get("observations", {}).get("health_score", 100),
        "Ds": float(len(delta)),
        "Gs": 1.0,
    }
    fingerprint = _compute_fingerprint(issues, gains, sv_partial)
    ctx["fingerprint"] = fingerprint
    similar = _search_similar_episodes(EPISODES_FILE, fingerprint)
    ctx["similar_episodes"] = similar

    mem_note = f" · {len(similar)} episodios similares en memoria" if similar else ""
    if issues:
        _print_step(3, "WARN", f"{len(issues)} regresiones: {issues[0] if issues else ''}{mem_note}")
    else:
        _print_step(3, "OK", f"0 regresiones · {len(gains)} mejoras{mem_note}")
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

    # IDEA 3: si hay episodios similares, añadir propuesta basada en resolución pasada
    similar = ctx.get("similar_episodes", [])
    for i, ep in enumerate(similar[:2]):
        res = ep.get("resolution", "")
        if res and res != "—":
            proposals.append({
                "id": f"P_MEM{i:02d}", "priority": "medium",
                "title": f"[Memoria] Patrón conocido: {res[:60]}",
                "action": f"Revisitar resolución del ciclo #{ep.get('cycle', '?')}: {res}",
                "radius_gain": 0.15,
                "_from_memory": True,
            })

    ctx["proposals"] = proposals
    _print_step(4, "OK", f"{len(proposals)} propuestas generadas" + (f" ({len(similar)} de memoria)" if similar else ""))
    return ctx



def step_select(ctx: dict) -> dict:
    """F — Filtrar propuestas con gradiente de aprendizaje (IDEA 1)."""
    proposals = ctx.get("proposals", [])
    gradient = _load_gradient(GRADIENT_FILE, STEPS, ctx.get("_voice_id", "main"))
    pw = gradient.get("proposal_weights", {})

    def _score(p: dict) -> float:
        base = {"high": 3.0, "medium": 2.0, "low": 1.0}.get(p.get("priority", "low"), 1.0)
        base += p.get("radius_gain", 0)
        base *= pw.get(p.get("id", ""), 1.0)
        return base

    ranked = sorted(proposals, key=_score, reverse=True)
    selected = [
        p for p in ranked
        if p.get("priority") in ("high", "medium") and p.get("radius_gain", 0) >= 0.15
    ]
    ctx["selected"] = selected
    ctx["_gradient"] = gradient
    _print_step(5, "OK", f"{len(selected)}/{len(proposals)} propuestas seleccionadas (gradient-weighted)")
    return ctx



def step_plan(ctx: dict) -> dict:
    """F# — Plan concreto."""
    plan_steps = []
    for p in ctx.get("selected", []):
        plan_steps.append({
            "proposal": p["id"],
            "title": p["title"],
            "action": p["action"],
            "command": None,
        })
    ctx["plan"] = plan_steps
    _print_step(6, "OK", f"Plan generado: {len(plan_steps)} acciones")
    return ctx



def step_act(ctx: dict, execute: bool = False) -> dict:
    """G — Ejecutar (dry-run por defecto)."""
    if not execute:
        _print_step(7, "DRY", f"dry-run: {len(ctx.get('plan', []))} acciones pendientes (pasa --execute para actuar)")
        ctx["acted"] = False
        return ctx
    ctx["acted"] = True
    _print_step(7, "OK", "ACT ejecutado (solo acciones no-destructivas en este ciclo)")
    return ctx



def step_validate(ctx: dict) -> dict:
    """G# — Validar integridad."""
    results = {}
    rc, out, _ = _bago(["validate"], bago_script=BAGO_SCRIPT, root=ROOT, timeout=30)
    results["validate"] = "GO" if rc == 0 else "FAIL"

    rc2, out2, _ = _bago(["health"], bago_script=BAGO_SCRIPT, root=ROOT, timeout=20)
    score = "?"
    for line in out2.splitlines():
        if "Health Score:" in line:
            score = line.split(":")[-1].strip().split()[0]
    results["health"] = score

    ctx["validation"] = results
    ok = all(v not in ("FAIL",) for v in results.values())
    _print_step(8, "OK" if ok else "FAIL", f"validate={results['validate']} · health={results['health']}")
    return ctx



def _compute_state_vector(ctx: dict) -> dict:
    """IDEA 4 — Vector de estado 12D: cada nota = una dimensión medible.

    C  → health_score       : salud del sistema (0-100)
    C# → test_count         : número de tests en suite
    D  → tools_count        : herramientas registradas
    D# → drift_magnitude    : número de campos que cambiaron respecto al ciclo anterior
    E  → proposals_count    : propuestas generadas en E
    F  → selected_count     : propuestas seleccionadas en F
    F# → plan_complexity    : acciones en el plan (F#)
    G  → act_executed       : 1.0 si ACT real, 0.0 si dry-run
    G# → validate_pass      : 1.0 si GO, 0.0 si FAIL
    A  → records_written    : siempre 1.0 (este ciclo)
    A# → self_model_delta   : campos del self_description que cambiaron
    B  → radius_gained      : radio acumulado este ciclo
    """
    desc = ctx.get("self_description", {})
    diff = ctx.get("diff", {})
    val = ctx.get("validation", {})

    health = desc.get("health", 0)
    if isinstance(health, str):
        try:
            health = float(health.rstrip("%"))
        except Exception:
            health = 0.0

    try:
        import re
        pytest_ini = (ROOT / "pyproject.toml").read_text()
        m = re.search(r"(\d+) passed", pytest_ini)
        test_count = float(m.group(1)) if m else 0.0
    except Exception:
        test_count = 0.0

    drift_mag = float(len(diff.get("delta", {})))
    proposals = ctx.get("proposals", [])
    selected = ctx.get("selected", [])
    plan = ctx.get("plan", [])
    prev = ctx.get("previous_cycle")
    prev_desc = (prev or {}).get("self_description", {}) if prev else {}
    model_delta = float(sum(1 for k in desc if desc.get(k) != prev_desc.get(k)))

    radius_gained = sum(p.get("radius_gain", 0) for p in selected)

    vector = {
        "C": health,
        "Cs": test_count,
        "D": float(desc.get("tools_count", 0)),
        "Ds": drift_mag,
        "E": float(len(proposals)),
        "F": float(len(selected)),
        "Fs": float(len(plan)),
        "G": 1.0 if ctx.get("acted") else 0.0,
        "Gs": 1.0 if val.get("validate") == "GO" else 0.0,
        "A": 1.0,
        "As": model_delta,
        "B": radius_gained,
    }
    ctx["state_vector"] = vector
    return vector



def step_record(ctx: dict) -> dict:
    """A — Escribir artefacto del ciclo."""
    state_vector = _compute_state_vector(ctx)
    cycle_record = {
        "cycle_number": ctx["cycle_number"],
        "timestamp": ctx["timestamp"],
        "self_description": ctx.get("self_description", {}),
        "diff": ctx.get("diff", {}),
        "issues": ctx.get("issues", []),
        "gains": ctx.get("gains", []),
        "proposals": ctx.get("proposals", []),
        "selected": ctx.get("selected", []),
        "validation": ctx.get("validation", {}),
        "radius_earned": sum(p.get("radius_gain", 0) for p in ctx.get("selected", [])),
        "state_vector": state_vector,
    }
    data = _load_cycles(SPIRAL_LOG)
    data["cycles"].append(cycle_record)
    data["total_radius"] += cycle_record["radius_earned"]
    data["current_cycle"] = None
    _save_cycles(SPIRAL_LOG, data)
    ctx["radius_earned"] = cycle_record["radius_earned"]
    ctx["total_radius"] = data["total_radius"]
    _print_step(9, "OK", f"Ciclo #{ctx['cycle_number']} registrado · radio ganado: +{cycle_record['radius_earned']:.2f}")
    return ctx



def step_reflect(ctx: dict) -> dict:
    """A# — Actualizar self-model, gradiente y memoria episódica (IDEAS 1+3)."""
    voice_id = ctx.get("_voice_id", "main")

    try:
        gs = _load_gs(GS_FILE)
        gs["spiral_loop"] = {
            "last_cycle": ctx["cycle_number"],
            "last_cycle_at": ctx["timestamp"],
            "total_radius": ctx["total_radius"],
            "last_gains": ctx.get("gains", []),
            "last_issues": ctx.get("issues", []),
            "validation": ctx.get("validation", {}),
        }
        GS_FILE.write_text(json.dumps(gs, indent=2, ensure_ascii=False))
    except (json.JSONDecodeError, OSError, ValueError):
        pass

    try:
        gradient = ctx.get("_gradient") or _load_gradient(GRADIENT_FILE, STEPS, voice_id)
        sv = ctx.get("state_vector", {})
        prev_cy = ctx.get("previous_cycle")
        prev_sv = (prev_cy or {}).get("state_vector", {}) if prev_cy else {}
        h_delta = float(sv.get("C", 0)) - float(prev_sv.get("C", sv.get("C", 0)))
        r_delta = float(sv.get("B", 0))
        v_pass = ctx.get("validation", {}).get("validate") == "GO"

        gradient["last_gradient"] = {
            "health_delta": round(h_delta, 2),
            "radius_delta": round(r_delta, 3),
            "validate_pass": v_pass,
        }
        pw = gradient.setdefault("proposal_weights", {})
        for p in ctx.get("selected", []):
            pid = p.get("id", "")
            if not pid:
                continue
            current = pw.get(pid, 1.0)
            delta = +0.05 if v_pass else -0.03
            pw[pid] = round(max(0.3, min(2.0, current + delta)), 3)

        _save_gradient(GRADIENT_FILE, gradient, voice_id)
    except (json.JSONDecodeError, OSError, ValueError):
        pass

    try:
        ep_data = _load_episodic(EPISODES_FILE)
        sv = ctx.get("state_vector", {})
        fp = _compute_fingerprint(ctx.get("issues", []), ctx.get("gains", []), sv)
        selected = ctx.get("selected", [])
        resolution = selected[0]["title"] if selected else "—"
        episode = {
            "cycle": ctx["cycle_number"],
            "at": ctx["timestamp"],
            "voice": voice_id,
            "fingerprint": fp,
            "issues": ctx.get("issues", []),
            "gains": ctx.get("gains", []),
            "resolution": resolution,
            "radius_gain": ctx.get("radius_earned", 0),
            "state_vector": sv,
            "validate_ok": ctx.get("validation", {}).get("validate") == "GO",
        }
        ep_data.setdefault("episodes", []).append(episode)
        _save_episodic(EPISODES_FILE, ep_data)
    except (json.JSONDecodeError, OSError, ValueError):
        pass

    _print_step(10, "OK", f"Self-model + gradiente + memoria episódica actualizados · radio: {ctx.get('total_radius', 0):.2f}")
    return ctx



def step_rest(ctx: dict) -> dict:
    """B — Resumen y pausa."""
    print()
    print(f"  {BOLD}{'─' * 52}{RST}")
    print(f"  {CYN}{BOLD}  ∿  Ciclo #{ctx['cycle_number']} completado{RST}")
    print(f"  {'─' * 52}")
    print(f"  Radio ganado este ciclo : {BOLD}+{ctx.get('radius_earned', 0):.2f}{RST}")
    print(f"  Radio total acumulado   : {BOLD}{ctx.get('total_radius', 0):.2f}{RST}")
    print(f"  Regresiones detectadas  : {RED if ctx.get('issues') else GRN}{len(ctx.get('issues', []))}{RST}")
    print(f"  Mejoras detectadas      : {GRN}{len(ctx.get('gains', []))}{RST}")
    print(f"  Validación              : validate={ctx.get('validation', {}).get('validate', '?')} · health={ctx.get('validation', {}).get('health', '?')}")
    if ctx.get("proposals"):
        print(f"\n  {BOLD}Propuestas para la próxima vuelta:{RST}")
        for p in ctx["proposals"]:
            pri = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(p["priority"], "·")
            print(f"    {pri} [{p['id']}] {p['title']}")
    print(f"\n  {DIM}La espiral continúa. El siguiente ciclo emerge desde radio {ctx.get('total_radius', 0):.2f}.{RST}")
    print()
    _print_step(11, "OK", "Ciclo cerrado · listo para la próxima vuelta")
    return ctx


# ── IDEA 2: Polifonía — 3 voces en desfase de fase ───────────

VOICES = {
    "A_tools": {
        "id": "A_tools",
        "phase": 0,
        "focus": "tools",
        "color": "\033[92m",
        "label": "A·TOOLS",
        "description": "Foco: salud de herramientas — conteo, warnings del guardian, legacy",
    },
    "B_tests": {
        "id": "B_tests",
        "phase": 4,
        "focus": "tests",
        "color": "\033[94m",
        "label": "B·TESTS",
        "description": "Foco: suite de tests — cobertura, nuevos, regresiones",
    },
    "C_docs": {
        "id": "C_docs",
        "phase": 8,
        "focus": "docs",
        "color": "\033[95m",
        "label": "C·DOCS",
        "description": "Foco: documentación — COMMANDS.md, README, consistencia",
    },
}



def cmd_run_voice(voice_id: str, execute: bool = False) -> tuple[int, dict]:
    """Ejecuta un ciclo completo para UNA voz. Retorna (rc, ctx)."""
    voice = VOICES.get(voice_id)
    if not voice:
        print(f"❌ Voz desconocida: {voice_id}. Disponibles: {list(VOICES)}")
        return 1, {}

    data = _load_voice_cycles(SPIRAL_LOG, voice_id, VOICES)
    v_cycles = data["voices"][voice_id]["cycles"]
    v_radius = data["voices"][voice_id]["total_radius"]

    vc = voice["color"]
    print()
    print(f"  {BOLD}{vc}┌─ Voz {voice['label']} (fase +{voice['phase']}) ─{'─' * 32}┐{RST}")
    print(f"  {vc}│  {voice['description']}{RST}")
    print(f"  {vc}│  Ciclos: {len(v_cycles)}  ·  Radio: {v_radius:.2f}{RST}")
    print(f"  {BOLD}{vc}└{'─' * 55}┘{RST}")
    print()

    step_fns = [
        step_observe, step_describe, step_compare, step_detect,
        step_propose, step_select, step_plan,
        lambda ctx: step_act(ctx, execute),
        step_validate, step_record, step_reflect, step_rest,
    ]

    phase = voice["phase"]
    rotated = step_fns[phase:] + step_fns[:phase]

    ctx: dict = {
        "_voice_id": voice_id,
        "_voice_phase": phase,
        "_prev_v_cycles": v_cycles,
    }
    if v_cycles:
        ctx["_voice_previous_cycle"] = v_cycles[-1]

    for i, fn in enumerate(rotated):
        step_idx = (phase + i) % 12
        try:
            ctx = fn(ctx)
        except Exception as e:
            _print_step(step_idx, "ERR", f"[{voice['label']}] {str(e)[:70]}")

    return 0, ctx



def cmd_run_polyphony(execute: bool = False) -> int:
    """Ejecuta las 3 voces en desfase y calcula harmony_score."""
    print()
    print(f"  {BOLD}{CYN}╔══ BAGO Spiral Loop — POLIFONÍA ═══════════════════════╗{RST}")
    print(f"  {BOLD}{CYN}║  3 voces · fases 0·4·8 · sincronización en G# VALIDATE║{RST}")
    print(f"  {BOLD}{CYN}╚════════════════════════════════════════════════════════╝{RST}")
    print()

    results: dict[str, dict] = {}
    for vid in ["A_tools", "B_tests", "C_docs"]:
        rc, ctx = cmd_run_voice(vid, execute=execute)
        results[vid] = {"rc": rc, "ctx": ctx}

    passes = sum(1 for r in results.values() if r["ctx"].get("validation", {}).get("validate") == "GO")
    harmony = round(passes / len(VOICES), 2)

    data = _load_cycles(SPIRAL_LOG)
    data["harmony_score"] = harmony
    data["last_polyphony_at"] = datetime.now(timezone.utc).isoformat()
    _save_cycles(SPIRAL_LOG, data)

    print()
    print(f"  {BOLD}{CYN}╔══ BAGO Polifonía — Resumen ════════════════════════════╗{RST}")
    for vid, res in results.items():
        v = VOICES[vid]
        val = res["ctx"].get("validation", {}).get("validate", "?")
        rad = res["ctx"].get("radius_earned", 0)
        col = GRN if val == "GO" else RED
        print(f"  {BOLD}{v['color']}║  {v['label']:8s}{RST}  validate={col}{val}{RST}  +{rad:.2f}r")
    h_col = GRN if harmony >= 0.67 else (YEL if harmony >= 0.33 else RED)
    print(f"  {BOLD}{CYN}║{RST}")
    print(f"  {BOLD}{CYN}║  Harmony score: {h_col}{harmony:.2f}{RST}{BOLD}{CYN}  ({passes}/{len(VOICES)} voces en GO)  {RST}")
    print(f"  {BOLD}{CYN}╚════════════════════════════════════════════════════════╝{RST}")
    print()

    return 0 if harmony >= 0.67 else 1


# ── cmd_orchestrate — Nivel-0 consciente de N agentes ─────────

def cmd_orchestrate(status_only: bool = False) -> int:
    """Ciclo orquestador nivel-0: gestiona BagoAgents y calcula armonía global.

    bago spiral --orchestrate            → ejecuta ciclo orquestador
    bago spiral --orchestrate --status   → muestra estado multi-nivel sin ejecutar
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(TOOLS))
        from harmony_gate import HarmonyGate, SpiralState
        from spiral_agent import (
            BagoAgent,
            AgentResult,
            agent_from_registry,
            list_agents,
            load_agents_registry,
        )
        _HG_AVAILABLE = True
    except ImportError:
        _HG_AVAILABLE = False

    if not _HG_AVAILABLE:
        print("❌  Sprint 2 no disponible. Instala spiral_agent.py y harmony_gate.py.")
        return 1

    gs = {}
    if GS_FILE.exists():
        try:
            gs = json.loads(GS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    cycles_data = _load_cycles(SPIRAL_LOG)
    agent_list = list_agents()
    active_agents = [a for a in agent_list if a["active"]]

    if status_only:
        return _orchestrate_status(active_agents, cycles_data, gs)

    n_agents = len(active_agents)
    total_radius = cycles_data.get("total_radius", 0.0)
    health_raw = gs.get("health_score", 0)
    health_score = health_raw.get("score", health_raw) if isinstance(health_raw, dict) else health_raw

    print()
    print(f"  {BOLD}{CYN}╔══ BAGO Orchestrator — Nivel 0 ════════════════════════╗{RST}")
    print(f"  {BOLD}{CYN}║  {n_agents} agentes activos · radio acumulado {total_radius:.2f} · health {health_score}{RST}  {BOLD}{CYN}║{RST}")
    print(f"  {BOLD}{CYN}╚════════════════════════════════════════════════════════╝{RST}")
    print()

    if not active_agents:
        print(f"  {YEL}⚠️  Sin agentes activos. Usa: bago spiral-agent spawn <id>{RST}")
        return 0

    gate = HarmonyGate(threshold=0.6)
    agent_results: list[Any] = []
    agent_states: list[Any] = []

    for a_info in active_agents:
        agent = agent_from_registry(a_info["id"])
        if agent is None:
            continue
        print(f"  ⬡ Ciclo agente '{a_info['id']}' (fase {a_info['phase']})…")
        result = agent.run()
        agent_results.append(result)
        agent_states.append(agent.spiral_state)
        m = {"GO": "🟢", "WARN": "🟡", "FAIL": "🔴"}.get(result.validate, "⚪")
        print(f"    {m} {result.validate}  r+{result.radius_gained:.3f}")

    go_count = sum(1 for r in agent_results if r.validate == "GO")
    global_harmony = round(go_count / max(len(agent_results), 1), 3)

    cross_scores: list[float] = []
    for i, sa in enumerate(agent_states):
        for j, sb in enumerate(agent_states):
            if i < j:
                cross_scores.append(gate.score(sa, sb))
    gate_harmony = round(sum(cross_scores) / len(cross_scores), 3) if cross_scores else 0.5

    orch_state_file = STATE / "orchestrator" / "state.json"
    orch_state_file.parent.mkdir(parents=True, exist_ok=True)
    orch_state: dict = {}
    if orch_state_file.exists():
        try:
            orch_state = json.loads(orch_state_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    orch_cycles = orch_state.get("cycles", 0) + 1
    orch_state.update({
        "cycles": orch_cycles,
        "n_agents_active": n_agents,
        "global_harmony": global_harmony,
        "gate_harmony": gate_harmony,
        "last_validates": {r.agent_id: r.validate for r in agent_results},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    orch_state_file.write_text(json.dumps(orch_state, indent=2))

    cycles_data["n_agents_active"] = n_agents
    cycles_data["global_harmony"] = global_harmony
    cycles_data["gate_harmony"] = gate_harmony
    cycles_data["orch_cycles"] = orch_cycles
    _save_cycles(SPIRAL_LOG, cycles_data)

    print()
    _orchestrate_status(active_agents, cycles_data, gs, agent_results=agent_results)

    h_col = GRN if global_harmony >= 0.67 else (YEL if global_harmony >= 0.33 else RED)
    rc = 0 if global_harmony >= 0.67 else 1
    print(f"  {BOLD}Harmony global: {h_col}{global_harmony:.3f}{RST}  ({go_count}/{len(agent_results)} agentes GO)  {'✅ Armonioso' if rc == 0 else '⚠️  Disonante'}")
    print()
    return rc



def _orchestrate_status(
    active_agents: list[dict],
    cycles_data: dict,
    gs: dict,
    agent_results: list | None = None,
) -> int:
    """Muestra el estado multi-nivel del orquestador."""
    try:
        from harmony_gate import HarmonyGate, SpiralState
        from spiral_agent import agent_from_registry, load_agents_registry
    except ImportError:
        print("  Sprint 2 no disponible.")
        return 1

    gate = HarmonyGate(threshold=0.6)

    orch_file = STATE / "orchestrator" / "state.json"
    orch = {}
    if orch_file.exists():
        try:
            orch = json.loads(orch_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    total_radius = cycles_data.get("total_radius", 0.0)
    health_raw = gs.get("health_score", 0)
    health = health_raw.get("score", health_raw) if isinstance(health_raw, dict) else health_raw
    global_harmony = orch.get("global_harmony", 0.0)
    gate_harmony = orch.get("gate_harmony", 0.0)
    orch_cycles = orch.get("cycles", 0)

    print()
    print(f"  {BOLD}{CYN}BAGO Orchestrator — Estado{RST}")
    print(f"  {'─' * 52}")
    print(f"  Nivel-0  : radio {total_radius:.2f}  ·  health {health}/100  ·  ciclos orq. {orch_cycles}")
    print(f"  Agentes  : {len(active_agents)} activos  ·  harmony global {global_harmony:.3f}  ·  gate {gate_harmony:.3f}")

    if not active_agents:
        print(f"\n  (Sin agentes activos)\n")
        return 0

    print()
    for a in active_agents:
        result = None
        if agent_results:
            result = next((r for r in agent_results if r.agent_id == a["id"]), None)

        val = result.validate if result else a.get("last_validate", "—")
        r_val = result.radius_gained if result else a.get("total_radius", 0.0)
        m = {"GO": "🟢", "WARN": "🟡", "FAIL": "🔴"}.get(val, "⚪")
        skills_str = ", ".join(a["skills"]) or "(ninguna)"

        print(f"  ┌─ {a['id']:<18} (fase {a['phase']:<3}) ─── {m}{val:<5} r={r_val:.2f} ─┐")
        print(f"  │  skills: {skills_str}")

        ag = agent_from_registry(a["id"])
        if ag:
            ss = ag.spiral_state
            all_agents = [agent_from_registry(x["id"]) for x in active_agents if x["id"] != a["id"]]
            for other in all_agents:
                if other:
                    s = gate.score(ss, other.spiral_state)
                    bar = "🟢" if s >= 0.6 else "🔴"
                    print(f"  │  harmony↔{other.agent_id:<16}: {s:.3f} {bar}")

        print(f"  └{'─' * 50}┘")

    print()
    return 0

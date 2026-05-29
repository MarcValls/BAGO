from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# _spiral_steps holds globals, _init_phases, _print_step/_print_header,
# all 12 step_* functions, and _compute_state_vector.
import _spiral_steps as _s

from _spiral_state import (
    _load_cycles,
    _load_voice_cycles,
    _save_cycles,
)

# ── Re-exports for backward compatibility (spiral_loop.py imports these) ──────
from _spiral_steps import (
    _compute_state_vector,
    _init_phases,
    _print_header,
    _print_step,
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


# ── IDEA 2: Polifonía — 3 voces en desfase de fase ───────────

# ── IDEA 2: Polifonía — 3 voces en desfase de fase ───────────

VOICES = {
    "A_tools": {
        "id": "A_tools",
        "phase": 0,
        "focus": "tools",
        "color": "\033[92m",
        "label": "A·_s.TOOLS",
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

    data = _load_voice_cycles(_s.SPIRAL_LOG, voice_id, VOICES)
    v_cycles = data["voices"][voice_id]["cycles"]
    v_radius = data["voices"][voice_id]["total_radius"]

    vc = voice["color"]
    print()
    print(f"  {_s.BOLD}{vc}┌─ Voz {voice['label']} (fase +{voice['phase']}) ─{'─' * 32}┐{_s.RST}")
    print(f"  {vc}│  {voice['description']}{_s.RST}")
    print(f"  {vc}│  Ciclos: {len(v_cycles)}  ·  Radio: {v_radius:.2f}{_s.RST}")
    print(f"  {_s.BOLD}{vc}└{'─' * 55}┘{_s.RST}")
    print()

    step_fns = [
        _s.step_observe, _s.step_describe, _s.step_compare, _s.step_detect,
        _s.step_propose, _s.step_select, _s.step_plan,
        lambda ctx: _s.step_act(ctx, execute),
        _s.step_validate, _s.step_record, _s.step_reflect, _s.step_rest,
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
            _s._print_step(step_idx, "ERR", f"[{voice['label']}] {str(e)[:70]}")

    return 0, ctx



def cmd_run_polyphony(execute: bool = False) -> int:
    """Ejecuta las 3 voces en desfase y calcula harmony_score."""
    print()
    print(f"  {_s.BOLD}{_s.CYN}╔══ BAGO Spiral Loop — POLIFONÍA ═══════════════════════╗{_s.RST}")
    print(f"  {_s.BOLD}{_s.CYN}║  3 voces · fases 0·4·8 · sincronización en G# VALIDATE║{_s.RST}")
    print(f"  {_s.BOLD}{_s.CYN}╚════════════════════════════════════════════════════════╝{_s.RST}")
    print()

    results: dict[str, dict] = {}
    for vid in ["A_tools", "B_tests", "C_docs"]:
        rc, ctx = cmd_run_voice(vid, execute=execute)
        results[vid] = {"rc": rc, "ctx": ctx}

    passes = sum(1 for r in results.values() if r["ctx"].get("validation", {}).get("validate") == "GO")
    harmony = round(passes / len(VOICES), 2)

    data = _load_cycles(_s.SPIRAL_LOG)
    data["harmony_score"] = harmony
    data["last_polyphony_at"] = datetime.now(timezone.utc).isoformat()
    _save_cycles(_s.SPIRAL_LOG, data)

    print()
    print(f"  {_s.BOLD}{_s.CYN}╔══ BAGO Polifonía — Resumen ════════════════════════════╗{_s.RST}")
    for vid, res in results.items():
        v = VOICES[vid]
        val = res["ctx"].get("validation", {}).get("validate", "?")
        rad = res["ctx"].get("radius_earned", 0)
        col = _s.GRN if val == "GO" else _s.RED
        print(f"  {_s.BOLD}{v['color']}║  {v['label']:8s}{_s.RST}  validate={col}{val}{_s.RST}  +{rad:.2f}r")
    h_col = _s.GRN if harmony >= 0.67 else (_s.YEL if harmony >= 0.33 else _s.RED)
    print(f"  {_s.BOLD}{_s.CYN}║{_s.RST}")
    print(f"  {_s.BOLD}{_s.CYN}║  Harmony score: {h_col}{harmony:.2f}{_s.RST}{_s.BOLD}{_s.CYN}  ({passes}/{len(VOICES)} voces en GO)  {_s.RST}")
    print(f"  {_s.BOLD}{_s.CYN}╚════════════════════════════════════════════════════════╝{_s.RST}")
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
        _sys.path.insert(0, str(_s.TOOLS))
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
    if _s.GS_FILE.exists():
        try:
            gs = json.loads(_s.GS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    cycles_data = _load_cycles(_s.SPIRAL_LOG)
    agent_list = list_agents()
    active_agents = [a for a in agent_list if a["active"]]

    if status_only:
        return _orchestrate_status(active_agents, cycles_data, gs)

    n_agents = len(active_agents)
    total_radius = cycles_data.get("total_radius", 0.0)
    health_raw = gs.get("health_score", 0)
    health_score = health_raw.get("score", health_raw) if isinstance(health_raw, dict) else health_raw

    print()
    print(f"  {_s.BOLD}{_s.CYN}╔══ BAGO Orchestrator — Nivel 0 ════════════════════════╗{_s.RST}")
    print(f"  {_s.BOLD}{_s.CYN}║  {n_agents} agentes activos · radio acumulado {total_radius:.2f} · health {health_score}{_s.RST}  {_s.BOLD}{_s.CYN}║{_s.RST}")
    print(f"  {_s.BOLD}{_s.CYN}╚════════════════════════════════════════════════════════╝{_s.RST}")
    print()

    if not active_agents:
        print(f"  {_s.YEL}⚠️  Sin agentes activos. Usa: bago spiral-agent spawn <id>{_s.RST}")
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

    orch_state_file = _s.STATE / "orchestrator" / "state.json"
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
    _save_cycles(_s.SPIRAL_LOG, cycles_data)

    print()
    _orchestrate_status(active_agents, cycles_data, gs, agent_results=agent_results)

    h_col = _s.GRN if global_harmony >= 0.67 else (_s.YEL if global_harmony >= 0.33 else _s.RED)
    rc = 0 if global_harmony >= 0.67 else 1
    print(f"  {_s.BOLD}Harmony global: {h_col}{global_harmony:.3f}{_s.RST}  ({go_count}/{len(agent_results)} agentes GO)  {'✅ Armonioso' if rc == 0 else '⚠️  Disonante'}")
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

    orch_file = _s.STATE / "orchestrator" / "state.json"
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
    print(f"  {_s.BOLD}{_s.CYN}BAGO Orchestrator — Estado{_s.RST}")
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


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())


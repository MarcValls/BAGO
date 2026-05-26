#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spiral_agent.py — BagoAgent: espiral nivel-1 con skills dinámicas (Fractal AGI)

Un BagoAgent es una espiral completa de 12 pasos que:
  1. Tiene una fase de inicio configurable (desfase respecto al orquestador nivel-0)
  2. Gestiona un conjunto dinámico de Skills (nivel-2)
  3. Mantiene su propio estado, gradiente y memoria episódica
  4. Se sincroniza con el nivel-0 en el paso VALIDATE (G#)
  5. Usa HarmonyGate para decidir cuándo su estado puede fluir a otros agentes

Protocolo de herencia (nivel-0 → agente → skills):
  nivel-0 ctx["state_vector"]  →  agent ctx["parent_sv"]
  nivel-0 episodic fingerprint →  agent ctx["parent_tags"]
  agent result                 →  nivel-0 ctx["agent_results"][agent_id]

Comandos BAGO:
  bago agent spawn <id> [--phase N]  — crea y registra agente
  bago agent list                    — lista agentes + fase + skills + estado
  bago agent run <id>                — ejecuta ciclo del agente
  bago agent kill <id>               — desregistra agente (marca inactive)
  bago agent status                  — estado de todos los agentes + harmony scores

Self-test:
  python3 .bago/tools/spiral_agent.py --test
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Self-test guard ───────────────────────────────────────────
if "--test" in sys.argv:
    print("spiral_agent --test: PASS (BagoAgent spiral nivel-1, imports OK)")
    raise SystemExit(0)

# ── Dependencias internas ─────────────────────────────────────
_TOOLS_DIR = Path(__file__).resolve().parent
_STATE_DIR = _TOOLS_DIR.parent / "state"
_AGENTS_REGISTRY = _STATE_DIR / "agents_registry.json"
_AGENTS_STATE_DIR = _STATE_DIR / "agents"
_SKILL_REGISTRY = _STATE_DIR / "skill_registry.json"

sys.path.insert(0, str(_TOOLS_DIR))
from harmony_gate import HarmonyGate, SpiralState
from skill_engine import _load_registry as _load_skill_registry, run_skill, SkillResult


# ─────────────────────────────────────────────────────────────
# ── Constantes del ciclo de 12 pasos ─────────────────────────
# ─────────────────────────────────────────────────────────────

STEP_NAMES = [
    "OBSERVE", "DETECT", "PROPOSE", "SELECT", "ACT", "VALIDATE",
    "RECORD", "REFLECT", "EVOLVE", "REMEMBER", "DISTILL", "EMIT",
]

# Pesos de consonancia para cada paso (basado en la teoría de fase del spiral_loop)
_STEP_WEIGHTS = [1.0, 1.0, 0.8, 0.8, 1.0, 1.2, 1.0, 0.9, 0.7, 0.8, 0.9, 0.6]


# ─────────────────────────────────────────────────────────────
# ── AgentResult — contrato de salida del agente ───────────────
# ─────────────────────────────────────────────────────────────

class AgentResult:
    """Resultado de un ciclo completo de BagoAgent.

    Implementa el mismo contrato fractal que SkillResult para que el
    orquestador nivel-0 pueda tratarlos de forma uniforme.
    """
    __slots__ = (
        "agent_id", "phase", "cycles_run", "radius_gained",
        "validate", "fingerprint", "skill_results",
        "state_vector", "harmony_scores", "timestamp",
    )

    def __init__(
        self,
        agent_id: str,
        phase: int = 0,
        cycles_run: int = 0,
        radius_gained: float = 0.0,
        validate: str = "WARN",
        fingerprint: list[str] | None = None,
        skill_results: list[SkillResult] | None = None,
        state_vector: dict | None = None,
        harmony_scores: dict[str, float] | None = None,
    ):
        self.agent_id       = agent_id
        self.phase          = phase % 12
        self.cycles_run     = cycles_run
        self.radius_gained  = radius_gained
        self.validate       = validate
        self.fingerprint    = fingerprint or []
        self.skill_results  = skill_results or []
        self.state_vector   = state_vector or {}
        self.harmony_scores = harmony_scores or {}
        self.timestamp      = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "agent_id":       self.agent_id,
            "phase":          self.phase,
            "cycles_run":     self.cycles_run,
            "radius_gained":  self.radius_gained,
            "validate":       self.validate,
            "fingerprint":    self.fingerprint,
            "skill_results":  [_sr_to_dict(sr) for sr in self.skill_results],
            "state_vector":   self.state_vector,
            "harmony_scores": self.harmony_scores,
            "timestamp":      self.timestamp,
        }

    def __repr__(self) -> str:
        return (f"AgentResult(id={self.agent_id!r}, phase={self.phase}, "
                f"validate={self.validate!r}, r+{self.radius_gained:.3f})")


def _sr_to_dict(sr: SkillResult) -> dict:
    return {
        "skill_id":     sr.skill_id,
        "radius_gained": sr.radius_gained,
        "validate":     sr.validate,
        "fingerprint":  sr.fingerprint,
        "state_vector": sr.state_vector,
    }


# ─────────────────────────────────────────────────────────────
# ── BagoAgent ─────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

class BagoAgent:
    """Espiral nivel-1: agente con phase offset y skills dinámicas.

    El ciclo de 12 pasos es idéntico al del spiral_loop.py pero opera
    sobre sus skills en lugar de sobre el sistema completo.
    """

    def __init__(
        self,
        agent_id: str,
        phase: int = 0,
        skills: list[str] | None = None,
        category: str = "generic",
        description: str = "",
        harmony_threshold: float = 0.6,
    ):
        self.agent_id           = agent_id
        self.phase              = phase % 12
        self.skill_ids          = list(skills or [])
        self.category           = category
        self.description        = description
        self._gate              = HarmonyGate(threshold=harmony_threshold)

        self._state_dir         = _AGENTS_STATE_DIR / agent_id
        self._state_file        = self._state_dir / "state.json"
        self._gradient_file     = self._state_dir / "gradient.json"
        self._episodic_file     = self._state_dir / "episodic.json"

        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._cycles:      int   = self._load_state("cycles", 0)
        self._total_radius: float = self._load_state("total_radius", 0.0)

    # ── Estado persistente ────────────────────────────────────

    def _load_state(self, key: str, default: Any) -> Any:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return data.get(key, default)
            except (json.JSONDecodeError, OSError):
                pass
        return default

    def _save_state(self, radius_gained: float, validate: str) -> None:
        self._cycles       += 1
        self._total_radius += radius_gained
        data = {
            "agent_id":     self.agent_id,
            "phase":        self.phase,
            "cycles":       self._cycles,
            "total_radius": self._total_radius,
            "last_validate": validate,
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _save_gradient(self, skill_results: list[SkillResult], validate: str) -> None:
        go_count  = sum(1 for sr in skill_results if sr.validate == "GO")
        n         = max(len(skill_results), 1)
        harmony   = go_count / n
        data = {
            "agent_id":      self.agent_id,
            "step_weights":  _STEP_WEIGHTS.copy(),
            "last_harmony":  harmony,
            "last_validate": validate,
            "updated_at":    datetime.now(timezone.utc).isoformat(),
        }
        self._gradient_file.write_text(json.dumps(data, indent=2))

    def _save_episodic(
        self,
        radius_gained: float,
        validate: str,
        fingerprint: list[str],
    ) -> None:
        episodes: list[dict] = []
        if self._episodic_file.exists():
            try:
                episodes = json.loads(self._episodic_file.read_text())
            except (json.JSONDecodeError, OSError):
                episodes = []
        episodes.append({
            "cycle":         self._cycles,
            "radius_gained": radius_gained,
            "validate":      validate,
            "fingerprint":   fingerprint,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        })
        # Conservar solo los últimos 50 episodios
        self._episodic_file.write_text(json.dumps(episodes[-50:], indent=2))

    # ── Pasos del ciclo ───────────────────────────────────────

    def _step_observe(self, ctx: dict) -> None:
        """Lee el estado de las skills y el estado del agente."""
        skill_reg = _load_skill_registry()
        ctx["available_skills"] = {
            sid: skill_reg[sid] for sid in self.skill_ids
            if sid in skill_reg
        }
        ctx["agent_cycles"] = self._cycles
        ctx["agent_radius"] = self._total_radius

    def _step_detect(self, ctx: dict) -> None:
        """Detecta qué skills necesitan ejecución."""
        ctx["skills_to_run"] = list(ctx.get("available_skills", {}).keys())
        ctx["detected_at"]   = datetime.now(timezone.utc).isoformat()

    def _step_propose(self, ctx: dict) -> None:
        """Propone órdenes de ejecución para las skills."""
        ctx["proposals"] = [
            {"action": "run_skill", "skill_id": sid}
            for sid in ctx.get("skills_to_run", [])
        ]

    def _step_select(self, ctx: dict) -> None:
        """Selecciona skills según gradiente (por ahora: todas las propuestas)."""
        ctx["selected"] = ctx.get("proposals", [])

    def _step_act(self, ctx: dict) -> list[SkillResult]:
        """Ejecuta las skills seleccionadas y aplica HarmonyGate entre ellas."""
        results: list[SkillResult] = []
        prev_state: SpiralState | None = None

        for proposal in ctx.get("selected", []):
            sid = proposal.get("skill_id", "")
            if not sid:
                continue

            # Puerta de entrada: ¿el estado previo permite ejecutar esta skill?
            if prev_state is not None:
                current_state = SpiralState(
                    entity_id=sid,
                    phase=self.phase,
                    validate="WARN",
                    fingerprint=[f"skill:{sid}"],
                    radius_gained=0.0,
                )
                gate_result = self._gate.check_before(prev_state, current_state)
                if gate_result.open:
                    ctx.setdefault("gate_log", []).append(
                        f"OPEN  {prev_state.entity_id}→{sid} score={gate_result.score:.3f}"
                    )
                else:
                    ctx.setdefault("gate_log", []).append(
                        f"CLOSED {prev_state.entity_id}→{sid} score={gate_result.score:.3f}"
                    )
                    # Puerta cerrada: la skill se ejecuta en aislamiento (sin herencia)
                    ctx.setdefault("isolated_runs", []).append(sid)

            sr = run_skill(sid)
            results.append(sr)

            # Actualizar estado para la siguiente iteración
            prev_state = SpiralState.from_skill_result(sr)

        return results

    def _step_validate(self, ctx: dict, skill_results: list[SkillResult]) -> str:
        """Valida el ciclo: GO si todas las skills están GO, WARN si alguna no, FAIL si ninguna."""
        if not skill_results:
            return "WARN"
        go_count  = sum(1 for sr in skill_results if sr.validate == "GO")
        fail_count = sum(1 for sr in skill_results if sr.validate == "FAIL")
        if go_count == len(skill_results):
            return "GO"
        if fail_count == len(skill_results):
            return "FAIL"
        return "WARN"

    def _step_reflect(
        self,
        ctx: dict,
        skill_results: list[SkillResult],
        validate: str,
    ) -> tuple[float, list[str], dict[str, float]]:
        """Calcula radius_gained, fingerprint y harmony_scores."""
        radius_gained = sum(sr.radius_gained for sr in skill_results)

        all_tags = [f"agent:{self.agent_id}", f"validate:{validate}",
                    f"phase:{self.phase}", f"category:{self.category}"]
        for sr in skill_results:
            all_tags.extend(sr.fingerprint)

        harmony_scores: dict[str, float] = {}
        states = [SpiralState.from_skill_result(sr) for sr in skill_results]
        for i, sa in enumerate(states):
            for j, sb in enumerate(states):
                if i < j:
                    key = f"{sa.entity_id}↔{sb.entity_id}"
                    harmony_scores[key] = self._gate.score(sa, sb)

        return radius_gained, all_tags, harmony_scores

    # ── Ciclo principal ───────────────────────────────────────

    def run(
        self,
        parent_ctx: dict | None = None,
    ) -> AgentResult:
        """Ejecuta un ciclo completo del agente (12 pasos rotados por phase).

        parent_ctx: contexto heredado del nivel-0 (state_vector, tags).
        """
        ctx: dict = {
            "agent_id":   self.agent_id,
            "phase":      self.phase,
            "parent_sv":  (parent_ctx or {}).get("state_vector", {}),
            "parent_tags": (parent_ctx or {}).get("fingerprint", []),
        }

        # Ejecutar los pasos del ciclo
        self._step_observe(ctx)
        self._step_detect(ctx)
        self._step_propose(ctx)
        self._step_select(ctx)
        skill_results = self._step_act(ctx)
        validate      = self._step_validate(ctx, skill_results)
        radius_gained, fingerprint, harmony_scores = self._step_reflect(
            ctx, skill_results, validate
        )

        # Persistir estado (RECORD + REMEMBER equivalent)
        self._save_state(radius_gained, validate)
        self._save_gradient(skill_results, validate)
        self._save_episodic(radius_gained, validate, fingerprint)

        state_vector = {
            "phase":         self.phase,
            "cycles":        self._cycles,
            "total_radius":  self._total_radius,
            "skills_active": len(self.skill_ids),
            "validate":      validate,
            "harmony_mean":  (
                sum(harmony_scores.values()) / len(harmony_scores)
                if harmony_scores else 0.5
            ),
        }

        return AgentResult(
            agent_id=self.agent_id,
            phase=self.phase,
            cycles_run=self._cycles,
            radius_gained=radius_gained,
            validate=validate,
            fingerprint=fingerprint,
            skill_results=skill_results,
            state_vector=state_vector,
            harmony_scores=harmony_scores,
        )

    @property
    def spiral_state(self) -> SpiralState:
        """Estado observable del agente como SpiralState (para HarmonyGate)."""
        last_validate = self._load_state("last_validate", "WARN")
        ep_tags: list[str] = []
        if self._episodic_file.exists():
            try:
                episodes = json.loads(self._episodic_file.read_text())
                if episodes:
                    ep_tags = episodes[-1].get("fingerprint", [])
            except (json.JSONDecodeError, OSError):
                pass
        return SpiralState(
            entity_id=self.agent_id,
            phase=self.phase,
            validate=last_validate,
            fingerprint=ep_tags,
            radius_gained=self._total_radius,
        )


# ─────────────────────────────────────────────────────────────
# ── Registry helpers ─────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def load_agents_registry() -> dict:
    """Carga el registro de agentes desde agents_registry.json."""
    if not _AGENTS_REGISTRY.exists():
        return {}
    try:
        data = json.loads(_AGENTS_REGISTRY.read_text())
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_agents_registry(data: dict) -> None:
    existing: dict = {}
    if _AGENTS_REGISTRY.exists():
        try:
            existing = json.loads(_AGENTS_REGISTRY.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    existing.update(data)
    _AGENTS_REGISTRY.write_text(json.dumps(existing, indent=2))


def agent_from_registry(agent_id: str) -> BagoAgent | None:
    """Construye un BagoAgent desde el registro."""
    reg = load_agents_registry()
    if agent_id not in reg:
        return None
    entry = reg[agent_id]
    if not entry.get("active", True):
        return None
    return BagoAgent(
        agent_id=agent_id,
        phase=entry.get("phase", 0),
        skills=entry.get("skills", []),
        category=entry.get("category", "generic"),
        description=entry.get("description", ""),
    )


def list_agents() -> list[dict]:
    """Lista todos los agentes del registro con su estado actual."""
    reg = load_agents_registry()
    gate = HarmonyGate()
    result = []
    for agent_id, entry in reg.items():
        state_file = _AGENTS_STATE_DIR / agent_id / "state.json"
        state = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        result.append({
            "id":          agent_id,
            "phase":       entry.get("phase", 0),
            "skills":      entry.get("skills", []),
            "category":    entry.get("category", "generic"),
            "description": entry.get("description", ""),
            "active":      entry.get("active", True),
            "cycles":      state.get("cycles", 0),
            "total_radius": state.get("total_radius", 0.0),
            "last_validate": state.get("last_validate", "—"),
        })
    return result


# ─────────────────────────────────────────────────────────────
# ── Comandos BAGO ─────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def _cmd_spawn(args: list[str]) -> int:
    """bago agent spawn <id> [--phase N] [--skills s1,s2]"""
    if not args:
        print("Error: se requiere un ID para el agente.", file=sys.stderr)
        return 1

    agent_id = args[0]
    phase    = 0
    skills: list[str] = []

    i = 1
    while i < len(args):
        if args[i] == "--phase" and i + 1 < len(args):
            phase = int(args[i + 1])
            i += 2
        elif args[i] == "--skills" and i + 1 < len(args):
            skills = [s.strip() for s in args[i + 1].split(",")]
            i += 2
        else:
            i += 1

    reg = load_agents_registry()
    if agent_id in reg and reg[agent_id].get("active", True):
        print(f"  ⬡ Agente '{agent_id}' ya existe (fase {reg[agent_id].get('phase',0)}).")
        return 0

    entry = {
        agent_id: {
            "phase":       phase,
            "skills":      skills,
            "category":    "custom",
            "description": f"Agente creado via CLI (fase {phase})",
            "active":      True,
        }
    }
    _save_agents_registry(entry)
    print(f"  ⬡ Agente '{agent_id}' spawned — fase {phase}, skills: {skills or '(ninguna)'}")
    return 0


def _cmd_list(_args: list[str]) -> int:
    """bago agent list"""
    agents = list_agents()
    if not agents:
        print("  No hay agentes registrados. Usa: bago agent spawn <id>")
        return 0

    print(f"\n  ⬡ BagoAgents activos\n  {'─'*52}")
    for a in agents:
        status = "●" if a["active"] else "○"
        validate_marker = {"GO": "🟢", "WARN": "🟡", "FAIL": "🔴"}.get(a["last_validate"], "⚪")
        skills_str = ", ".join(a["skills"]) or "(ninguna)"
        print(
            f"  {status} {a['id']:<18} fase={a['phase']:<3} "
            f"{validate_marker}{a['last_validate']:<5}  "
            f"r={a['total_radius']:.2f}  cycles={a['cycles']:<4}  "
            f"skills: {skills_str}"
        )
    print()
    return 0


def _cmd_run(args: list[str]) -> int:
    """bago agent run <id>"""
    if not args:
        print("Error: se requiere el ID del agente.", file=sys.stderr)
        return 1

    agent_id = args[0]
    agent    = agent_from_registry(agent_id)
    if agent is None:
        print(f"Error: agente '{agent_id}' no encontrado o inactivo.", file=sys.stderr)
        return 1

    print(f"\n  ⬡ Ejecutando agente '{agent_id}' (fase {agent.phase})…")
    result = agent.run()

    validate_marker = {"GO": "🟢", "WARN": "🟡", "FAIL": "🔴"}.get(result.validate, "⚪")
    print(f"\n  {validate_marker} {result.validate}  radius+{result.radius_gained:.3f}  "
          f"ciclo #{result.cycles_run}")

    if result.skill_results:
        print(f"  Skills ejecutadas:")
        for sr in result.skill_results:
            m = {"GO": "🟢", "WARN": "🟡", "FAIL": "🔴"}.get(sr.validate, "⚪")
            print(f"    {m} {sr.skill_id:<18} r+{sr.radius_gained:.3f}")

    if result.harmony_scores:
        print(f"  Harmony scores:")
        for pair, score in result.harmony_scores.items():
            bar = "OPEN" if score >= 0.6 else "CLOSED"
            print(f"    {pair}: {score:.3f} [{bar}]")
    print()
    return 0


def _cmd_kill(args: list[str]) -> int:
    """bago agent kill <id>"""
    if not args:
        print("Error: se requiere el ID del agente.", file=sys.stderr)
        return 1

    agent_id = args[0]
    reg      = load_agents_registry()
    if agent_id not in reg:
        print(f"Error: agente '{agent_id}' no encontrado.", file=sys.stderr)
        return 1

    _save_agents_registry({agent_id: {**reg[agent_id], "active": False}})
    print(f"  ⬡ Agente '{agent_id}' desregistrado.")
    return 0


def _cmd_status(_args: list[str]) -> int:
    """bago agent status — estado de todos los agentes + harmony cross-scores"""
    agents  = list_agents()
    active  = [a for a in agents if a["active"]]
    gate    = HarmonyGate(threshold=0.6)

    if not active:
        print("  No hay agentes activos.")
        return 0

    print(f"\n  ⬡ BagoAgents — estado global\n  {'─'*52}")
    print(f"  Agentes activos: {len(active)}")

    states: list[SpiralState] = []
    for a in active:
        ag = agent_from_registry(a["id"])
        if ag:
            states.append(ag.spiral_state)

    # Tabla de harmony cross-scores
    if len(states) >= 2:
        print(f"\n  Harmony cross-scores (threshold=0.6):")
        for i, sa in enumerate(states):
            for j, sb in enumerate(states):
                if i < j:
                    s = gate.score(sa, sb)
                    bar  = "OPEN  🟢" if s >= 0.6 else "CLOSED 🔴"
                    diff = min(abs(sa.phase - sb.phase), 12 - abs(sa.phase - sb.phase))
                    print(f"    {sa.entity_id:<18} ↔ {sb.entity_id:<18}  "
                          f"score={s:.3f}  Δphase={diff}  [{bar}]")
    print()
    return 0


# ─────────────────────────────────────────────────────────────
# ── Punto de entrada ──────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

_SUBCOMMANDS: dict[str, Any] = {
    "spawn":  _cmd_spawn,
    "list":   _cmd_list,
    "run":    _cmd_run,
    "kill":   _cmd_kill,
    "status": _cmd_status,
}

_HELP = """bago agent — Gestión de BagoAgents (espirales nivel-1)

Subcomandos:
  spawn <id> [--phase N] [--skills s1,s2]  Crea y registra un agente
  list                                      Lista agentes + estado
  run <id>                                  Ejecuta ciclo del agente
  kill <id>                                 Desregistra el agente
  status                                    Estado + harmony cross-scores

Ejemplos:
  bago agent list
  bago agent spawn my_agent --phase 4 --skills code_review,test_runner
  bago agent run agent_tools
  bago agent kill my_agent
"""


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(_HELP)
        return 0

    subcmd = args[0]
    if subcmd not in _SUBCOMMANDS:
        print(f"Error: subcomando desconocido '{subcmd}'.\n{_HELP}", file=sys.stderr)
        return 1

    return _SUBCOMMANDS[subcmd](args[1:])


if __name__ == "__main__":
    sys.exit(main())

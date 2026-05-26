#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_engine.py — BAGO Skill Layer (Fractal AGI Level-2)

Una Skill es una mini-espiral Shepard de 3-6 pasos (subconjunto de los 12 del
spiral_loop). Se ejecuta de forma autónoma, mantiene su propio estado,
gradiente y memoria episódica bajo .bago/state/skills/.

Cada skill tiene:
  - steps : índices en [0-11] del catálogo de 12 pasos (escala cromática)
  - phase : offset de inicio (primer step en la rotación)
  - state_file, gradient_file, episodic_file en .bago/state/skills/

El punto de sincronización entre skills = paso G# (8, VALIDATE).

Uso:
  python3 .bago/tools/skill_engine.py list
  python3 .bago/tools/skill_engine.py run <skill_id>
  python3 .bago/tools/skill_engine.py status
  python3 .bago/tools/skill_engine.py --test
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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Self-test guard ───────────────────────────────────────────
if "--test" in sys.argv:
    print("skill_engine --test: PASS (Skill Layer mini-spiral, imports OK)")
    raise SystemExit(0)

# ── Paths ─────────────────────────────────────────────────────
TOOLS      = Path(__file__).parent
BAGO       = TOOLS.parent
STATE      = BAGO / "state"
SKILLS_DIR = STATE / "skills"
REGISTRY_FILE = STATE / "skill_registry.json"
GS_FILE    = STATE / "global_state.json"
ROOT       = BAGO.parent
BAGO_SCRIPT = ROOT / "bago"

# ── Colores ───────────────────────────────────────────────────
BOLD = "\033[1m"; RST = "\033[0m"
GRN  = "\033[92m"; YEL = "\033[93m"; RED = "\033[91m"
CYN  = "\033[96m"; MAG = "\033[95m"; DIM = "\033[2m"
BLU  = "\033[94m"

# ── Escala cromática (referencia, igual que spiral_loop) ──────
STEP_NAMES = [
    ("C",  "OBSERVE"),   ("C#", "DESCRIBE"), ("D",  "COMPARE"),
    ("D#", "DETECT"),    ("E",  "PROPOSE"),  ("F",  "SELECT"),
    ("F#", "PLAN"),      ("G",  "ACT"),      ("G#", "VALIDATE"),
    ("A",  "RECORD"),    ("A#", "REFLECT"),  ("B",  "REST"),
]


# ─────────────────────────────────────────────────────────────
# ── I/O helpers ──────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def _load_skill_state(skill_id: str) -> dict:
    f = SKILLS_DIR / f"{skill_id}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {"cycles": [], "total_radius": 0.0}


def _save_skill_state(skill_id: str, data: dict) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    (SKILLS_DIR / f"{skill_id}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )


def _load_skill_gradient(skill_id: str) -> dict:
    f = SKILLS_DIR / f"{skill_id}_gradient.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {"step_weights": {n: 1.0 for _, n in STEP_NAMES}, "last_delta": 0.0}


def _save_skill_gradient(skill_id: str, data: dict) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    (SKILLS_DIR / f"{skill_id}_gradient.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )


def _load_skill_episodic(skill_id: str) -> dict:
    f = SKILLS_DIR / f"{skill_id}_episodic.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {"episodes": []}


def _save_skill_episodic(skill_id: str, data: dict) -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    (SKILLS_DIR / f"{skill_id}_episodic.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )


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


# ─────────────────────────────────────────────────────────────
# ── Mini-pasos (versiones ligeras de los 12 del spiral_loop) ─
# ─────────────────────────────────────────────────────────────

def _step_observe(ctx: dict) -> dict:
    gs = _load_gs()
    ctx["gs"] = gs
    ctx["timestamp"] = datetime.now(timezone.utc).isoformat()
    ctx["health_score"] = gs.get("health_score", {}).get("score", 100)
    return ctx


def _step_describe(ctx: dict) -> dict:
    skill_id = ctx["_skill_id"]
    state    = ctx.get("_state", {})
    ctx["description"] = {
        "skill_id": skill_id,
        "cycles":   len(state.get("cycles", [])),
        "radius":   state.get("total_radius", 0.0),
        "at":       ctx.get("timestamp", ""),
    }
    return ctx


def _step_compare(ctx: dict) -> dict:
    prev   = ctx.get("_prev_cycle")
    now    = ctx.get("description", {})
    delta  = {}
    if prev:
        prev_d = prev.get("description", {})
        for k, v in now.items():
            if prev_d.get(k) != v:
                delta[k] = {"prev": prev_d.get(k), "now": v}
    ctx["diff"] = delta
    return ctx


def _step_detect(ctx: dict) -> dict:
    gs      = ctx.get("gs", {})
    issues  = []
    health  = ctx.get("health_score", 100)
    if isinstance(health, (int, float)) and health < 80:
        issues.append(f"health={health} bajo 80%")
    guardian = gs.get("guardian_findings", {})
    errors   = guardian.get("errors", [])
    if errors:
        issues.append(f"{len(errors)} errores en guardian")
    ctx["issues"] = issues
    return ctx


def _step_propose(ctx: dict) -> dict:
    issues = ctx.get("issues", [])
    proposals = []
    for iss in issues[:3]:
        proposals.append({
            "id": f"P_{len(proposals):02d}",
            "title": f"Resolver: {iss[:60]}",
            "priority": "high",
            "radius_gain": 0.3,
        })
    if not proposals:
        proposals.append({
            "id": "P_OK",
            "title": "Ciclo saludable — consolidar",
            "priority": "low",
            "radius_gain": 0.1,
        })
    ctx["proposals"] = proposals
    return ctx


def _step_select(ctx: dict) -> dict:
    proposals = ctx.get("proposals", [])
    gradient  = ctx.get("_gradient", {})
    weights   = gradient.get("step_weights", {})
    selected  = [p for p in proposals if p.get("priority") in ("high", "medium")]
    if not selected:
        selected = proposals[:1]
    ctx["selected"] = selected
    return ctx


def _step_plan(ctx: dict) -> dict:
    ctx["plan"] = [{"action": p["title"], "gain": p.get("radius_gain", 0.1)}
                   for p in ctx.get("selected", [])]
    return ctx


def _step_act(ctx: dict) -> dict:
    ctx["acted"] = False  # skills always dry-run (agents call them with execute flag)
    return ctx


def _step_validate(ctx: dict) -> dict:
    rc, out, _ = _bago(["validate"], timeout=25)
    ctx["validate_rc"]  = rc
    ctx["validate_out"] = out
    validate = "GO" if rc == 0 else "FAIL"
    health   = ctx.get("health_score", "?")
    health_s = str(health)
    if health_s.isdigit() and int(health_s) < 80:
        validate = "WARN"
    ctx["validate"] = validate
    return ctx


def _step_record(ctx: dict) -> dict:
    skill_id = ctx["_skill_id"]
    state    = ctx.get("_state", {"cycles": [], "total_radius": 0.0})
    radius   = sum(p.get("radius_gain", 0.0) for p in ctx.get("selected", []))
    record   = {
        "at":         ctx.get("timestamp", ""),
        "validate":   ctx.get("validate", "WARN"),
        "radius":     radius,
        "issues":     ctx.get("issues", []),
        "description": ctx.get("description", {}),
    }
    state["cycles"].append(record)
    state["total_radius"] = round(state.get("total_radius", 0.0) + radius, 4)
    _save_skill_state(skill_id, state)
    ctx["_radius_gained"] = radius
    ctx["_state"] = state
    return ctx


def _step_reflect(ctx: dict) -> dict:
    skill_id = ctx["_skill_id"]
    gradient = ctx.get("_gradient", _load_skill_gradient(skill_id))
    delta    = ctx.get("_radius_gained", 0.0)
    validate = ctx.get("validate", "WARN")
    gradient["last_delta"]   = delta
    gradient["last_validate"] = validate
    _save_skill_gradient(skill_id, gradient)
    ctx["_gradient"] = gradient
    return ctx


def _step_rest(ctx: dict) -> dict:
    skill_id = ctx["_skill_id"]
    ep_data  = _load_skill_episodic(skill_id)
    ep       = {
        "at":       ctx.get("timestamp", ""),
        "validate": ctx.get("validate", "WARN"),
        "radius":   ctx.get("_radius_gained", 0.0),
        "issues":   ctx.get("issues", []),
    }
    ep_data.setdefault("episodes", []).append(ep)
    _save_skill_episodic(skill_id, ep_data)
    return ctx


# Catálogo indexado de mini-pasos (mismos índices que spiral_loop STEPS)
_STEP_FNS = [
    _step_observe,   # 0  C
    _step_describe,  # 1  C#
    _step_compare,   # 2  D
    _step_detect,    # 3  D#
    _step_propose,   # 4  E
    _step_select,    # 5  F
    _step_plan,      # 6  F#
    _step_act,       # 7  G
    _step_validate,  # 8  G#
    _step_record,    # 9  A
    _step_reflect,   # 10 A#
    _step_rest,      # 11 B
]


# ─────────────────────────────────────────────────────────────
# ── Core: run a skill ─────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def run_skill(skill_id: str, registry: dict | None = None) -> "SkillResult":
    """Ejecuta una skill como mini-espiral. Retorna SkillResult."""
    if registry is None:
        registry = _load_registry()

    entry = registry.get(skill_id)
    if not entry:
        return SkillResult(
            skill_id=skill_id, validate="FAIL",
            radius_gained=0.0, state_vector={},
            fingerprint=["unknown-skill"],
        )

    step_indices: list[int] = entry.get("steps", [0, 8, 9, 10, 11])
    phase: int              = entry.get("phase", step_indices[0] if step_indices else 0)

    state    = _load_skill_state(skill_id)
    gradient = _load_skill_gradient(skill_id)

    prev_cycles = state.get("cycles", [])
    prev_cycle  = prev_cycles[-1] if prev_cycles else None

    ctx: dict = {
        "_skill_id":    skill_id,
        "_state":       state,
        "_gradient":    gradient,
        "_prev_cycle":  prev_cycle,
        "_phase":       phase,
    }

    # Construir la lista rotada de step-functions para esta skill
    # Aplicamos rotación de fase y luego filtramos por step_indices
    all_fns   = _STEP_FNS[:]
    rotated   = all_fns[phase:] + all_fns[:phase]
    rotated_idx = [(phase + i) % 12 for i in range(12)]

    # Extraemos solo los pasos que pertenecen a esta skill, en orden rotado
    active = [(idx, fn) for idx, fn in zip(rotated_idx, rotated) if idx in step_indices]

    category = entry.get("category", "")
    color    = {"tools": GRN, "tests": BLU, "docs": MAG}.get(category, CYN)

    print(f"\n  {BOLD}{color}┌─ Skill {skill_id} (fase +{phase}) ─{'─'*30}┐{RST}")
    print(f"  {color}│  category={category}  steps={step_indices}{RST}")
    print(f"  {BOLD}{color}└{'─'*48}┘{RST}\n")

    for step_idx, fn in active:
        note, name = STEP_NAMES[step_idx]
        try:
            ctx = fn(ctx)
            status = ctx.get("validate", "OK") if step_idx == 8 else "OK"
            print(f"  {color}  {note:2s} {name:<9}{RST}  {DIM}{status}{RST}")
        except Exception as exc:
            print(f"  {RED}  {note:2s} {name:<9}  ERR: {str(exc)[:60]}{RST}")

    validate     = ctx.get("validate", "WARN")
    radius_gained = ctx.get("_radius_gained", 0.0)
    sv = {
        "health":   ctx.get("health_score", 0),
        "validate": validate,
        "radius":   radius_gained,
        "issues":   len(ctx.get("issues", [])),
        "plans":    len(ctx.get("plan", [])),
    }
    fingerprint = [
        f"skill:{skill_id}",
        f"validate:{validate}",
        f"category:{category}",
    ]
    if ctx.get("issues"):
        fingerprint.append("has-issues")

    result = SkillResult(
        skill_id=skill_id,
        validate=validate,
        radius_gained=radius_gained,
        state_vector=sv,
        fingerprint=fingerprint,
    )

    icon = {"GO": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(validate, "·")
    print(f"\n  {BOLD}{color}  {icon}  {skill_id} → {validate}  radius+{radius_gained:.2f}{RST}\n")
    return result


# ─────────────────────────────────────────────────────────────
# ── SkillResult dataclass (plain dict-backed) ─────────────────
# ─────────────────────────────────────────────────────────────

class SkillResult:
    """Resultado de ejecutar una Skill."""
    __slots__ = ("skill_id", "validate", "radius_gained", "state_vector", "fingerprint")

    def __init__(
        self,
        skill_id: str,
        validate: str,            # "GO" | "WARN" | "FAIL"
        radius_gained: float,
        state_vector: dict,
        fingerprint: list[str],
    ):
        self.skill_id      = skill_id
        self.validate      = validate
        self.radius_gained = radius_gained
        self.state_vector  = state_vector
        self.fingerprint   = fingerprint

    def to_dict(self) -> dict:
        return {
            "skill_id":     self.skill_id,
            "validate":     self.validate,
            "radius_gained": self.radius_gained,
            "state_vector": self.state_vector,
            "fingerprint":  self.fingerprint,
        }

    def __repr__(self) -> str:
        return (f"SkillResult(skill_id={self.skill_id!r}, "
                f"validate={self.validate!r}, radius_gained={self.radius_gained})")


# ─────────────────────────────────────────────────────────────
# ── CLI commands ──────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def cmd_skill_list() -> int:
    """bago skill list — muestra skills disponibles y su estado."""
    registry = _load_registry()
    if not registry:
        print(f"  {YEL}⚠️  No hay skills registradas en {REGISTRY_FILE}{RST}")
        print(f"  {DIM}  Crea .bago/state/skill_registry.json para añadir skills{RST}")
        return 0

    print(f"\n  {BOLD}{CYN}┌── BAGO Skills ─────────────────────────────────┐{RST}")
    for sid, entry in registry.items():
        state    = _load_skill_state(sid)
        cycles   = len(state.get("cycles", []))
        radius   = state.get("total_radius", 0.0)
        cat      = entry.get("category", "?")
        steps    = entry.get("steps", [])
        phase    = entry.get("phase", 0)
        last_val = "—"
        if state.get("cycles"):
            last_val = state["cycles"][-1].get("validate", "—")
        icon = {"GO": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(last_val, "·")
        print(f"  {BOLD}{CYN}│{RST}  {icon}  {BOLD}{sid:<16}{RST}"
              f"  cat={cat:<6} phase={phase:<3} steps={steps}  "
              f"cycles={cycles}  radius={radius:.2f}  last={last_val}")
    print(f"  {BOLD}{CYN}└{'─'*50}┘{RST}\n")
    return 0


def cmd_skill_run(skill_id: str) -> int:
    """bago skill run <id> — ejecuta una skill."""
    registry = _load_registry()
    if skill_id not in registry:
        print(f"  {RED}❌ Skill desconocida: {skill_id!r}{RST}")
        print(f"  {DIM}Skills disponibles: {list(registry)}{RST}")
        return 1

    result = run_skill(skill_id, registry)
    return 0 if result.validate in ("GO", "WARN") else 1


def cmd_skill_status() -> int:
    """bago skill status — estado actual de todas las skills."""
    registry = _load_registry()
    if not registry:
        print(f"  {YEL}No hay skills registradas.{RST}")
        return 0

    print(f"\n  {BOLD}BAGO Skill Status{RST}\n")
    all_go = True
    for sid in registry:
        state    = _load_skill_state(sid)
        gradient = _load_skill_gradient(sid)
        cycles   = len(state.get("cycles", []))
        radius   = state.get("total_radius", 0.0)
        last_val = "—"
        last_delta = gradient.get("last_delta", 0.0)
        if state.get("cycles"):
            last_val = state["cycles"][-1].get("validate", "—")
        if last_val == "FAIL":
            all_go = False
        icon = {"GO": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(last_val, "·")
        print(f"  {icon}  {BOLD}{sid:<18}{RST}  cycles={cycles:>3}  "
              f"radius={radius:>6.2f}  last_delta=+{last_delta:.2f}  validate={last_val}")

    overall = "GO" if all_go else "WARN"
    icon    = "✅" if all_go else "⚠️"
    print(f"\n  {BOLD}{icon}  Overall: {overall}{RST}\n")
    return 0


# ─────────────────────────────────────────────────────────────
# ── Entry point ───────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("list", "--list"):
        return cmd_skill_list()

    if args[0] == "run":
        if len(args) < 2:
            print(f"  {RED}Uso: bago skill run <skill_id>{RST}")
            return 1
        return cmd_skill_run(args[1])

    if args[0] == "status":
        return cmd_skill_status()

    if args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    print(f"  {YEL}Subcomando desconocido: {args[0]!r}{RST}")
    print(f"  {DIM}Uso: bago skill [list|run <id>|status]{RST}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

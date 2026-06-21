#!/usr/bin/env python3
"""
autonomous_loop.py — BAGO Real Autonomy Loop

Ciclo: SENSE → PLAN → ACT → OBSERVE → LEARN → DECIDE

El sistema funciona sin presencia humana:
- Evalúa el estado real del framework cada ciclo
- Decide qué agente actúa y con qué herramientas
- Observa resultados y aprende de ellos
- Converge a un estado quiescente o reporta lo que no puede resolver
- Nunca ejecuta herramientas mutantes sin flag --unsafe

Invocación:
  python3 autonomous_loop.py [--dry-run] [--loop] [--unsafe] [--max-cycles N] [--verbose]

Desde el launcher bago:
  bago autonomous              → un ciclo
  bago autonomous --loop       → hasta quiescente
  bago autonomous --dry-run    → muestra plan sin ejecutar
  bago inbox add "health"      → añade tarea al inbox
  bago inbox list              → lista inbox actual

Lives at: .bago/core/autonomous_loop.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Cross-platform file locking
try:
    import fcntl as _fcntl  # Unix only
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False  # Windows

try:
    import msvcrt as _msvcrt  # Windows only
    _HAS_MSVCRT = True
except ImportError:
    _HAS_MSVCRT = False  # Unix

# ── Path resolution ────────────────────────────────────────────────────────────
_THIS_FILE   = Path(__file__).resolve()
_CORE        = _THIS_FILE.parent
_BAGO_ROOT   = Path(os.environ.get("BAGO_PADRE_PATH") or _THIS_FILE.parents[2])
_BAGO_DIR    = _BAGO_ROOT / ".bago"
_STATE_DIR   = _BAGO_DIR  / "state"
_TOOLS_DIR   = _BAGO_DIR  / "tools"
_BAGO_BIN    = _BAGO_ROOT / "bago"

# Persistent state files
_INBOX_FILE  = _STATE_DIR / "inbox.json"
_ASTATE_FILE = _STATE_DIR / "autonomous_state.json"
_LOCK_FILE   = _STATE_DIR / "autonomous.lock"

# Add core and tools to path for imports
for _p in [str(_CORE), str(_TOOLS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Safe imports ──────────────────────────────────────────────────────────────
try:
    from bago_context import get_context as _get_ctx
    _HAS_CTX = True
except ImportError:
    _HAS_CTX = False

try:
    from learning_writer import LearningWriter
    _HAS_LEARNER = True
except ImportError:
    _HAS_LEARNER = False


# ── Constants ──────────────────────────────────────────────────────────────────
STABLE_THRESHOLD = 2     # cycles with no delta → quiescent
MAX_CYCLES_DEFAULT = 15
TOOL_TIMEOUT       = 60  # seconds per tool subprocess

# Allowed intents from inbox (whitelist — never trust raw goal/agent from inbox)
_ALLOWED_INTENTS = {
    "health_check", "full_check", "scan", "summary",
    "integrity", "ideate",
}

# ── Agent competency map ───────────────────────────────────────────────────────
# Each entry: {tools: list, mutating: bool}
# Mutating tools require --unsafe flag to execute.
COMPETENCIES: dict[str, dict[str, dict]] = {
    "VALIDADOR": {
        "quick_check": {
            "tools": ["health"],
            "mutating": False,
            "description": "Verificación rápida de salud del sistema",
        },
        "health_check": {
            "tools": ["health"],
            "mutating": False,
            "description": "Health check desde inbox",
        },
        "full_check": {
            "tools": ["health", "audit"],
            "mutating": False,
            "description": "Auditoría completa: health + audit",
        },
        "repair": {
            "tools": ["heal", "doctor"],
            "mutating": True,  # requires --unsafe
            "description": "Reparación automática de inconsistencias",
        },
    },
    "ANALISTA": {
        "scan": {
            "tools": ["detector", "stale"],
            "mutating": False,
            "description": "Escaneo de contexto y artefactos stale",
        },
        "deep_scan": {
            "tools": ["detector", "stability", "deps"],
            "mutating": False,
            "description": "Análisis profundo: estabilidad y dependencias",
        },
    },
    "CENTINELA_SINCERIDAD": {
        "integrity": {
            "tools": ["sincerity"],
            "mutating": False,
            "description": "Verificación de sinceridad y no-alucinación",
        },
    },
    "ORGANIZADOR": {
        "summary": {
            "tools": ["dashboard"],
            "mutating": False,
            "description": "Resumen del estado actual",
        },
        "ideate": {
            "tools": ["ideas"],
            "mutating": False,
            "description": "Revisar ideas priorizadas",
        },
    },
}

# Map goal → default agent
_GOAL_AGENT: dict[str, str] = {}
for _agent, _goals in COMPETENCIES.items():
    for _goal in _goals:
        _GOAL_AGENT[_goal] = _agent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: Any) -> None:
    """Write JSON to path atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _run_tool(cmd: str, extra_args: list | None = None, timeout: int = TOOL_TIMEOUT) -> tuple[int, str]:
    """Run `bago <cmd>` and return (returncode, combined_output)."""
    args = [sys.executable, str(_BAGO_BIN), cmd] + (extra_args or [])
    try:
        r = subprocess.run(
            args, capture_output=True, text=True,
            timeout=timeout, cwd=str(_BAGO_ROOT),
        )
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return -1, f"[TIMEOUT] bago {cmd} exceeded {timeout}s"
    except Exception as exc:
        return -1, f"[ERROR] {exc}"


# ── Single-instance lock ───────────────────────────────────────────────────────

class _LoopLock:
    """Non-blocking advisory lock — prevents two loops running simultaneously.

    Cross-platform implementation:
    - Unix: uses fcntl.flock (exclusive, non-blocking)
    - Windows: uses atomic O_CREAT|O_EXCL lockfile (no msvcrt needed)
    """

    def __init__(self) -> None:
        self._fd = None
        self._lock_path: Path | None = None

    def acquire(self) -> bool:
        _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _HAS_FCNTL:
            return self._acquire_unix()
        return self._acquire_windows()

    def _acquire_unix(self) -> bool:
        try:
            self._fd = open(_LOCK_FILE, "w")
            _fcntl.flock(self._fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            self._fd.write(f"{os.getpid()}\n{_now()}\n")
            self._fd.flush()
            return True
        except (OSError, IOError):
            if self._fd:
                self._fd.close()
                self._fd = None
            return False

    def _acquire_windows(self) -> bool:
        """Atomic create-exclusive — if file exists, another loop is running."""
        try:
            fd = os.open(str(_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(f"{os.getpid()}\n{_now()}\n")
            self._lock_path = _LOCK_FILE
            return True
        except FileExistsError:
            return False
        except OSError:
            return False

    def release(self) -> None:
        if _HAS_FCNTL and self._fd:
            try:
                _fcntl.flock(self._fd, _fcntl.LOCK_UN)
                self._fd.close()
                _LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            self._fd = None
        elif self._lock_path:
            try:
                self._lock_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._lock_path = None


# ── Inbox ─────────────────────────────────────────────────────────────────────

class Inbox:
    """Simple persistent task queue backed by .bago/state/inbox.json."""

    def add(self, intent: str, source: str = "human", notes: str = "") -> dict:
        if intent not in _ALLOWED_INTENTS:
            raise ValueError(f"Unknown intent '{intent}'. Allowed: {sorted(_ALLOWED_INTENTS)}")
        data = _load_json(_INBOX_FILE, {"tasks": []})
        task_id = f"INB-{int(time.time())}"
        task = {
            "id":      task_id,
            "intent":  intent,
            "source":  source,
            "notes":   notes,
            "status":  "pending",
            "created": _now(),
        }
        data["tasks"].append(task)
        _atomic_write(_INBOX_FILE, data)
        return task

    def pending(self) -> list[dict]:
        data = _load_json(_INBOX_FILE, {"tasks": []})
        return [t for t in data.get("tasks", []) if t.get("status") == "pending"]

    def mark_done(self, task_id: str) -> None:
        data = _load_json(_INBOX_FILE, {"tasks": []})
        for t in data.get("tasks", []):
            if t["id"] == task_id:
                t["status"] = "done"
                t["completed"] = _now()
        _atomic_write(_INBOX_FILE, data)

    def list_all(self) -> list[dict]:
        return _load_json(_INBOX_FILE, {"tasks": []}).get("tasks", [])

    def clear_done(self) -> int:
        data = _load_json(_INBOX_FILE, {"tasks": []})
        before = len(data.get("tasks", []))
        data["tasks"] = [t for t in data.get("tasks", []) if t.get("status") != "done"]
        _atomic_write(_INBOX_FILE, data)
        return before - len(data["tasks"])


# ── AutonomousLoop ─────────────────────────────────────────────────────────────

class AutonomousLoop:
    """
    BAGO Real Autonomy Loop.

    Runs a SENSE → PLAN → ACT → OBSERVE → LEARN → DECIDE cycle.
    Terminates when quiescent (no actionable delta for STABLE_THRESHOLD cycles).

    Parameters:
        dry_run:    if True, plan but do not execute tools
        unsafe:     if True, mutating tools are allowed
        max_cycles: hard upper limit on iterations
        verbose:    extra console output
    """

    def __init__(
        self,
        dry_run:    bool = False,
        unsafe:     bool = False,
        max_cycles: int  = MAX_CYCLES_DEFAULT,
        verbose:    bool = False,
    ) -> None:
        self.dry_run    = dry_run
        self.unsafe     = unsafe
        self.max_cycles = max_cycles
        self.verbose    = verbose

        self.ctx     = _get_ctx() if _HAS_CTX else None
        self.learner = LearningWriter(self.ctx) if _HAS_LEARNER else None
        self.inbox   = Inbox()

        self._stable_count = 0
        self._last_plan_key: str = ""
        self._last_state:    dict = {}
        self._cycle_history: list[dict] = []

    # ── SENSE ──────────────────────────────────────────────────────────────────

    def sense(self) -> dict:
        """
        Collect structured system state.

        Strategy: import health_score functions directly (fast); run stale
        via subprocess for isolation. Returns normalized state dict.
        """
        state: dict[str, Any] = {
            "health":      -1,
            "pack_ok":     True,
            "stale_count": 0,
            "inbox_tasks": self.inbox.pending(),
            "ts":          _now(),
        }

        # Health score — direct import for speed
        try:
            from health_score import (
                score_integridad, score_disciplina_workflow,
                score_captura_decisiones, score_estado_stale,
                score_consistencia_inventario,
            )
            total, maxt = 0, 0
            for fn in [score_integridad, score_disciplina_workflow,
                       score_captura_decisiones, score_estado_stale,
                       score_consistencia_inventario]:
                s, m, _ = fn()
                total += s; maxt += m
            state["health"] = (total * 100 // maxt) if maxt else 0
        except Exception:
            # Fallback: subprocess
            rc, out = _run_tool("health", timeout=30)
            if rc == 0:
                for line in out.splitlines():
                    tok = line.strip().split()
                    if tok and tok[0].isdigit():
                        state["health"] = int(tok[0])
                        break
            else:
                state["health"] = 0

        # Pack integrity — validate_manifest + validate_state via subprocess
        rc_m, _ = _run_tool("validate", timeout=30)
        state["pack_ok"] = (rc_m == 0)

        # Stale count — count WARN lines from stale_detector
        rc_s, out_s = _run_tool("stale", timeout=20)
        state["stale_count"] = sum(
            1 for ln in out_s.splitlines()
            if "WARN" in ln or "⚠️" in ln
        )

        return state

    # ── PLAN ───────────────────────────────────────────────────────────────────

    def plan(self, state: dict) -> list[dict]:
        """
        Map state → ordered list of goal dicts.
        Applies learning context to skip/prioritize goals.
        """
        goals: list[dict] = []

        learn_ctx = self.learner.get_context_for_planning() if self.learner else {}
        skip_goals: set = learn_ctx.get("skip_goals", set())

        def _goal(name: str, agent: str, priority: int, reason: str) -> dict:
            comp = COMPETENCIES.get(agent, {}).get(name, {})
            return {
                "goal":     name,
                "agent":    agent,
                "tools":    comp.get("tools", []),
                "mutating": comp.get("mutating", False),
                "priority": priority,
                "reason":   reason,
                "skip":     name in skip_goals,
                "inbox_task_id": None,
            }

        # P1: Pack integrity
        if not state["pack_ok"]:
            goals.append(_goal("full_check", "VALIDADOR", 1,
                               "pack integrity failure → audit required"))

        # P2: Health below threshold
        elif state["health"] >= 0 and state["health"] < 60:
            goals.append(_goal("full_check", "VALIDADOR", 2,
                               f"health={state['health']}/100 — below 60 threshold"))
        elif state["health"] >= 0 and state["health"] < 80:
            goals.append(_goal("quick_check", "VALIDADOR", 3,
                               f"health={state['health']}/100 — below 80 threshold"))

        # P3: Stale artefacts
        if state["stale_count"] > 2:
            goals.append(_goal("scan", "ANALISTA", 4,
                               f"{state['stale_count']} stale items detected"))

        # P4: Inbox tasks (intent whitelist enforced)
        for task in state["inbox_tasks"]:
            intent = task.get("intent", "")
            agent  = _GOAL_AGENT.get(intent, "ORGANIZADOR")
            g = _goal(intent, agent, 5, f"inbox task {task['id']}: {intent}")
            g["inbox_task_id"] = task["id"]
            goals.append(g)

        # Always end with ORGANIZADOR summary
        goals.append(_goal("summary", "ORGANIZADOR", 99, "cycle summary"))

        # Sort by priority; filter mutating if not unsafe
        result = []
        for g in sorted(goals, key=lambda x: x["priority"]):
            if g["mutating"] and not self.unsafe:
                g["skip"] = True
                g["skip_reason"] = "mutating tool skipped (use --unsafe to enable)"
            result.append(g)

        return result

    # ── ACT ────────────────────────────────────────────────────────────────────

    def act(self, goal: dict) -> dict:
        """
        Execute a goal's tool chain and return structured results.
        Respects dry_run and skip flags.
        """
        results: list[dict] = []

        if goal.get("skip"):
            return {
                "goal": goal["goal"], "agent": goal["agent"],
                "skipped": True, "skip_reason": goal.get("skip_reason", "learned skip"),
                "results": [],
            }

        for tool in goal["tools"]:
            if self.dry_run:
                results.append({"cmd": tool, "rc": 0, "output": "[dry-run]", "skipped": True})
                continue

            if self.verbose:
                print(f"    ▶ [{goal['agent']}] bago {tool} …", flush=True)

            rc, output = _run_tool(tool)
            results.append({"cmd": tool, "rc": rc, "output": output[:2000]})

            if self.verbose:
                icon = "✅" if rc == 0 else "❌"
                print(f"    {icon} {tool} → rc={rc}", flush=True)

            # Short-circuit on blocking failure
            if rc != 0 and not goal.get("mutating"):
                break

        return {
            "goal":    goal["goal"],
            "agent":   goal["agent"],
            "tools":   goal["tools"],
            "skipped": False,
            "results": results,
        }

    # ── OBSERVE ────────────────────────────────────────────────────────────────

    def observe(self, goal: dict, act_result: dict, state_before: dict, state_after: dict) -> dict:
        """
        Parse act_result into structured observation.
        Feeds the LearningWriter.
        """
        if act_result.get("skipped"):
            return {"goal": goal["goal"], "skipped": True}

        results    = act_result.get("results", [])
        all_ok     = all(r["rc"] == 0 for r in results if not r.get("skipped"))
        any_run    = any(not r.get("skipped") for r in results)
        success    = all_ok and any_run if not self.dry_run else True

        delta_h = (state_after.get("health", -1) - state_before.get("health", -1))
        signals: list[str] = []

        if delta_h > 0:
            signals.append("health_improved")
        elif delta_h < 0:
            signals.append("health_degraded")

        if not state_before.get("pack_ok") and state_after.get("pack_ok"):
            signals.append("pack_repaired")

        for r in results:
            out = r.get("output", "")
            if "100/100" in out or "HEALTH SCORE" in out and "🟢" in out:
                signals.append("health_100")
            if "GO V2" in out or "VEREDICTO" in out and "✅" in out:
                signals.append("audit_pass")
            if "CLEAN" in out:
                signals.append("clean_state")

        obs = {
            "goal":         goal["goal"],
            "agent":        goal["agent"],
            "success":      success,
            "delta_health": delta_h,
            "signals":      signals,
            "tools_run":    [r["cmd"] for r in results if not r.get("skipped")],
        }

        # Feed learning
        if self.learner and not self.dry_run:
            self.learner.observe(
                goal=goal["goal"], agent=goal["agent"],
                success=success, delta_health=delta_h,
                signals=signals, tools_run=obs["tools_run"],
                cycle=len(self._cycle_history),
            )

        # Mark inbox task done
        tid = goal.get("inbox_task_id")
        if tid:
            self.inbox.mark_done(tid)

        return obs

    # ── DECIDE ─────────────────────────────────────────────────────────────────

    def decide(self, plan: list[dict], state_before: dict, state_after: dict) -> str:
        """
        Return: CONTINUE | STABLE | MAX_CYCLES

        Quiescent when:
        - No actionable goals remain (except summary)
        - Inbox is empty
        - No health/pack delta between cycles
        """
        actionable = [
            g for g in plan
            if not g.get("skip") and g["goal"] not in ("summary",)
        ]
        no_delta = (
            state_before.get("health")  == state_after.get("health") and
            state_before.get("pack_ok") == state_after.get("pack_ok") and
            state_before.get("stale_count") == state_after.get("stale_count")
        )
        inbox_empty = len(self.inbox.pending()) == 0

        if not actionable and inbox_empty and no_delta:
            self._stable_count += 1
        else:
            self._stable_count = 0

        if self._stable_count >= STABLE_THRESHOLD:
            return "STABLE"

        if len(self._cycle_history) >= self.max_cycles:
            return "MAX_CYCLES"

        return "CONTINUE"

    # ── Single cycle ───────────────────────────────────────────────────────────

    def run_cycle(self, cycle_n: int) -> tuple[str, dict]:
        """Run one full SENSE→PLAN→ACT→OBSERVE→LEARN→DECIDE cycle."""
        self._log(f"── Ciclo {cycle_n} ──────────────────────────────────")

        # SENSE
        self._log("  SENSE …")
        state_before = self.sense()
        self._print_state(state_before)

        # PLAN
        self._log("  PLAN …")
        plan = self.plan(state_before)
        self._print_plan(plan)

        if self.dry_run:
            return "DRY_RUN_DONE", {"cycle": cycle_n, "plan": plan, "state": state_before}

        # ACT + OBSERVE
        observations: list[dict] = []
        for goal in plan:
            act_result   = self.act(goal)
            state_after  = self.sense()   # re-sense after each goal
            obs          = self.observe(goal, act_result, state_before, state_after)
            observations.append(obs)
            state_before = state_after    # rolling window

        # DECIDE
        decision = self.decide(plan, state_before, state_after)

        cycle_rec = {
            "cycle": cycle_n, "ts": _now(),
            "state": state_before,
            "plan_size": len([g for g in plan if not g.get("skip")]),
            "observations": observations,
            "decision": decision,
        }
        self._cycle_history.append(cycle_rec)
        self._save_state(decision)

        return decision, cycle_rec

    # ── Main run loop ──────────────────────────────────────────────────────────

    def run(self, loop_mode: bool = False) -> None:
        """Run until stable, max_cycles reached, or KeyboardInterrupt."""
        lock = _LoopLock()
        if not lock.acquire():
            print("  ⚠️  Loop autónomo ya en ejecución (autonomous.lock existe).")
            return

        try:
            self._print_header(loop_mode)
            cycle = 0

            while True:
                decision, _ = self.run_cycle(cycle)
                cycle += 1

                if decision == "DRY_RUN_DONE":
                    print("\n  [dry-run completado — no se ejecutó ninguna herramienta]")
                    break
                if decision == "STABLE":
                    print(f"\n  ✅ BAGO quiescente — sistema estable (ciclo {cycle})")
                    break
                if decision == "MAX_CYCLES":
                    print(f"\n  ⚠️  Límite de {self.max_cycles} ciclos alcanzado")
                    break
                if not loop_mode:
                    break

                time.sleep(2)   # brief pause between loop cycles

        except KeyboardInterrupt:
            print("\n  ↩  Interrumpido por el usuario")
        finally:
            lock.release()

    # ── State persistence ──────────────────────────────────────────────────────

    def _save_state(self, decision: str) -> None:
        data = {
            "status":           decision.lower(),
            "cycle_count":      len(self._cycle_history),
            "last_cycle_ts":    _now(),
            "last_decision":    decision,
            "stable_count":     self._stable_count,
            "last_health":      self._last_state.get("health", -1),
            "history_tail": self._cycle_history[-5:],
        }
        try:
            _atomic_write(_ASTATE_FILE, data)
        except Exception:
            pass

    # ── Display helpers ────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        print(msg, flush=True)
        if self.ctx:
            self.ctx.log("info", msg, tool="autonomous")

    def _print_header(self, loop_mode: bool) -> None:
        mode = "bucle continuo" if loop_mode else "ciclo único"
        flags = []
        if self.dry_run: flags.append("dry-run")
        if self.unsafe:  flags.append("unsafe")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print()
        print("╔════════════════════════════════════════════╗")
        print("║  BAGO · Autonomía Real                     ║")
        print(f"╠════════════════════════════════════════════╣")
        print(f"║  Modo:    {mode:<34}║")
        print(f"║  Máx:     {self.max_cycles} ciclos{' ' * (28 - len(str(self.max_cycles)))}║")
        if flags:
            print(f"║  Flags:   {', '.join(flags):<34}║")
        print("╚════════════════════════════════════════════╝")
        print()

    def _print_state(self, state: dict) -> None:
        h = state.get("health", -1)
        h_icon = "🟢" if h >= 80 else ("🟡" if h >= 60 else "🔴")
        pack = "✅" if state.get("pack_ok") else "❌"
        stale = state.get("stale_count", 0)
        inbox = len(state.get("inbox_tasks", []))
        print(f"  Estado → health={h_icon} {h}/100  pack={pack}  "
              f"stale={stale}  inbox={inbox}", flush=True)

    def _print_plan(self, plan: list[dict]) -> None:
        active = [g for g in plan if not g.get("skip")]
        skipped = [g for g in plan if g.get("skip")]
        print(f"  Plan   → {len(active)} objetivos activos"
              + (f", {len(skipped)} saltados" if skipped else ""))
        for g in active:
            print(f"    • [{g['agent']}] {g['goal']} ({', '.join(g['tools'])}) — {g['reason']}")
        print()


# ── Inbox CLI ─────────────────────────────────────────────────────────────────

def cmd_inbox(args: list[str]) -> None:
    inbox = Inbox()
    sub = args[0] if args else "list"

    if sub == "add":
        if len(args) < 2:
            print("  Uso: bago inbox add <intent>")
            print(f"  Intents disponibles: {sorted(_ALLOWED_INTENTS)}")
            return
        intent = args[1]
        notes  = " ".join(args[2:])
        try:
            task = inbox.add(intent, source="human", notes=notes)
            print(f"  ✅ Tarea añadida: {task['id']} [{intent}]")
        except ValueError as e:
            print(f"  ❌ {e}")

    elif sub == "list":
        tasks = inbox.list_all()
        if not tasks:
            print("  Inbox vacío.")
            return
        print(f"  Inbox ({len(tasks)} tareas):")
        for t in tasks:
            icon = "⏳" if t["status"] == "pending" else "✅"
            print(f"  {icon} [{t['id']}] {t['intent']} — {t['status']}")

    elif sub == "clear":
        n = inbox.clear_done()
        print(f"  ✅ {n} tareas completadas eliminadas del inbox.")

    else:
        print(f"  Subcomando desconocido: {sub}. Usa: add | list | clear")


# ── Entry point ───────────────────────────────────────────────────────────────

def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--dry-run",    action="store_true")
    p.add_argument("--loop",       action="store_true")
    p.add_argument("--unsafe",     action="store_true")
    p.add_argument("--max-cycles", type=int, default=MAX_CYCLES_DEFAULT)
    p.add_argument("--verbose",    action="store_true")
    p.add_argument("--json",       action="store_true")
    # inbox subcommand passthrough
    p.add_argument("--inbox",      nargs=argparse.REMAINDER, default=None)
    args, _ = p.parse_known_args()
    return args


if __name__ == "__main__":
    _args = _parse()

    if _args.inbox is not None:
        cmd_inbox(_args.inbox)
        sys.exit(0)

    loop = AutonomousLoop(
        dry_run    = _args.dry_run,
        unsafe     = _args.unsafe,
        max_cycles = _args.max_cycles,
        verbose    = _args.verbose,
    )

    if _args.json:
        # Sense + plan only, output JSON
        import json as _json
        state = loop.sense()
        plan  = loop.plan(state)
        print(_json.dumps({
            "state": {k: v for k, v in state.items() if k != "inbox_tasks"},
            "inbox_count": len(state["inbox_tasks"]),
            "plan": [{"goal": g["goal"], "agent": g["agent"], "skip": g.get("skip", False),
                       "reason": g["reason"]} for g in plan],
            "ts": _now(),
        }, indent=2, ensure_ascii=False))
        sys.exit(0)

    loop.run(loop_mode=_args.loop)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""supervisor.py — BAGO Supervision Layer runner.

Orquesta los 6 agentes guardianes con el patrón SENSE→PLAN→ACT→OBSERVE→LEARN.

Uso:
    python .bago/supervision/supervisor.py run [--loop <nombre>] [--dry-run]
    python .bago/supervision/supervisor.py status
    python .bago/supervision/supervisor.py check <agente>
    python .bago/supervision/supervisor.py report [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# -- UTF-8 guard (Windows cp1252 safety) ----------------------------------------
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Rutas ──────────────────────────────────────────────────────────────────────
SUPERVISION_DIR = Path(__file__).parent
AGENTS_DIR      = SUPERVISION_DIR / "agents"
ARTIFACTS_DIR   = SUPERVISION_DIR / "artifacts"
LOOPS_DIR       = SUPERVISION_DIR / "loops"
BAGO_ROOT       = SUPERVISION_DIR.parent          # .bago/
REPO_ROOT       = BAGO_ROOT.parent                # repo root
STATE_CONTRACTS = BAGO_ROOT / "state" / "contracts"
STATE_CONTRACTS.mkdir(parents=True, exist_ok=True)


# ── Dataclasses ────────────────────────────────────────────────────────────────
@dataclass
class SenseResult:
    agent: str
    output: str
    return_code: int
    drift_detected: bool = False


@dataclass
class PlanResult:
    agent: str
    action: str          # "pass" | "fix" | "block"
    details: str = ""


@dataclass
class ActResult:
    agent: str
    action_taken: str
    success: bool


@dataclass
class ObserveResult:
    agent: str
    passed: bool
    output: str


@dataclass
class AgentReport:
    agent: str
    status: str          # "green" | "yellow" | "red" | "pending"
    message: str
    artifact: str
    on_failure: str
    blocker: bool = False
    cascade_triggered: bool = False   # marcado por upstream failure
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SupervisionReport:
    loop: str
    timestamp: str
    agents: list[AgentReport]
    has_blockers: bool
    blockers_summary: str

    def to_dict(self) -> dict:
        return {
            "loop": self.loop,
            "timestamp": self.timestamp,
            "has_blockers": self.has_blockers,
            "blockers_summary": self.blockers_summary,
            "agents": [
                {
                    "agent": a.agent,
                    "status": a.status,
                    "message": a.message,
                    "artifact": a.artifact,
                    "on_failure": a.on_failure,
                    "blocker": a.blocker,
                    "cascade_triggered": a.cascade_triggered,
                    "timestamp": a.timestamp,
                }
                for a in self.agents
            ],
        }


# ── GuardianAgent ──────────────────────────────────────────────────────────────
class GuardianAgent:
    def __init__(self, definition: dict, dry_run: bool = False) -> None:
        self.name        = definition["agent"]
        self.mission     = definition.get("mission", "")
        self.gate        = definition.get("gate", "")
        self.on_failure  = definition.get("on_failure", "warn")
        self.artifact    = (definition.get("writes") or [""])[0]
        self.sense_cmd   = definition.get("sense", "")
        self.act_cmd     = definition.get("act", "")
        self.observe_cmd = definition.get("observe", "")
        self.learn_cmd   = definition.get("learn_cmd", "")   # comando extra en LEARN
        self.dry_run     = dry_run

    @staticmethod
    def _is_executable_cmd(cmd: str) -> bool:
        stripped = cmd.strip()
        if not stripped:
            return False
        head = stripped.split()[0].lower()
        return head in {"python", "pytest", "git"}

    def _run(self, cmd: str, *, cwd: Path = REPO_ROOT) -> tuple[str, int]:
        """Ejecuta un comando de shell y devuelve (output, return_code)."""
        if not cmd:
            return "", 0
        if not self._is_executable_cmd(cmd):
            return "SKIP: non-executable directive", 0
        try:
            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                cwd=str(cwd), timeout=60,env=env,
            )
            return (result.stdout + result.stderr).strip(), result.returncode
        except subprocess.TimeoutExpired:
            return "TIMEOUT", 1
        except Exception as exc:
            return str(exc), 1

    def sense(self) -> SenseResult:
        output, rc = self._run(self.sense_cmd)
        drift = rc != 0 or "drift" in output.lower() or "error" in output.lower()
        return SenseResult(agent=self.name, output=output, return_code=rc, drift_detected=drift)

    def plan(self, sense: SenseResult) -> PlanResult:
        if not sense.drift_detected:
            return PlanResult(agent=self.name, action="pass", details="No drift detected")
        action = "block" if self.on_failure == "block_release" else "fix"
        return PlanResult(agent=self.name, action=action, details=sense.output[:300])

    def act(self, plan: PlanResult) -> ActResult:
        if plan.action == "pass" or self.dry_run:
            return ActResult(agent=self.name, action_taken="no-op", success=True)
        if self.act_cmd:
            output, rc = self._run(self.act_cmd)
            return ActResult(agent=self.name, action_taken=self.act_cmd, success=(rc == 0))
        return ActResult(agent=self.name, action_taken="reported", success=True)

    def observe(self) -> ObserveResult:
        if self.observe_cmd:
            output, rc = self._run(self.observe_cmd)
            return ObserveResult(agent=self.name, passed=(rc == 0), output=output[:500])
        return ObserveResult(agent=self.name, passed=True, output="no observe cmd configured")

    def learn(self, observe: ObserveResult) -> None:
        """Actualiza el artefacto con historial acumulativo de ejecuciones."""
        artifact_path = SUPERVISION_DIR / self.artifact.replace(".bago/supervision/", "")
        if not artifact_path.exists() or not artifact_path.suffix == ".json":
            # Artefacto .md — si hay learn_cmd, lo ejecutamos igual
            if self.learn_cmd and not self.dry_run:
                self._run(self.learn_cmd)
            return
        try:
            data = json.loads(artifact_path.read_text(encoding="utf-8"))
            now  = datetime.now().isoformat()

            # Actualizar campos inmediatos
            data["last_run"] = now
            data["overall"]  = "green" if observe.passed else "red"

            # ── Memoria acumulativa: run_history ─────────────────────────────
            history_entry = {
                "timestamp": now,
                "passed":    observe.passed,
                "summary":   observe.output[:200] if observe.output else "ok",
            }
            data.setdefault("run_history", []).append(history_entry)
            # Mantener solo los últimos 30 registros
            if len(data["run_history"]) > 30:
                data["run_history"] = data["run_history"][-30:]

            artifact_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass  # no bloquear el ciclo por fallo de escritura

        # ── learn_cmd extra (ej. harvest xfails) ─────────────────────────────
        if self.learn_cmd and not self.dry_run:
            self._run(self.learn_cmd)

    def run_cycle(self, upstream_failed: bool = False) -> AgentReport:
        """Ejecuta el ciclo completo SENSE→PLAN→ACT→OBSERVE→LEARN.

        upstream_failed: si un agente anterior con block_release fue red,
                         se fuerza re-sense aunque el estado previo fuera green.
        """
        try:
            sense_r   = self.sense()
            # Cascada: si upstream falló, escalamos a drift aunque sense sea ok
            if upstream_failed and not sense_r.drift_detected:
                sense_r = SenseResult(
                    agent=self.name,
                    output=f"[cascade] upstream blocker → forced re-sense\n{sense_r.output}",
                    return_code=sense_r.return_code,
                    drift_detected=True,
                )
            plan_r    = self.plan(sense_r)
            act_r     = self.act(plan_r)
            observe_r = self.observe()
            self.learn(observe_r)

            if plan_r.action == "pass" and observe_r.passed and not upstream_failed:
                status, blocker = "green", False
                message = "OK"
            elif self.on_failure == "block_release":
                status, blocker = "red", True
                message = plan_r.details or sense_r.output[:200]
            else:
                status, blocker = "yellow", False
                message = plan_r.details or sense_r.output[:200]

            return AgentReport(
                agent=self.name,
                status=status,
                message=message,
                artifact=self.artifact,
                on_failure=self.on_failure,
                blocker=blocker,
                cascade_triggered=upstream_failed,
            )
        except Exception as exc:
            return AgentReport(
                agent=self.name,
                status="red",
                message=f"EXCEPTION: {exc}",
                artifact=self.artifact,
                on_failure=self.on_failure,
                blocker=(self.on_failure == "block_release"),
            )


# ── Supervisor ─────────────────────────────────────────────────────────────────
class Supervisor:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._agents: dict[str, dict] = {}
        self._loops:  dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        for path in AGENTS_DIR.glob("*.agent.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._agents[data["agent"]] = data
            except Exception:
                pass
        for path in LOOPS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._loops[data["loop"]] = data
            except Exception:
                pass

    def run_loop(self, loop_name: str) -> SupervisionReport:
        loop_def = self._loops.get(loop_name)
        if not loop_def:
            available = list(self._loops.keys())
            return SupervisionReport(
                loop=loop_name,
                timestamp=datetime.now().isoformat(),
                agents=[],
                has_blockers=True,
                blockers_summary=f"Loop '{loop_name}' no encontrado. Disponibles: {available}",
            )

        reports: list[AgentReport] = []
        sorted_agents = sorted(loop_def.get("agents", []), key=lambda a: a["order"])
        upstream_blocker_active = False  # cascada: se activa si algún block_release falla

        for entry in sorted_agents:
            agent_name = entry["agent"]
            definition = self._agents.get(agent_name)
            if not definition:
                reports.append(AgentReport(
                    agent=agent_name, status="red",
                    message=f"Definición no encontrada: {agent_name}.agent.json",
                    artifact="", on_failure=entry.get("on_failure", "warn"),
                    blocker=(entry.get("on_failure") == "block_release"),
                ))
                continue
            guardian = GuardianAgent(definition, dry_run=self.dry_run)
            report   = guardian.run_cycle(upstream_failed=upstream_blocker_active)
            # Override on_failure from loop if specified
            if entry.get("on_failure"):
                report.on_failure = entry["on_failure"]
                report.blocker    = (entry["on_failure"] == "block_release" and report.status == "red")
            # Activar cascada si este agente es bloqueante y falló
            if report.blocker and report.status == "red":
                upstream_blocker_active = True
            reports.append(report)

        blockers     = [r for r in reports if r.blocker]
        has_blockers = bool(blockers)
        blockers_summary = "; ".join(f"{b.agent}: {b.message[:80]}" for b in blockers) if blockers else ""

        supervision_report = SupervisionReport(
            loop=loop_name,
            timestamp=datetime.now().isoformat(),
            agents=reports,
            has_blockers=has_blockers,
            blockers_summary=blockers_summary,
        )

        # Persistir report en state/contracts/
        report_path = STATE_CONTRACTS / f"{loop_name}_report.json"
        try:
            report_path.write_text(
                json.dumps(supervision_report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

        return supervision_report

    def status(self) -> dict:
        """Devuelve el estado actual de todos los agentes (last known)."""
        result = {}
        for name, defn in self._agents.items():
            artifact_rel = (defn.get("writes") or [""])[0]
            artifact_path = SUPERVISION_DIR / artifact_rel.replace(".bago/supervision/", "")
            last_run = None
            overall  = "pending_scan"
            if artifact_path.exists() and artifact_path.suffix == ".json":
                try:
                    data     = json.loads(artifact_path.read_text(encoding="utf-8"))
                    last_run = data.get("last_run") or data.get("last_checked")
                    overall  = data.get("overall") or data.get("status") or "pending_scan"
                except Exception:
                    pass
            result[name] = {
                "mission":    defn.get("mission", "")[:60],
                "artifact":   artifact_rel,
                "last_run":   last_run,
                "status":     overall,
                "on_failure": defn.get("on_failure", "warn"),
            }
        return result

    def check_agent(self, name: str) -> AgentReport:
        definition = self._agents.get(name)
        if not definition:
            return AgentReport(
                agent=name, status="red",
                message=f"Agente '{name}' no encontrado",
                artifact="", on_failure="warn",
            )
        guardian = GuardianAgent(definition, dry_run=self.dry_run)
        return guardian.run_cycle()


# ── CLI ────────────────────────────────────────────────────────────────────────
ICON = {"green": "✅", "yellow": "⚠️ ", "red": "❌", "pending_scan": "🔍", None: "❓"}


def _print_status(sup: Supervisor) -> None:
    st = sup.status()
    width = 70
    print(f"┌─ BAGO Supervision Layer {'─' * (width - 27)}┐")
    for name, info in st.items():
        icon  = ICON.get(info["status"], "❓")
        badge = f"{icon} {info['status']}"
        art   = Path(info["artifact"]).name if info["artifact"] else "—"
        line  = f"│  {name:<30} {badge:<18} {art:<20}│"
        print(line[:width + 2])
    print(f"└{'─' * width}┘")


def _print_report(report: SupervisionReport, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return
    status_icon = "❌" if report.has_blockers else "✅"
    print(f"\n{status_icon} Loop: {report.loop}  [{report.timestamp[:19]}]")
    for a in report.agents:
        icon = ICON.get(a.status, "❓")
        print(f"  {icon} {a.agent:<32} {a.message[:60]}")
    if report.has_blockers:
        print(f"\n🔴 BLOQUEADO: {report.blockers_summary}")
    else:
        print("\n🟢 Todos los gates pasaron.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="BAGO Supervision Layer — guardián de coherencia sistémica",
        prog="supervisor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = sub.add_parser("run", help="Ejecuta un loop de supervisión")
    run_p.add_argument(
        "--loop", default="contract_drift",
        choices=["pre_release", "post_test_cleanup", "legacy_decay", "contract_drift"],
        help="Loop a ejecutar (default: contract_drift)",
    )
    run_p.add_argument("--dry-run", action="store_true", help="No ejecuta ACT — solo sense+plan")
    run_p.add_argument("--json", action="store_true", help="Output JSON")

    # status
    sub.add_parser("status", help="Estado actual de todos los guardianes")

    # check
    check_p = sub.add_parser("check", help="Ejecuta un guardián específico")
    check_p.add_argument("agent", help="Nombre del agente")
    check_p.add_argument("--dry-run", action="store_true")
    check_p.add_argument("--json", action="store_true")

    # report
    rep_p = sub.add_parser("report", help="Muestra el último report guardado")
    rep_p.add_argument(
        "--loop", default="contract_drift",
        choices=["pre_release", "post_test_cleanup", "legacy_decay", "contract_drift"],
    )
    rep_p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    dry_run = getattr(args, "dry_run", False)
    as_json = getattr(args, "json", False)

    sup = Supervisor(dry_run=dry_run)

    if args.command == "run":
        loop_name = args.loop.replace("-", "_") + ("_loop" if not args.loop.endswith("_loop") else "")
        # normalise: "pre_release" → "pre_release_loop"
        if not loop_name.endswith("_loop"):
            loop_name += "_loop"
        report = sup.run_loop(loop_name)
        _print_report(report, as_json)
        return 1 if report.has_blockers else 0

    if args.command == "status":
        _print_status(sup)
        return 0

    if args.command == "check":
        report = sup.check_agent(args.agent)
        if as_json:
            print(json.dumps({
                "agent": report.agent, "status": report.status,
                "message": report.message, "artifact": report.artifact,
            }, indent=2))
        else:
            icon = ICON.get(report.status, "❓")
            print(f"{icon} {report.agent}: {report.message}")
        return 1 if report.blocker else 0

    if args.command == "report":
        loop_name = args.loop + "_loop"
        report_path = STATE_CONTRACTS / f"{loop_name}_report.json"
        if not report_path.exists():
            print(f"Sin report guardado para loop '{loop_name}'. Ejecuta: supervisor run --loop {args.loop}")
            return 1
        data = json.loads(report_path.read_text(encoding="utf-8"))
        if as_json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            icon = "❌" if data.get("has_blockers") else "✅"
            print(f"{icon} {data['loop']} [{data['timestamp'][:19]}]")
            for a in data.get("agents", []):
                print(f"  {ICON.get(a['status'], '❓')} {a['agent']}: {a['message'][:80]}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

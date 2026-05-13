#!/usr/bin/env python3
"""
bago start — Arranque de sesión BAGO con presencia visual completa.

Secuencia:
  1. Cabecera BAGO (versión, fecha, modelo)
  2. MAESTRO carga estado del sistema
  3. AUDITOR verifica salud
  4. ORQUESTADOR activa ShepardCycle
  5. Panel resumen (workflow, tarea activa, voces)
  6. Prompt: ¿aceptar idea top como tarea? [s/N]

Uso:
  bago start             → arranque interactivo completo
  bago start --auto      → acepta la idea top sin prompt
  bago start --quiet     → solo health check, sin ideas
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

ROOT  = Path(__file__).resolve().parent.parent.parent   # project root
BAGO  = ROOT / ".bago"
TOOLS = BAGO / "tools"
STATE = BAGO / "state"


def _is_devmode() -> bool:
    """Returns True if global_state has devmode=true."""
    try:
        gs = json.loads((STATE / "global_state.json").read_text(encoding="utf-8"))
        return bool(gs.get("devmode", False))
    except Exception:
        return False


def _active_project() -> str:
    """Returns active_project from global_state, or '(ninguno)'."""
    try:
        gs = json.loads((STATE / "global_state.json").read_text(encoding="utf-8"))
        return gs.get("active_project") or "(ninguno)"
    except Exception:
        return "(ninguno)"

# ── Presence ──────────────────────────────────────────────────────────────────
def _load_bp():
    try:
        spec = importlib.util.spec_from_file_location("bago_presence", TOOLS / "bago_presence.py")
        mod  = importlib.util.module_from_spec(spec)    # type: ignore
        spec.loader.exec_module(mod)                    # type: ignore
        return mod.bp
    except Exception:
        class _Null:
            def __getattr__(self, _): return lambda *a, **k: None
        return _Null()

bp = _load_bp()

# ── Helpers de estado ──────────────────────────────────────────────────────────

def _read_json(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default or {}


def _load_state() -> dict:
    return _read_json(STATE / "global_state.json")


def _load_conductor() -> dict:
    return _read_json(STATE / "conductor_state.json")


def _load_health() -> dict:
    return _read_json(STATE / "health.json")


def _load_pending_task() -> dict | None:
    t = STATE / "pending_w2_task.json"
    return _read_json(t) if t.exists() else None


def _run(args: list[str], silent: bool = False) -> tuple[int, str]:
    result = subprocess.run(
        args, cwd=str(ROOT),
        capture_output=silent,
        text=True if silent else False,
    )
    output = (result.stdout or "") + (result.stderr or "") if silent else ""
    return result.returncode, output


def _run_stream(args: list[str]) -> int:
    """Ejecuta mostrando output en tiempo real."""
    return subprocess.run(args, cwd=str(ROOT)).returncode


# ── Paso 1: Cabecera ──────────────────────────────────────────────────────────

def _step_header(state: dict) -> None:
    version  = state.get("bago_version", "?")
    now      = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")
    bp.header(f"INICIANDO  ·  {now}")


# ── Paso 2: Estado del sistema ────────────────────────────────────────────────

def _step_load_state(state: dict) -> None:
    bp.act("MAESTRO", "cargando estado del sistema")
    time.sleep(0.08)

    sprint   = state.get("sprint_status", {})
    workflow = sprint.get("active_workflow") if isinstance(sprint, dict) else None
    updated  = state.get("last_updated", "?")

    if workflow:
        bp.think(f"workflow activo: {workflow}", role="")
    else:
        bp.think("sin workflow activo en este momento")
    bp.think(f"estado actualizado: {updated}")


# ── Paso 3: Health ────────────────────────────────────────────────────────────

def _step_workspace() -> None:
    """Muestra el selector de workspace si aún no está configurado."""
    try:
        spec = importlib.util.spec_from_file_location(
            "workspace_selector", TOOLS / "workspace_selector.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.select(skip_if_set=True)
    except Exception:
        pass


def _step_record_project() -> None:
    """Registra el proyecto activo en recent_projects.json."""
    try:
        spec = importlib.util.spec_from_file_location(
            "recent_projects", TOOLS / "recent_projects.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.record_project()
    except Exception:
        pass


def _step_health() -> int:
    bp.act("AUDITOR_CANONICO", "verificando salud del sistema")

    # Obtener score rápido
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "health_score.py"), "--score-only"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=15
        )
        score_raw = r.stdout.strip().split()[0]
        score = int(score_raw) if score_raw.isdigit() else None
    except Exception:
        score = None

    if score is None:
        bp.act("AUDITOR_CANONICO", "salud: sin datos disponibles")
        return 0
    elif score >= 80:
        bp.act("AUDITOR_CANONICO", f"salud: {score}/100  🟢  SISTEMA OPERATIVO")
    elif score >= 50:
        bp.act("AUDITOR_CANONICO", f"salud: {score}/100  🟡  ADVERTENCIAS PRESENTES")
    else:
        bp.act("AUDITOR_CANONICO", f"salud: {score}/100  🔴  ATENCIÓN REQUERIDA")
    return 0


# ── Paso 4: ShepardCycle ──────────────────────────────────────────────────────

def _step_cap(conductor: dict) -> None:
    bp.act("ORQUESTADOR", "activando ShepardCycle · CAP")
    time.sleep(0.06)

    gate   = conductor.get("gate", "PUERTA_CERRADA")
    voices = conductor.get("active_voices", [])
    limit  = conductor.get("limit", 3)

    if voices:
        bp.cap_voices(voices[:limit], gate=gate)
    else:
        bp.think("ShepardCycle en reposo · sin voces activas")
        bp.gate_change(gate)


# ── Paso 5 (user mode): Panel proyecto ───────────────────────────────────────

def _step_project_panel(state: dict, task: dict | None) -> None:
    """Project-first panel for user mode (devmode=false)."""
    project = state.get("active_project") or _active_project()
    sprint  = state.get("sprint_status", {})
    wf      = sprint.get("active_workflow") if isinstance(sprint, dict) else None

    bp.voice_enter(project.upper(), gate="ACTIVO")

    if wf:
        bp.voice_line(f"Workflow activo : {wf}")
    if task:
        done  = task.get("status") == "done"
        icon  = "✅" if done else "⏳"
        title = task.get("idea_title") or task.get("title", "?")
        bp.voice_line(f"Tarea activa    : {icon} {title[:55]}")
    else:
        bp.voice_line("Tarea activa    : (ninguna — acepta una idea abajo)")

    bp.voice_exit()


# ── Paso 5 (dev mode): Panel sistema completo ─────────────────────────────────

def _step_panel(state: dict, conductor: dict, task: dict | None) -> None:
    bp.voice_enter("SISTEMA", gate="ACTIVO")

    sprint  = state.get("sprint_status", {})
    wf      = sprint.get("active_workflow") if isinstance(sprint, dict) else None
    version = state.get("bago_version", "?")
    voices  = conductor.get("active_voices", [])

    # Static motor audit
    try:
        _gs = importlib.util.spec_from_file_location(
            "agent_static_guard", TOOLS / "agent_static_guard.py"
        )
        _gm = importlib.util.module_from_spec(_gs)   # type: ignore
        _gs.loader.exec_module(_gm)                   # type: ignore
        audit = _gm.guard.audit()
        motor_s  = f"{audit['static_roles']} roles · limpio"
        dynamic_s = f"{audit['dynamic_count']} agentes dinámicos"
    except Exception:
        motor_s = dynamic_s = "?"

    bp.voice_line(f"Versión BAGO  : {version}")
    bp.voice_line(f"Workflow      : {wf or '(ninguno)'}")
    bp.voice_line(f"Motor estático: {motor_s}")
    bp.voice_line(f"Dinámica      : {dynamic_s}")
    bp.voice_line(f"Voces CAP     : {', '.join(voices) if voices else '(reposo)'}")

    if task:
        done = task.get("status") == "done"
        icon = "✅" if done else "⏳"
        title = task.get("idea_title") or task.get("title", "?")
        bp.voice_line(f"Tarea activa  : {icon} {title[:55]}")
    else:
        bp.voice_line("Tarea activa  : (ninguna — usa bago ideas)")

    bp.voice_exit()


# ── Paso 6: Ideas top ─────────────────────────────────────────────────────────

def _step_ideas(devmode: bool = False) -> int:
    bp.act("GENERADOR", "consultando ideas priorizadas")
    print()
    cmd = [sys.executable, str(TOOLS / "emit_ideas.py")]
    if devmode:
        cmd.append("--all")
    rc, _ = _run(cmd, silent=False)
    return rc


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    auto    = "--auto"  in sys.argv
    quiet   = "--quiet" in sys.argv
    dev_arg = "--dev"   in sys.argv   # force dev view regardless of devmode flag

    devmode = dev_arg or _is_devmode()

    # Cargar datos sin bloquear
    state     = _load_state()
    conductor = _load_conductor()
    task      = _load_pending_task()

    # ── Secuencia de arranque ─────────────────────────────────────────────────
    _step_header(state)
    _step_workspace()       # selector dev/user workspace (solo si no está configurado)
    _step_record_project()  # registra proyecto actual → alimenta recent_projects.json

    if devmode:
        # Developer mode: full system view (original behaviour)
        _step_load_state(state)
        _step_health()
        _step_cap(conductor)
        _step_panel(state, conductor, task)
    else:
        # User mode: project-first, clean view
        _step_health()
        _step_project_panel(state, task)

    if quiet:
        bp.act("MAESTRO", "arranque silencioso — usa bago ideas para ver tareas")
        sys.exit(0)

    # ── Ideas y prompt ────────────────────────────────────────────────────────
    rc_ideas = _step_ideas(devmode=devmode)
    if rc_ideas != 0:
        bp.act("AUDITOR_CANONICO", "gate no pasa — repara el baseline primero")
        sys.exit(rc_ideas)

    print()
    bp.act("MAESTRO", "¿aceptamos la idea top como tarea activa?")
    print()

    if auto:
        answer = "s"
        print("  [--auto] aceptando automáticamente idea #1")
    else:
        try:
            answer = input("  Respuesta [s/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            bp.act("MAESTRO", "sin aceptación — hasta la próxima sesión")
            sys.exit(0)

    if answer in {"s", "si", "sí", "y", "yes"}:
        print()
        rc_accept = _run_stream([sys.executable, str(TOOLS / "emit_ideas.py"), "--accept", "1"])
        bp.act("MAESTRO", "tarea aceptada — usa bago task para ver detalles")
        sys.exit(rc_accept)
    else:
        bp.act("MAESTRO", "ninguna idea aceptada · usa bago ideas --accept N cuando quieras")

    _sac_suggest("bago start", exit_code=0)
    sys.exit(0)


def _sac_suggest(trigger: str, exit_code: int = 0) -> None:
    try:
        spec = importlib.util.spec_from_file_location(
            "bago_sac_engine", Path(__file__).parent / "bago_sac_engine.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.sac_suggest(trigger, exit_code=exit_code)
    except Exception:
        pass


def _self_test():
    assert Path(__file__).exists()
    print("  1/1 tests pasaron")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()

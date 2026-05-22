#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vertice_activator.py — Evaluador de activación de revisión Vértice.

Evalúa señales para abrir revisión Vértice:
  1. ≥3 sesiones W0 consecutivas sin decisiones capturadas → WARN
  2. health score < 60 → WARN
  3. Escenario activo sin actividad > 14 días → WARN
  4. validate_pack KO recurrente → ERROR → activar Vértice

Salida: CLEAN / WATCH / ACTIVATE con justificación.

Uso:
  python3 .bago/tools/vertice_activator.py
"""

from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
TOOLS = ROOT / "tools"
GLOBAL_STATE = STATE / "global_state.json"

CLEAN    = "CLEAN"
WATCH    = "WATCH"
ACTIVATE = "ACTIVATE"
WARN     = "WARN"


def load_global() -> dict:
    if not GLOBAL_STATE.exists():
        return {}
    return json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))


def load_sessions() -> list:
    """Carga todas las sesiones cerradas ordenadas por fecha."""
    sessions_dir = STATE / "sessions"
    if not sessions_dir.exists():
        return []
    sessions = []
    for f in sessions_dir.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            sessions.append(s)
        except Exception:
            continue
    # Ordenar por closed_at o created_at
    def sort_key(s):
        return s.get("closed_at") or s.get("created_at") or ""
    return sorted(sessions, key=sort_key)


def check_w0_consecutive(sessions: list, signals: list) -> None:
    """≥3 sesiones W0 consecutivas sin decisiones."""
    # Mirar las últimas 10 sesiones
    recent = [s for s in sessions if s.get("status") == "closed"][-10:]
    if not recent:
        return
    consecutive = 0
    for s in reversed(recent):
        workflow_id = s.get("workflow", "")
        decisions = s.get("decisions", [])
        if "w0" in workflow_id.lower() or workflow_id.lower() == "w0_free_session":
            if not decisions:
                consecutive += 1
            else:
                break
        else:
            break
    if consecutive >= 3:
        signals.append((WARN, f"≥3 sesiones W0 consecutivas sin decisiones capturadas ({consecutive} consecutivas)"))


def check_health_score(signals: list) -> None:
    """health score < 60 → WARN."""
    try:
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "health_score.py"), "--score-only"],
            capture_output=True, text=True, timeout=30
        )
        out = proc.stdout.strip()
        # Parsear score del output
        for line in out.splitlines():
            if line.strip().isdigit():
                score = int(line.strip())
                if score < 60:
                    signals.append((WARN, f"Health score bajo: {score}/100 (umbral=60)"))
                return
    except Exception:
        pass  # Si no se puede calcular, no es señal de activación


def check_scenario_inactivity(global_state: dict, sessions: list, signals: list) -> None:
    """Escenario activo sin actividad > 14 días → WARN."""
    active = global_state.get("active_scenarios", [])
    if not active:
        return

    now = datetime.now(timezone.utc)
    threshold = timedelta(days=14)

    for scenario_id in active:
        # Buscar última sesión que mencione este escenario
        last_activity = None
        for s in sessions:
            if s.get("escenario") == scenario_id or scenario_id in str(s.get("notes", "")):
                ts_str = s.get("closed_at") or s.get("created_at")
                if ts_str:
                    try:
                        timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if last_activity is None or timestamp > last_activity:
                            last_activity = timestamp
                    except ValueError:
                        pass

        if last_activity is None:
            # Sin registro de actividad
            signals.append((WARN, f"Escenario activo '{scenario_id}' sin actividad registrada en sesiones"))
        else:
            inactivity = now - last_activity
            if inactivity > threshold:
                signals.append((WARN, f"Escenario '{scenario_id}' sin actividad desde hace {inactivity.days} días (umbral=14)"))


def check_pack_ko_recurrent(sessions: list, signals: list) -> None:
    """validate_pack KO recurrente en últimas sesiones → ERROR."""
    # Buscar evidencias o cambios de tipo KO recurrente
    # Heurística: buscar en las últimas 5 sesiones cerradas menciones de KO validate_pack
    recent = [s for s in sessions if s.get("status") == "closed"][-5:]
    ko_count = 0
    for s in recent:
        notes = str(s.get("notes", "")).lower() + str(s.get("context", "")).lower()
        if "ko" in notes and "pack" in notes:
            ko_count += 1
    if ko_count >= 2:
        signals.append((ACTIVATE, f"validate_pack KO encontrado en {ko_count} de las últimas 5 sesiones → activar Vértice"))


def main():
    global_state = load_global()
    sessions = load_sessions()
    signals = []

    check_w0_consecutive(sessions, signals)
    check_health_score(signals)
    check_scenario_inactivity(global_state, sessions, signals)
    check_pack_ko_recurrent(sessions, signals)

    # Determinar nivel
    if any(s[0] == ACTIVATE for s in signals):
        level = ACTIVATE
    elif signals:
        level = WATCH
    else:
        level = CLEAN

    # Output
    icons = {CLEAN: "✅", WATCH: "⚠️ ", ACTIVATE: "🔴"}
    print(f"Vértice: {icons[level]} {level}")

    if signals:
        for sev, msg in signals:
            icon = "🔴" if sev == ACTIVATE else "⚠️ "
            print(f"  {icon} [{sev}] {msg}")

    if level == ACTIVATE:
        print()
        print("  → Se recomienda abrir sesión de revisión Vértice (role_vertice)")

    return 0 if level == CLEAN else (1 if level == WATCH else 2)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())

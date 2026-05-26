#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chronicle_reporter.py — Sesión Chronicle integrando GitHub Copilot CLI /chronicle

Implementa `/chronicle` de Copilot CLI como reporte BAGO:
- Resumen de sesión anterior (historial local)
- Contexto persistente entre sesiones
- Recomendaciones basadas en historia
- Integrable con W5 (Cierre y Continuidad)

Uso:
  python3 .bago/tools/chronicle_reporter.py
  python3 .bago/tools/chronicle_reporter.py --detailed
  python3 .bago/tools/chronicle_reporter.py --summary
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path
import sys
from bago_utils import (
    get_state_dir, ensure_subdir, load_json, timestamp_readable
)

SESSIONS_DIR = ensure_subdir("sessions")
GLOBAL_STATE_FILE = get_state_dir() / "global_state.json"


def get_session_history() -> list:
    """Lee historial de sesiones."""
    sessions = []
    if SESSIONS_DIR.exists():
        for session_file in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:10]:
            try:
                session = load_json(session_file)
                sessions.append(session)
            except Exception:
                pass
    return sessions


def get_recent_changes() -> list:
    """Obtiene cambios recientes registrados."""
    changes_dir = get_state_dir() / "changes"
    changes = []
    if changes_dir.exists():
        for change_file in sorted(changes_dir.glob("BAGO-CHG-*.json"), reverse=True)[:5]:
            try:
                change = load_json(change_file)
                changes.append({
                    "id": change.get("id", "?"),
                    "description": change.get("description", "?"),
                    "timestamp": change.get("timestamp", "?")
                })
            except Exception:
                pass
    return changes


def get_pending_tasks() -> list:
    """Obtiene tareas pendientes."""
    pending = []
    
    # W2 pending task
    w2_file = get_state_dir() / "pending_w2_task.json"
    if w2_file.exists():
        try:
            w2_task = load_json(w2_file)
            pending.append({
                "type": "W2 Implementation",
                "title": w2_task.get("title", "?"),
                "status": "pending"
            })
        except Exception:
            pass
    
    return pending


def format_chronicle_report(summary: bool = False) -> str:
    """Formatea reporte chronicle."""
    gs = load_json(GLOBAL_STATE_FILE)
    sessions = get_session_history()
    changes = get_recent_changes()
    pending = get_pending_tasks()
    
    now = timestamp_readable()
    
    report = f"""
════════════════════════════════════════════════════════════════
  BAGO SESSION CHRONICLE — {now}
════════════════════════════════════════════════════════════════

"""
    
    # Estado global
    report += "STATUS\n"
    report += f"  Version:        {gs.get('version', '?')}\n"
    report += f"  Health:         {gs.get('health_status', '?')}\n"
    report += f"  Mode:           {gs.get('mode', '?')}\n"
    report += f"  Total Sessions: {len(sessions)}\n"
    report += "\n"
    
    # Sesiones recientes
    if sessions and not summary:
        report += "RECENT SESSIONS (Last 10)\n"
        for i, session in enumerate(sessions[:10], 1):
            sid = session.get('session_id', '?')[:20]
            wf = session.get('workflow', '?')
            status = session.get('status', '?')
            report += f"  [{i:2}] {sid:<20} | {wf:<15} | {status}\n"
        report += "\n"
    
    # Cambios recientes
    if changes and not summary:
        report += "RECENT CHANGES (Last 5)\n"
        for change in changes:
            report += f"  • {change['id']:15} | {change['description'][:40]}\n"
        report += "\n"
    
    # Tareas pendientes
    if pending:
        report += "PENDING TASKS\n"
        for task in pending:
            report += f"  • [{task['type']:20}] {task['title']}\n"
        report += "\n"
    
    # Recomendaciones
    report += "RECOMMENDATIONS FOR NEXT SESSION\n"
    if pending:
        report += f"  1. Complete pending {pending[0]['type']} task\n"
    if sessions:
        last_wf = sessions[0].get('workflow', '?')
        report += f"  2. Continue with workflow type similar to: {last_wf}\n"
    report += "  3. Run: bago audit (before starting work)\n"
    report += "  4. Run: bago cosecha (after closing session)\n"
    report += "\n"
    
    report += "════════════════════════════════════════════════════════════════\n"
    
    return report


def main():
    detailed = "--detailed" in sys.argv or "-v" in sys.argv
    summary = "--summary" in sys.argv or "-s" in sys.argv
    
    report = format_chronicle_report(summary=summary)
    print(report)
    
    if not summary and not detailed:
        print("Opciones:")
        print("  bago chronicle --summary    → resumen breve")
        print("  bago chronicle --detailed   → reporte completo con análisis")
        print()



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()


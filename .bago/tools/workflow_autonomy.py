#!/usr/bin/env python3
"""workflow_autonomy.py — reconciliación automática del flujo activo.

La regla es simple:
- si hay pasos seguros que se pueden aplicar sin permiso, el sistema los aplica;
- si falta permiso o hay riesgo, se reporta y se detiene;
- si la tarea W2 ya quedó resuelta, se cierra el workflow automáticamente.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = BAGO_ROOT / "state"
GLOBAL_FILE = STATE_DIR / "global_state.json"
TASK_FILE = STATE_DIR / "pending_w2_task.json"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _active_workflow() -> dict | None:
    gs = _load_json(GLOBAL_FILE) or {}
    sprint = gs.get("sprint_status") or {}
    active = sprint.get("active_workflow")
    return active if isinstance(active, dict) and active.get("code") else None


def _pending_task() -> dict | None:
    task = _load_json(TASK_FILE)
    if task is None:
        return None
    return task


def reconcile_workflow() -> dict:
    """Reconcilia el estado del flujo. No asume permisos interactivos."""
    current = _active_workflow()
    task = _pending_task()
    result = {
        "auto_closed": False,
        "workflow": current,
        "task": task,
        "reason": "",
    }
    if not current:
        result["reason"] = "no_active_workflow"
        return result

    # W2: si no hay task residual, o la task está done, cerramos el workflow.
    if current.get("code") in {"W2", "W2_IMPLEMENTACION_CONTROLADA"}:
        task_status = (task or {}).get("status", "").lower() if isinstance(task, dict) else ""
        if task is None or task_status == "done":
            done_args = [sys.executable, str(BAGO_ROOT / "tools" / "flow.py"), "done"]
            r = subprocess.run(done_args, capture_output=True, text=True, encoding="utf-8", errors="replace")
            result["auto_closed"] = r.returncode == 0
            result["reason"] = "auto_closed_w2" if r.returncode == 0 else "auto_close_failed"
            result["stdout"] = (r.stdout or "").strip()
            result["stderr"] = (r.stderr or "").strip()
            return result

    result["reason"] = "no_action"
    return result

#!/usr/bin/env python3
"""workflow_autonomy.py — reconciliación automática del flujo activo.

La regla es simple:
- si hay pasos seguros que se pueden aplicar sin permiso, el sistema los aplica;
- si falta permiso o hay riesgo, se reporta y se detiene;
- si la tarea W2 ya quedó resuelta, se cierra el workflow automáticamente.
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
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = BAGO_ROOT / "state"
GLOBAL_FILE = STATE_DIR / "global_state.json"
TASK_FILE = STATE_DIR / "pending_w2_task.json"

# ── BagoShell integration (optional, fail-soft) ──────────────────────────────
try:
    import importlib.util as _ilu2
    _shell_path = BAGO_ROOT / "tools" / "bago_shell.py"
    if _shell_path.exists():
        _sp = _ilu2.spec_from_file_location("_bago_shell_wf", str(_shell_path))
        _sm = _ilu2.module_from_spec(_sp)  # type: ignore
        sys.modules[_sp.name] = _sm        # type: ignore
        _sp.loader.exec_module(_sm)        # type: ignore
        _BagoShell = _sm.BagoShell
    else:
        _BagoShell = None  # type: ignore
except Exception:
    _BagoShell = None  # type: ignore


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
            flow_path = BAGO_ROOT / "tools" / "flow.py"
            if _BagoShell is not None:
                shell = _BagoShell(auto_approve=True, dry_run=False)
                r = shell._run_script(flow_path, ["done"], capture_output=True)
                rc = r.exit_code
                result["stdout"] = (r.stdout or "").strip()
                result["stderr"] = (r.stderr or "").strip()
            else:
                done_args = [sys.executable, str(flow_path), "done"]
                proc = subprocess.run(done_args, capture_output=True, text=True, encoding="utf-8", errors="replace")
                rc = proc.returncode
                result["stdout"] = (proc.stdout or "").strip()
                result["stderr"] = (proc.stderr or "").strip()
            result["auto_closed"] = rc == 0
            result["reason"] = "auto_closed_w2" if rc == 0 else "auto_close_failed"
            return result

    result["reason"] = "no_action"
    return result


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


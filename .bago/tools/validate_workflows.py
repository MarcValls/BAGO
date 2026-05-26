"""Validaciones auxiliares de workflows."""

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

def check_w10_desync(sprint_status: dict) -> list[str]:
    warnings: list[str] = []
    active_wf = sprint_status.get("active_workflow")
    last = sprint_status.get("last_completed_workflow") or {}
    last_code = last.get("code") if isinstance(last, dict) else None

    if (
        active_wf is not None
        and last_code is not None
        and active_wf == last_code
    ):
        title = last.get("title", "")
        ended = last.get("ended", "")
        warnings.append(
            f"WARN-W010: active_workflow='{active_wf}' coincide con "
            f"last_completed_workflow='{last_code}' ('{title}', ended={ended}) "
            "— el flujo parece completado pero active_workflow no fue limpiado"
        )
    return warnings

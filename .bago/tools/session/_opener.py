#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""session._opener — Abre o reabre una sesión W2 pre-rellenada desde handoff."""
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

ROOT = Path(__file__).resolve().parents[3]
TASK_FILE = ROOT / ".bago" / "state" / "pending_w2_task.json"
PREFLIGHT = ROOT / ".bago" / "tools" / "session_preflight.py"
CLOSE_DIR = ROOT / ".bago" / "state"

WORKFLOW_ROLES: dict[str, str] = {
    "W2": "role_architect,role_validator",
    "W3": "role_executor,role_validator",
    "W4": "role_auditor,role_organizer",
    "W5": "role_executor,role_organizer",
    "W7": "role_architect,role_validator",
    "W9": "role_organizer,role_vertice",
}
DEFAULT_ROLES = "role_architect,role_validator"

def _load_task() -> dict | None:
    if not TASK_FILE.exists():
        return None
    try:
        return json.loads(TASK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

def _derive_roles(task: dict) -> str:
    wf = str(task.get("workflow", "")).strip().upper()
    for key, roles in WORKFLOW_ROLES.items():
        if key in wf:
            return roles
    return DEFAULT_ROLES

def _build_args(task: dict) -> dict[str, str]:
    objetivo = task.get("objetivo", "").strip()
    roles = _derive_roles(task)
    archivos = task.get("archivos_candidatos", [])
    artefactos = ",".join(archivos[:6]) if archivos else "state/sessions,state/changes,state/evidences"
    return {"objetivo": objetivo, "roles": roles, "artefactos": artefactos}

def _find_latest_close() -> Path | None:
    candidates = sorted(CLOSE_DIR.glob("session_close_*.md"), reverse=True)
    return candidates[0] if candidates else None

def _parse_close_artifact(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    info: dict = {"title": "", "files": [], "summary": ""}
    for line in text.splitlines():
        if line.startswith("## "):
            info["title"] = line[3:].strip()
        elif line.startswith("- "):
            info["files"].append(line[2:].strip())
        elif not info["summary"] and line.strip() and not line.startswith("#"):
            info["summary"] = line.strip()
    return info

def _run_preflight(objetivo: str, roles: str, artefactos: str, dry: bool) -> int:
    print()
    if dry:
        print("  [--dry] Comando que se ejecutaría:")
        print(f"  {sys.executable} {PREFLIGHT} \\")
        print(f"    --objetivo \"{objetivo}\" \\")
        print(f"    --roles \"{roles}\" \\")
        print(f"    --artefactos \"{artefactos}\"")
        print()
        return 0

    cmd = [
        sys.executable,
        str(PREFLIGHT),
        "--objetivo", objetivo,
        "--roles", roles,
        "--artefactos", artefactos,
    ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode

def _cmd_reopen(dry: bool) -> int:
    close_path = _find_latest_close()
    if close_path is None:
        print()
        print("  ℹ  No hay artefactos de cierre de sesión previos.")
        print("     Cierra una sesión primero con: bago task --done")
        print()
        return 1

    info = _parse_close_artifact(close_path)
    title = info["title"] or close_path.stem
    files = info["files"]
    summary = info["summary"]

    task = _load_task()
    if task and task.get("status") != "done":
        objetivo = task.get("objetivo", title)
        roles = _derive_roles(task)
        archivos = task.get("archivos_candidatos", files)
    else:
        objetivo = title
        roles = DEFAULT_ROLES
        archivos = files

    artefactos = ",".join(str(f) for f in archivos[:6]) if archivos else "state/sessions"

    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Reabrir desde continuidad (session_close)        │")
    print("  └──────────────────────────────────────────────────────────┘")
    print(f"  Artefacto : {close_path.name}")
    print(f"  Tarea     : {title}")
    if summary:
        print(f"  Resumen   : {summary}")
    print(f"  Objetivo  : {objetivo}")
    print(f"  Roles     : {roles}")
    print(f"  Artefactos: {artefactos}")
    print()
    return _run_preflight(objetivo, roles, artefactos, dry)

def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    dry = "--dry" in args
    reopen = "--reopen" in args

    if reopen:
        return _cmd_reopen(dry)

    task = _load_task()
    if task is None:
        print()
        print("  ℹ  No hay tarea W2 pendiente.")
        print("     Acepta una idea primero con: bago ideas --accept N")
        print()
        return 1

    if task.get("status") == "done":
        print()
        print("  ℹ  La tarea W2 está marcada como completada (done).")
        print("     Limpia con: bago task --clear")
        print("     O acepta una nueva: bago ideas --accept N")
        print()
        return 1

    payload = _build_args(task)
    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Session opener desde handoff                     │")
    print("  └──────────────────────────────────────────────────────────┘")
    print(f"  Idea      : #{task.get('idea_index', '?')} — {task.get('idea_title', '—')}")
    print(f"  Objetivo  : {payload['objetivo']}")
    print(f"  Roles     : {payload['roles']}")
    print(f"  Artefactos: {payload['artefactos']}")
    print()
    return _run_preflight(payload["objetivo"], payload["roles"], payload["artefactos"], dry)

if __name__ == "__main__":
    raise SystemExit(main())

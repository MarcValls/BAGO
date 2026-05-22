"""creation_mode.commands — Handlers para comandos internos (:build, :layer, :chat...)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import STATE, TOOLS_DIR, ROOT, C_HEADER, C_GREEN, C_RED, C_YELLOW, console
from .data import load_projects
from .git_tools import run_command


def cmd_build(project: dict, build_status: list) -> None:
    proj_path = project.get("project_path") or str(ROOT)
    console.clear()
    console.print(f"[{C_HEADER}]Build en {proj_path}[/{C_HEADER}]")
    rc, out, err = run_command([sys.executable, "-m", "build"], cwd=proj_path, timeout=120)
    build_status[0] = f"[{C_GREEN}]✓ Build OK[/{C_GREEN}]" if rc == 0 else f"[{C_RED}]✗ Build falló (rc={rc})[/{C_RED}]"
    console.print(out[-800:] if len(out) > 800 else out or "(sin salida)")
    if err:
        console.print(f"[red]{err[:400]}[/red]")
    input("\n  [Enter para volver]")


def cmd_test(project: dict, build_status: list) -> None:
    proj_path = project.get("project_path") or str(ROOT)
    console.clear()
    console.print(f"[{C_HEADER}]Test en {proj_path}[/{C_HEADER}]")
    rc, out, err = run_command([sys.executable, "-m", "pytest", "-q"], cwd=proj_path, timeout=120)
    build_status[0] = f"[{C_GREEN}]✓ Tests OK[/{C_GREEN}]" if rc == 0 else f"[{C_RED}]✗ Tests fallaron (rc={rc})[/{C_RED}]"
    console.print(out[-800:] if len(out) > 800 else out or "(sin salida)")
    if err:
        console.print(f"[red]{err[:400]}[/red]")
    input("\n  [Enter para volver]")


def cmd_lint(project: dict, build_status: list) -> None:
    proj_path = project.get("project_path") or str(ROOT)
    console.clear()
    console.print(f"[{C_HEADER}]Lint en {proj_path}[/{C_HEADER}]")
    rc, out, err = run_command([sys.executable, "-m", "flake8", "."], cwd=proj_path, timeout=120)
    build_status[0] = f"[{C_GREEN}]✓ Lint OK[/{C_GREEN}]" if rc == 0 else f"[{C_YELLOW}]⚠ Lint con advertencias (rc={rc})[/{C_YELLOW}]"
    console.print(out[-800:] if len(out) > 800 else out or "(sin salida)")
    if err:
        console.print(f"[red]{err[:400]}[/red]")
    input("\n  [Enter para volver]")


def cmd_project_select(project: dict, build_status: list) -> None:
    projects = load_projects()
    console.clear()
    if projects:
        console.print(f"[{C_HEADER}]Proyectos disponibles:[/{C_HEADER}]")
        for i, p in enumerate(projects[:10], 1):
            name = p.get("name") or Path(p.get("path", "?")).name
            active = "  [green]✓[/green]" if name == project.get("project_name") else ""
            console.print(f"  {i}. {name}{active}")
        console.print(f"\n  [grey50]Usa :project <número> para cambiar[/grey50]")
    else:
        console.print(f"[{C_YELLOW}]Sin proyectos recientes.[/{C_YELLOW}]")
    input("\n  [Enter para volver]")


def cmd_project_change(index_str: str, project: dict, build_status: list) -> None:
    projects = load_projects()
    try:
        idx = int(index_str) - 1
        if 0 <= idx < len(projects):
            proj = projects[idx]
            proj_path = proj.get("path", "")
            if proj_path:
                rc = STATE / "repo_context.json"
                rc_data = json.loads(rc.read_text(encoding="utf-8")) if rc.exists() else {}
                rc_data["project_name"] = proj.get("name") or Path(proj_path).name
                rc_data["project_path"] = proj_path
                rc.write_text(json.dumps(rc_data, indent=2, ensure_ascii=False), encoding="utf-8")
                build_status[0] = f"[{C_GREEN}]Proyecto cambiado a {rc_data['project_name']}[/{C_GREEN}]"
        else:
            build_status[0] = f"[{C_RED}]Índice fuera de rango[/{C_RED}]"
    except ValueError:
        build_status[0] = f"[{C_RED}]Número inválido[/{C_RED}]"


def cmd_ideas() -> None:
    console.clear()
    subprocess.run([sys.executable, str(TOOLS_DIR / "emit_ideas.py")], cwd=str(ROOT))
    input("\n  [Enter para volver al modo creación]")


def cmd_task() -> None:
    console.clear()
    subprocess.run([sys.executable, str(TOOLS_DIR / "show_task.py")], cwd=str(ROOT))
    input("\n  [Enter para volver al modo creación]")


def save_milestone(text: str, gs: dict) -> None:
    task_file = STATE / "pending_w2_task.json"
    if task_file.exists():
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
            milestones = task.get("milestones", [])
            milestones.append({"text": text, "timestamp": datetime.now().isoformat()})
            task["milestones"] = milestones
            task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    else:
        notes_file = STATE / "creation_notes.json"
        notes = []
        if notes_file.exists():
            try:
                notes = json.loads(notes_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        notes.append({"text": text, "timestamp": datetime.now().isoformat()})
        notes_file.write_text(json.dumps(notes[-50:], indent=2, ensure_ascii=False), encoding="utf-8")

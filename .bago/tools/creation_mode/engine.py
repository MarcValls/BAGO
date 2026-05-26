"""creation_mode.engine — Bucle principal y entrypoints."""
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

import argparse
import sys
from datetime import datetime

from .config import console, _HAS_PROMPT_TOOLKIT, PromptSession, Style, HTML, ROOT, TOOLS_DIR
from .data import (
    load_global_state, load_recent_sessions, load_agents, load_tools_count,
    load_active_task, load_project, load_issues, load_layer_config,
)
from .renderer import build_layout
from .commands import (
    cmd_build, cmd_test, cmd_lint, cmd_project_select, cmd_project_change,
    cmd_ideas, cmd_task, save_milestone,
)


def render_once(tab: str, layer: str = "", sublayer: str = "") -> None:
    gs = load_global_state()
    sessions = load_recent_sessions()
    agents = load_agents()
    tools_count = load_tools_count()
    active_task = load_active_task()
    project = load_project()
    issues = load_issues()
    layout = build_layout(
        sessions, gs, agents, tools_count, active_task,
        project, issues, tab, "", None, "", layer, sublayer,
    )
    console.print(layout)


def run_interactive(tab: str, layer: str = "", sublayer: str = "") -> int:
    gs = load_global_state()
    sessions = load_recent_sessions()
    agents = load_agents()
    tools_count = load_tools_count()
    active_task = load_active_task()
    project = load_project()
    issues = load_issues()
    last_input = ""
    preview_path = None
    build_status = [""]

    special_cmds = {
        ":q": "salir", ":quit": "salir",
        ":cambios": "tab", ":archivos": "tab", ":preview": "tab", ":issues": "tab",
        ":refresh": "refresh", ":ideas": "ideas", ":task": "task",
        ":project": "project", ":build": "build", ":test": "test", ":lint": "lint",
        ":layer": "layer", ":sub": "sub", ":all": "all", ":chat": "chat",
    }

    session = None
    if _HAS_PROMPT_TOOLKIT:
        pt_style = Style.from_dict({"prompt": "#5555ff bold", "rprompt": "#666666"})
        session = PromptSession(history=None, style=pt_style)

    while True:
        console.clear()
        layout = build_layout(
            sessions, gs, agents, tools_count, active_task,
            project, issues, tab, last_input, preview_path, build_status[0],
            layer, sublayer,
        )
        console.print(layout)
        console.print(
            f"\n  [grey50]:q salir  :cambios/:archivos/:preview/:issues  :refresh  :ideas  :task  :project  :build/:test/:lint  :layer/:sub/:all  :chat[/grey50]"
        )

        try:
            if session:
                user_input = session.prompt(
                    HTML("<ansiblue><b>  ⌘ </b></ansiblue>"),
                    rprompt=HTML("<ansiblack>modo creación</ansiblack>"),
                ).strip()
            else:
                user_input = input("  ⌘  ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[grey50]  Saliendo de modo creación.[/grey50]")
            return 0

        if not user_input:
            continue

        if user_input in (":q", ":quit"):
            console.print("\n[grey50]  Saliendo de modo creación.[/grey50]")
            return 0
        elif user_input == ":cambios":
            tab = "cambios"
        elif user_input == ":archivos":
            tab = "archivos"
        elif user_input == ":preview":
            tab = "preview"
        elif user_input.startswith(":preview "):
            tab = "preview"
            preview_path = user_input[len(":preview "):].strip()
        elif user_input == ":issues":
            tab = "issues"
        elif user_input == ":refresh":
            gs = load_global_state()
            sessions = load_recent_sessions()
            active_task = load_active_task()
            project = load_project()
            issues = load_issues()
            build_status[0] = ""
        elif user_input == ":ideas":
            cmd_ideas()
        elif user_input == ":task":
            cmd_task()
        elif user_input == ":project":
            cmd_project_select(project, build_status)
        elif user_input.startswith(":project "):
            cmd_project_change(user_input[len(":project "):].strip(), project, build_status)
        elif user_input == ":build":
            cmd_build(project, build_status)
        elif user_input == ":test":
            cmd_test(project, build_status)
        elif user_input == ":lint":
            cmd_lint(project, build_status)
        elif user_input.startswith(":layer "):
            layer = user_input[len(":layer "):].strip().lower()
            build_status[0] = f"[green]Capa cambiada a {layer}[/green]"
        elif user_input.startswith(":sub "):
            sublayer = user_input[len(":sub "):].strip().lower()
            build_status[0] = f"[green]Subcapa cambiada a {sublayer}[/green]"
        elif user_input == ":all":
            layer = ""
            sublayer = ""
            build_status[0] = f"[green]Vista unificada (todas las capas)[/green]"
        elif user_input == ":chat":
            console.print("\n[grey50]  Volviendo al chat BAGO...[/grey50]")
            return 0
        else:
            last_input = user_input
            save_milestone(user_input, gs)


def main() -> int:
    parser = argparse.ArgumentParser(description="BAGO modo creación — layout 3 paneles")
    parser.add_argument("--once", action="store_true", help="Render único")
    parser.add_argument("--tab", choices=["cambios", "archivos", "preview", "issues"], default="cambios")
    parser.add_argument("--layer", default="", help="Capa arquitectónica")
    parser.add_argument("--sublayer", default="", help="Subcapa")
    args = parser.parse_args()

    layer = args.layer
    sublayer = args.sublayer
    if not layer:
        cfg = load_layer_config()
        layer = cfg.get("layer", "")
        if not sublayer:
            sublayer = cfg.get("sublayer", "")

    if args.once:
        render_once(args.tab, layer, sublayer)
        return 0
    return run_interactive(args.tab, layer, sublayer)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""creation_mode.py — BAGO modo creación: layout 3 paneles tipo Copilot.

Layout:
  ┌──────────────────┬──────────────────────────────────┬─────────────────┐
  │    SESIONES      │          ÁREA DE TRABAJO         │ CAMBIOS ARCHIVOS│
  │                  │                                  │                 │
  │  lista sesiones  │   flujo activo + input hito      │ git diff / tree │
  │                  │                                  │                 │
  │ Personalizaciones│                                  │                 │
  │  Agentes         │                                  │                 │
  │  Habilidades     │                                  │                 │
  │  Instrucciones   │                                  │                 │
  │  Flujos          │                                  │                 │
  │  Tools           │                                  │                 │
  │  Extensiones     │                                  │                 │
  └──────────────────┴──────────────────────────────────┴─────────────────┘

Uso:
    python3 .bago/tools/creation_mode.py          # modo interactivo
    python3 .bago/tools/creation_mode.py --once   # render único, no interactivo
    python3 .bago/tools/creation_mode.py --tab cambios   # panel derecho: cambios
    python3 .bago/tools/creation_mode.py --tab archivos  # panel derecho: archivos
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Dependencias rich ─────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.rule import Rule
    from rich.align import Align
    from rich.live import Live
    from rich import box as rbox
except ImportError:
    print("ERROR: pip install rich", file=sys.stderr)
    sys.exit(1)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    _HAS_PROMPT_TOOLKIT = False

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
BAGO_ROOT  = ROOT / ".bago"
STATE      = BAGO_ROOT / "state"
TOOLS_DIR  = BAGO_ROOT / "tools"

console = Console()

# ── Paleta de colores (dark theme como VS Code) ───────────────────────────────
C_BG         = "grey11"
C_BORDER     = "grey30"
C_HEADER     = "bold white"
C_ITEM       = "grey82"
C_ITEM_DIM   = "grey50"
C_ACCENT     = "dodger_blue1"
C_GREEN      = "spring_green3"
C_YELLOW     = "yellow3"
C_INPUT_BG   = "grey15"

# ── Carga de datos ────────────────────────────────────────────────────────────

def _load_global_state() -> dict:
    try:
        return json.loads((STATE / "global_state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_recent_sessions(n: int = 8) -> list[dict]:
    """Carga sesiones recientes desde execution_history.jsonl."""
    hist_file = STATE / "execution_history.jsonl"
    sessions: list[dict] = []
    if hist_file.exists():
        try:
            lines = hist_file.read_text(encoding="utf-8").strip().splitlines()
            seen: set[str] = set()
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    key = entry.get("task", "")[:40]
                    if key and key not in seen:
                        seen.add(key)
                        sessions.append(entry)
                        if len(sessions) >= n:
                            break
                except Exception:
                    pass
        except Exception:
            pass
    return sessions


def _load_active_task() -> dict | None:
    task_file = STATE / "pending_w2_task.json"
    if task_file.exists():
        try:
            return json.loads(task_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _load_agents() -> list[str]:
    agents_file = STATE / "agents_registry.json"
    if agents_file.exists():
        try:
            data = json.loads(agents_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [a.get("id", a) if isinstance(a, dict) else str(a) for a in data[:6]]
            if isinstance(data, dict):
                return list(data.keys())[:6]
        except Exception:
            pass
    # Fallback: agentes conocidos del framework
    return ["ANALISTA", "ARQUITECTO", "GENERADOR", "ORGANIZADOR", "VALIDADOR", "CENTINELA"]


def _load_tools_count() -> int:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_tr", TOOLS_DIR / "tool_registry.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_tr"] = mod
        spec.loader.exec_module(mod)
        return len(mod.REGISTRY)
    except Exception:
        return 0


def _git_changes() -> list[tuple[str, str]]:
    """Retorna lista de (status, filepath) con cambios git."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--short"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=5
        )
        changes = []
        for line in result.stdout.strip().splitlines():
            if len(line) > 2:
                status = line[:2].strip()
                path   = line[3:].strip()
                changes.append((status, path))
        return changes[:15]
    except Exception:
        return []


def _project_files(max_items: int = 12) -> list[str]:
    """Retorna archivos del proyecto activo (no .bago/)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--cached", "--exclude-standard"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=5
        )
        files = [
            f for f in result.stdout.strip().splitlines()
            if not f.startswith(".bago/") and not f.startswith("build/") and not f.startswith("dist/")
        ]
        return files[:max_items]
    except Exception:
        return []


# ── Constructores de paneles ──────────────────────────────────────────────────

def _panel_left(sessions: list[dict], gs: dict, agents: list[str], tools_count: int) -> Panel:
    t = Text()

    # Sección: Sesiones recientes
    workflow = gs.get("sprint_status", {}).get("active_workflow", {})
    active_title = workflow.get("title", "")

    if sessions:
        for i, s in enumerate(sessions[:6]):
            task = s.get("task", "sesión")[:28]
            ts   = s.get("timestamp")
            time_str = ""
            if ts:
                try:
                    dt = datetime.fromtimestamp(ts)
                    time_str = dt.strftime("%d/%m %H:%M")
                except Exception:
                    pass
            icon = "◉" if i == 0 else "○"
            t.append(f"\n  {icon} ", style=C_ACCENT if i == 0 else C_ITEM_DIM)
            t.append(f"{task}", style=C_ITEM if i == 0 else C_ITEM_DIM)
            if time_str:
                t.append(f"\n    {time_str}", style=C_ITEM_DIM)
    else:
        t.append("\n  ", style=C_ITEM_DIM)
        t.append("Sin sesiones registradas", style=C_ITEM_DIM)

    # Separador
    t.append("\n\n")

    # Sección: Personalizaciones
    t.append("  Personalizaciones", style=f"bold {C_ACCENT}")
    t.append("  ∨", style=C_ITEM_DIM)
    t.append("\n")

    items = [
        ("◎", "Agentes",       f"{len(agents)} activos"),
        ("⊡", "Habilidades",   f"{tools_count} tools"),
        ("≡", "Instrucciones", "BOOTSTRAP.md"),
        ("⇌", "Flujos",        workflow.get("code", "W2") if workflow else "—"),
        ("⚙", "Tools",         ".bago/tools/"),
        ("⊕", "Extensiones",   ".bago/extensions/"),
    ]
    for icon, label, detail in items:
        t.append(f"\n  {icon} ", style=C_ACCENT)
        t.append(f"{label}", style=C_ITEM)
        t.append(f"  {detail}", style=C_ITEM_DIM)

    return Panel(
        t,
        title="[bold white]Sesiones[/bold white]",
        title_align="left",
        border_style=C_BORDER,
        padding=(0, 1),
    )


def _panel_center(gs: dict, active_task: dict | None, last_input: str = "") -> Panel:
    t = Text()

    workflow = gs.get("sprint_status", {}).get("active_workflow", {})

    if workflow:
        t.append("\n")
        t.append(f"  Área de trabajo activa\n", style=C_ITEM_DIM)
        t.append(f"  {workflow.get('code','W2')} — ", style=C_ACCENT)
        t.append(f"{workflow.get('title','')}\n", style=f"bold {C_ITEM}")
        started = workflow.get("started", "")
        if started:
            try:
                dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                t.append(f"  Iniciado: {dt.strftime('%d/%m/%Y %H:%M')}\n", style=C_ITEM_DIM)
            except Exception:
                pass
    else:
        t.append("\n\n")
        t.append("  Para empezar, selecciona un ", style=C_ITEM_DIM)
        t.append("área de trabajo", style=f"bold {C_ACCENT}")
        t.append(" ∨\n", style=C_ITEM_DIM)

    # Tarea activa
    if active_task:
        t.append("\n  Tarea activa:\n", style=C_ITEM_DIM)
        title = active_task.get("title") or active_task.get("idea_title", "")
        if title:
            t.append(f"  ▸ {title[:60]}\n", style=f"bold {C_GREEN}")
        step = active_task.get("siguiente_paso") or active_task.get("next_step", "")
        if step:
            t.append(f"    → {step[:70]}\n", style=C_ITEM_DIM)

    # Input box — ancho 38 para caber en el panel central
    W = 38
    t.append("\n")
    t.append("  ┌" + "─" * W + "┐\n", style=C_BORDER)
    if last_input:
        display = last_input[: W - 2]
        padding = " " * (W - 2 - len(display))
        t.append(f"  │ {display}{padding} │\n", style=C_ITEM)
    else:
        placeholder = "¿Cuál es tu próximo hito?"
        padding = " " * (W - 2 - len(placeholder))
        t.append(f"  │ {placeholder}{padding} │\n", style=C_ITEM_DIM)
    plus_pad = " " * (W - 4)
    t.append(f"  │ +{plus_pad}↑ │\n", style=C_ITEM_DIM)
    t.append("  └" + "─" * W + "┘\n", style=C_BORDER)

    return Panel(
        t,
        title="[bold white]Área de trabajo[/bold white]",
        title_align="left",
        border_style=C_BORDER,
        padding=(0, 1),
    )


def _panel_right(tab: str = "cambios") -> Panel:
    t = Text()

    # Tabs
    t.append("\n  ")
    if tab == "cambios":
        t.append("Cambios", style=f"bold {C_ACCENT}")
        t.append("  Archivos", style=C_ITEM_DIM)
    else:
        t.append("Cambios", style=C_ITEM_DIM)
        t.append("  Archivos", style=f"bold {C_ACCENT}")
    t.append("\n")
    t.append("  " + "─" * 28 + "\n", style=C_BORDER)

    if tab == "cambios":
        changes = _git_changes()
        if changes:
            status_colors = {
                "M": C_YELLOW, "A": C_GREEN, "D": "red3",
                "R": C_ACCENT, "?": C_ITEM_DIM, "??": C_ITEM_DIM,
            }
            for status, filepath in changes:
                color = status_colors.get(status, C_ITEM)
                fname = Path(filepath).name
                t.append(f"\n  {status:<2} ", style=color)
                t.append(f"{fname[:24]}", style=C_ITEM)
                parent = str(Path(filepath).parent)
                if parent != ".":
                    t.append(f"\n     {parent[:24]}", style=C_ITEM_DIM)
        else:
            t.append("\n\n")
            t.append("  ⬡\n\n", style=C_ITEM_DIM)
            t.append("  Sin cambios\n", style=C_ITEM_DIM)
            t.append("  pendientes.\n", style=C_ITEM_DIM)
    else:
        files = _project_files()
        if files:
            for filepath in files:
                fname = Path(filepath).name
                ext   = Path(filepath).suffix
                ext_icons = {
                    ".py": "🐍", ".md": "📄", ".json": "📋",
                    ".txt": "📝", ".sh": "⚙", ".yaml": "📋", ".yml": "📋",
                }
                icon = ext_icons.get(ext, "📁")
                t.append(f"\n  {icon} {fname[:24]}", style=C_ITEM)
                parent = str(Path(filepath).parent)
                if parent != ".":
                    t.append(f"\n    {parent[:24]}", style=C_ITEM_DIM)
        else:
            t.append("\n\n")
            t.append("  ⬡\n\n", style=C_ITEM_DIM)
            t.append("  Las carpetas y los\n", style=C_ITEM_DIM)
            t.append("  archivos aparecerán\n", style=C_ITEM_DIM)
            t.append("  aquí.\n", style=C_ITEM_DIM)

    return Panel(
        t,
        border_style=C_BORDER,
        padding=(0, 0),
    )


# ── Render principal ──────────────────────────────────────────────────────────

def _build_layout(sessions, gs, agents, tools_count, active_task, tab, last_input="") -> Layout:
    layout = Layout()
    layout.split_row(
        Layout(name="left",   ratio=3),
        Layout(name="center", ratio=5),
        Layout(name="right",  ratio=3),
    )
    layout["left"].update(_panel_left(sessions, gs, agents, tools_count))
    layout["center"].update(_panel_center(gs, active_task, last_input))
    layout["right"].update(_panel_right(tab))
    return layout


def _render_once(tab: str = "cambios") -> None:
    gs          = _load_global_state()
    sessions    = _load_recent_sessions()
    agents      = _load_agents()
    tools_count = _load_tools_count()
    active_task = _load_active_task()
    layout      = _build_layout(sessions, gs, agents, tools_count, active_task, tab)
    # Altura fija de 30 líneas para no ocupar toda la terminal
    console.print(layout, height=30)


# ── Modo interactivo ──────────────────────────────────────────────────────────

def _run_interactive(tab: str = "cambios") -> int:
    gs          = _load_global_state()
    sessions    = _load_recent_sessions()
    agents      = _load_agents()
    tools_count = _load_tools_count()
    active_task = _load_active_task()
    last_input  = ""

    # Comandos especiales en modo creación
    special_cmds: dict[str, str] = {
        ":q":         "salir",
        ":quit":      "salir",
        ":cambios":   "cambiar a tab Cambios",
        ":archivos":  "cambiar a tab Archivos",
        ":refresh":   "refrescar datos",
        ":ideas":     "ver ideas disponibles",
        ":task":      "ver tarea activa",
    }

    pt_style = Style.from_dict({
        "prompt":       "#5555ff bold",
        "rprompt":      "#666666",
    })

    if _HAS_PROMPT_TOOLKIT:
        session: PromptSession = PromptSession(
            history=None,
            style=pt_style,
        )
    else:
        session = None

    while True:
        # Render layout
        console.clear()
        layout = _build_layout(
            sessions, gs, agents, tools_count, active_task, tab, last_input
        )
        console.print(layout)

        # Info de comandos
        console.print(
            f"\n  [grey50]:q salir  :cambios/:archivos tabs  :refresh  :ideas  :task[/grey50]"
        )

        # Input
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

        # Comandos especiales
        if user_input in (":q", ":quit"):
            console.print("\n[grey50]  Saliendo de modo creación.[/grey50]")
            return 0
        elif user_input == ":cambios":
            tab = "cambios"
        elif user_input == ":archivos":
            tab = "archivos"
        elif user_input == ":refresh":
            gs          = _load_global_state()
            sessions    = _load_recent_sessions()
            active_task = _load_active_task()
        elif user_input == ":ideas":
            console.clear()
            import subprocess
            subprocess.run([sys.executable, str(TOOLS_DIR / "emit_ideas.py")], cwd=str(ROOT))
            input("\n  [Enter para volver al modo creación]")
        elif user_input == ":task":
            console.clear()
            subprocess.run([sys.executable, str(TOOLS_DIR / "show_task.py")], cwd=str(ROOT))
            input("\n  [Enter para volver al modo creación]")
        else:
            # Guardar como hito / nota en la tarea activa
            last_input = user_input
            _save_milestone(user_input, gs)


def _save_milestone(text: str, gs: dict) -> None:
    """Guarda el hito como nota en el estado de la tarea activa."""
    task_file = STATE / "pending_w2_task.json"
    if task_file.exists():
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
            milestones = task.get("milestones", [])
            milestones.append({
                "text":      text,
                "timestamp": datetime.now().isoformat(),
            })
            task["milestones"] = milestones
            task_file.write_text(
                json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass
    else:
        # Sin tarea activa: guardar en notas de creación
        notes_file = STATE / "creation_notes.json"
        notes = []
        if notes_file.exists():
            try:
                notes = json.loads(notes_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        notes.append({"text": text, "timestamp": datetime.now().isoformat()})
        notes_file.write_text(
            json.dumps(notes[-50:], indent=2, ensure_ascii=False), encoding="utf-8"
        )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="BAGO modo creación — layout 3 paneles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Render único (no interactivo)",
    )
    parser.add_argument(
        "--tab", choices=["cambios", "archivos"], default="cambios",
        help="Panel derecho inicial (default: cambios)",
    )
    args = parser.parse_args()

    if args.once:
        _render_once(args.tab)
        return 0

    return _run_interactive(args.tab)


if __name__ == "__main__":
    sys.exit(main())

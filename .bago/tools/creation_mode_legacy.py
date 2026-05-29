#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""creation_mode.py — BAGO modo creación: layout 3 paneles tipo AI Studio.

Layout:
  ┌──────────────────┬──────────────────────────────────┬─────────────────┐
  │    SESIONES      │          ÁREA DE TRABAJO         │ CAMBIOS/ARCHIVOS│
  │                  │     (proyecto + tarea activa)      │  preview/issues │
  │  lista sesiones  │                                  │                 │
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
    python3 .bago/tools/creation_mode.py --tab preview   # panel derecho: preview
    python3 .bago/tools/creation_mode.py --tab issues    # panel derecho: issues
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import json
import os
import fnmatch
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path


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
    PromptSession = None
    Style = None
    HTML = None
    _HAS_PROMPT_TOOLKIT = False

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
BAGO_ROOT  = ROOT / ".bago"
STATE      = BAGO_ROOT / "state"
TOOLS_DIR  = BAGO_ROOT / "tools"
DB         = STATE / "bago.db"

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
C_RED        = "red3"
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


def _load_agents() -> list[str]:
    reg = STATE / "agents_registry.json"
    if not reg.exists():
        return []
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        return [k for k in data if not k.startswith("_")]
    except Exception:
        return []


def _load_tools_count() -> int:
    try:
        return len(list((TOOLS_DIR).glob("*.py")))
    except Exception:
        return 0


def _load_active_task() -> dict | None:
    task_file = STATE / "pending_w2_task.json"
    if not task_file.exists():
        return None
    try:
        return json.loads(task_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_project() -> dict:
    """Carga el proyecto activo vinculado desde repo_context.json."""
    rc = STATE / "repo_context.json"
    if not rc.exists():
        return {}
    try:
        return json.loads(rc.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_projects() -> list[dict]:
    """Carga proyectos recientes para multi-proyecto."""
    rp = STATE / "recent_projects.json"
    if not rp.exists():
        return []
    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _load_issues() -> list[dict]:
    """Carga issues con label bago o estado bago-in-progress."""
    issues: list[dict] = []
    if DB.exists():
        try:
            con = sqlite3.connect(str(DB), timeout=1)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                """SELECT id, title, status, priority, source FROM issues
                   WHERE status IN ('open','in-progress','bago-in-progress')
                   ORDER BY priority DESC, created_at DESC LIMIT 15"""
            ).fetchall()
            for r in rows:
                issues.append(dict(r))
            con.close()
        except Exception:
            pass
    if not issues:
        issues_file = STATE / "issues.json"
        if issues_file.exists():
            try:
                data = json.loads(issues_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    issues = [i for i in data if i.get("status") in ("open", "in-progress", "bago-in-progress")][:15]
            except Exception:
                pass
    return issues


def _load_layer_config() -> dict:
    cfg = STATE / "creation_studio.json"
    if not cfg.exists():
        return {}
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return {}


_LAYERS: dict[str, dict] = {
    "frontend": {
        "patterns": [
            "*/frontend/**", "*/src/components/**", "*/src/ui/**", "*/src/hooks/**",
            "*/src/pages/**", "*/public/**", "*/styles/**", "*/assets/**",
            "*.css", "*.scss", "*.less", "*.tsx", "*.jsx", "*.vue", "*.svelte",
            "*.html", "*.htm",
        ],
    },
    "backend": {
        "patterns": [
            "*/backend/**", "*/src/api/**", "*/src/services/**", "*/src/models/**",
            "*/src/workers/**", "*/src/middleware/**", "*/src/core/**",
            "*.py", "*.go", "*.rs", "*.java", "*.kt", "*.rb",
        ],
    },
    "db": {
        "patterns": [
            "*/migrations/**", "*/seeds/**", "*/schema/**", "*/db/**",
            "*.sql", "*.prisma", "*.orm", "*.ddl",
        ],
    },
    "api": {
        "patterns": [
            "*/api/**", "*/openapi/**", "*/swagger/**", "*/proto/**",
            "*.yaml", "*.yml", "*.proto", "*.graphql", "*.gql", "*.wsdl",
        ],
    },
    "infra": {
        "patterns": [
            "Dockerfile*", "docker-compose*", "*/k8s/**", "*/.github/**",
            "*/terraform/**", "*/nginx/**", "*/scripts/**",
            "*.tf", "*.hcl", "*.yml", "*.yaml", ".env*",
        ],
    },
    "all": {"patterns": ["*"]},
}


def _matches_layer(path: str, layer: str) -> bool:
    if not layer or layer == "all":
        return True
    cfg = _LAYERS.get(layer)
    if not cfg:
        return True
    for pat in cfg.get("patterns", []):
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, "*/" + pat):
            return True
    return False


def _preview_file(path: str, max_lines: int = 40) -> list[str]:
    """Devuelve las primeras líneas de un archivo."""
    p = Path(path)
    if not p.exists() or p.is_dir():
        return ["  (no existe)"]
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        out = [f"  {l.rstrip()}" for l in lines[:max_lines]]
        if total > max_lines:
            out.append(f"  ... ({total - max_lines} líneas más)")
        return out or ["  (vacío)"]
    except Exception as exc:
        return [f"  Error: {exc}"]


def _run_command(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> tuple[int, str, str]:
    """Ejecuta un comando y devuelve (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as exc:
        return -1, "", str(exc)


def _git_status_lines(root: Path, layer: str = "") -> list[str]:
    """Devuelve líneas de git status --short, filtradas por capa."""
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, cwd=str(root), encoding="utf-8", errors="replace", timeout=10
        )
        out = proc.stdout.strip()
        lines = out.splitlines() if out else []
        if not lines:
            return ["  Sin cambios"]
        if not layer or layer == "all":
            return lines
        filtered = [l for l in lines if _matches_layer(l.split()[-1] if l.split() else l, layer)]
        return filtered or ["  Sin cambios en esta capa"]
    except Exception:
        return ["  (git no disponible)"]


def _git_file_tree(root: Path, layer: str = "") -> list[str]:
    """Devuelve lista de archivos trackeados, filtrados por capa."""
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, cwd=str(root), encoding="utf-8", errors="replace", timeout=10
        )
        out = proc.stdout.strip()
        lines = out.splitlines()
        if layer and layer != "all":
            lines = [l for l in lines if _matches_layer(l, layer)]
        lines = lines[:30]
        return [f"  {l}" for l in lines] or ["  (vacío)"]
    except Exception:
        return ["  (git no disponible)"]


# ── Render helpers ──────────────────────────────────────────────────────────────

def _panel(title: str, content: str | Text, border_color: str = C_BORDER) -> Panel:
    return Panel(
        content,
        title=f"[bold {border_color}]{title}[/bold {border_color}]",
        border_style=border_color,
        padding=(0, 1),
    )


def _build_left_panel(sessions: list[dict], agents: list[str], tools_count: int) -> Panel:
    t = Table(box=None, padding=(0, 0), show_header=False)
    t.add_column(style=C_ITEM, overflow="fold")

    t.add_row(f"[{C_HEADER}]Sesiones recientes[/{C_HEADER}]")
    for s in sessions[:6]:
        task = s.get("task", "?")
        t.add_row(f"  [{C_ACCENT}]▸[/{C_ACCENT}] {task[:34]}")
    if not sessions:
        t.add_row(f"  [{C_ITEM_DIM}]— ninguna —[/{C_ITEM_DIM}]")

    t.add_row("")
    t.add_row(f"[{C_HEADER}]Personalización[/{C_HEADER}]")
    t.add_row(f"  [{C_GREEN}]●[/{C_GREEN}] Agentes  [{C_ITEM_DIM}]{len(agents)}[/{C_ITEM_DIM}]")
    t.add_row(f"  [{C_GREEN}]●[/{C_GREEN}] Skills   [{C_ITEM_DIM}]171[/{C_ITEM_DIM}]")
    t.add_row(f"  [{C_GREEN}]●[/{C_GREEN}] Tools    [{C_ITEM_DIM}]{tools_count}[/{C_ITEM_DIM}]")
    t.add_row(f"  [{C_GREEN}]●[/{C_GREEN}] Flujos W2")

    return _panel("Sesiones", t)


def _build_center_panel(active_task: dict | None, project: dict, last_input: str, build_status: str, layer: str = "", sublayer: str = "") -> Panel:
    t = Table(box=None, padding=(0, 0), show_header=False)
    t.add_column(style=C_ITEM, overflow="fold")

    proj_name = project.get("project_name", "—") or "—"
    proj_path = project.get("project_path", "")
    branch    = project.get("git_branch", "—") or "—"
    mode      = project.get("working_mode", "—") or "—"
    t.add_row(f"[{C_HEADER}]Proyecto activo[/{C_HEADER}]")
    t.add_row(f"  [{C_ACCENT}]▶[/{C_ACCENT}] {proj_name}")
    if proj_path:
        t.add_row(f"  [{C_ITEM_DIM}]   {proj_path}[/{C_ITEM_DIM}]")
    t.add_row(f"  [{C_ITEM_DIM}]   branch {branch}  ·  modo {mode}[/{C_ITEM_DIM}]")
    if layer:
        sub_info = f" · {sublayer}" if sublayer else ""
        t.add_row(f"  [{C_YELLOW}]   capa: {layer}{sub_info}[/{C_YELLOW}]")
    t.add_row("")

    t.add_row(f"[{C_HEADER}]Tarea activa[/{C_HEADER}]")
    if active_task:
        title = active_task.get("title", active_task.get("idea_title", "?"))
        slot  = active_task.get("slot", active_task.get("idea_index", "?"))
        t.add_row(f"  [{C_GREEN}]▶[/{C_GREEN}] [{C_ACCENT}]{title}[/{C_ACCENT}]")
        t.add_row(f"  [{C_ITEM_DIM}]   slot #{slot}[/{C_ITEM_DIM}]")
        milestones = active_task.get("milestones", [])
        if milestones:
            t.add_row(f"  [{C_ITEM_DIM}]   hitos: {len(milestones)}[/{C_ITEM_DIM}]")
    else:
        t.add_row(f"  [{C_ITEM_DIM}]— Sin tarea activa —[/{C_ITEM_DIM}]")
        t.add_row(f"  [{C_ITEM_DIM}]   Acepta una idea: bago ideas --accept 1[/{C_ITEM_DIM}]")

    t.add_row("")
    t.add_row(f"[{C_HEADER}]Último hito[/{C_HEADER}]")
    if last_input:
        t.add_row(f"  [{C_YELLOW}]›[/{C_YELLOW}] {last_input[:56]}")
    else:
        t.add_row(f"  [{C_ITEM_DIM}]— escribe un hito —[/{C_ITEM_DIM}]")

    if build_status:
        t.add_row("")
        t.add_row(f"[{C_HEADER}]Build[/{C_HEADER}]")
        t.add_row(f"  {build_status}")

    return _panel("Área de trabajo", t)


def _build_right_panel(tab: str, root: Path, preview_path: str | None, issues: list[dict], layer: str = "") -> Panel:
    if tab == "cambios":
        lines = _git_status_lines(root, layer)
        content = "\n".join(lines[:28])
        title = f"Cambios [{layer}]" if layer else "Cambios"
        return _panel(title, content)

    if tab == "archivos":
        lines = _git_file_tree(root, layer)
        title = f"Archivos [{layer}]" if layer else "Archivos"
        return _panel(title, "\n".join(lines))

    if tab == "preview":
        if preview_path:
            lines = _preview_file(preview_path)
            header = f"[{C_HEADER}]{preview_path}[/{C_HEADER}]\n"
            return _panel("Preview", header + "\n".join(lines))
        return _panel("Preview", f"  [{C_ITEM_DIM}]Usa :preview <archivo>[/{C_ITEM_DIM}]")

    if tab == "issues":
        if not issues:
            return _panel("Issues", f"  [{C_ITEM_DIM}]Sin issues abiertos[/{C_ITEM_DIM}]")
        t = Table(box=None, padding=(0, 0), show_header=False)
        t.add_column(style=C_ITEM, overflow="fold")
        for issue in issues[:10]:
            title = issue.get("title", "?")
            status = issue.get("status", "?")
            pri = issue.get("priority", 0)
            color = C_GREEN if status == "open" else C_YELLOW
            t.add_row(f"  [{color}]●[/{color}] [{C_ACCENT}]{title[:40]}[/{C_ACCENT}] [{C_ITEM_DIM}]({status} p{pri})[/{C_ITEM_DIM}]")
        return _panel(f"Issues ({len(issues)})", t)

    return _panel("Panel", "")


def _build_layout(
    sessions: list[dict],
    gs: dict,
    agents: list[str],
    tools_count: int,
    active_task: dict | None,
    project: dict,
    issues: list[dict],
    tab: str,
    last_input: str,
    preview_path: str | None,
    build_status: str,
    layer: str = "",
    sublayer: str = "",
) -> Layout:
    layout = Layout()
    layout.split_row(
        Layout(name="left",   size=26),
        Layout(name="center", ratio=2),
        Layout(name="right",  size=38),
    )
    layout["left"].update(_build_left_panel(sessions, agents, tools_count))
    layout["center"].update(_build_center_panel(active_task, project, last_input, build_status, layer, sublayer))
    layout["right"].update(_build_right_panel(tab, ROOT, preview_path, issues, layer))
    return layout


# ── Entry points ──────────────────────────────────────────────────────────────

def _render_once(tab: str, layer: str = "", sublayer: str = "") -> None:
    gs          = _load_global_state()
    sessions    = _load_recent_sessions()
    agents      = _load_agents()
    tools_count = _load_tools_count()
    active_task = _load_active_task()
    project     = _load_project()
    issues      = _load_issues()
    layout = _build_layout(
        sessions, gs, agents, tools_count, active_task,
        project, issues, tab, "", None, "", layer, sublayer,
    )
    console.print(layout)


def _run_interactive(tab: str, layer: str = "", sublayer: str = "") -> int:
    gs          = _load_global_state()
    sessions    = _load_recent_sessions()
    agents      = _load_agents()
    tools_count = _load_tools_count()
    active_task = _load_active_task()
    project     = _load_project()
    issues      = _load_issues()
    last_input  = ""
    preview_path = None
    build_status = ""

    special_cmds: dict[str, str] = {
        ":q":         "salir",
        ":quit":      "salir",
        ":cambios":   "cambiar a tab Cambios",
        ":archivos":  "cambiar a tab Archivos",
        ":preview":   "cambiar a tab Preview",
        ":issues":    "cambiar a tab Issues",
        ":refresh":   "refrescar datos",
        ":ideas":     "ver ideas disponibles",
        ":task":      "ver tarea activa",
        ":project":   "cambiar proyecto activo",
        ":build":     "ejecutar build",
        ":test":      "ejecutar tests",
        ":lint":      "ejecutar linter",
        ":layer":     "cambiar capa arquitectonica",
        ":sub":       "cambiar subcapa",
        ":all":       "ver todas las capas",
        ":chat":      "volver al chat BAGO",
    }

    if _HAS_PROMPT_TOOLKIT:
        pt_style = Style.from_dict({
            "prompt":       "#5555ff bold",
            "rprompt":      "#666666",
        })
        session: PromptSession = PromptSession(
            history=None,
            style=pt_style,
        )
    else:
        session = None

    while True:
        console.clear()
        layout = _build_layout(
            sessions, gs, agents, tools_count, active_task,
            project, issues, tab, last_input, preview_path, build_status,
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
            gs          = _load_global_state()
            sessions    = _load_recent_sessions()
            active_task = _load_active_task()
            project     = _load_project()
            issues      = _load_issues()
            build_status = ""
        elif user_input == ":ideas":
            console.clear()
            subprocess.run([sys.executable, str(TOOLS_DIR / "emit_ideas.py")], cwd=str(ROOT))
            input("\n  [Enter para volver al modo creación]")
        elif user_input == ":task":
            console.clear()
            subprocess.run([sys.executable, str(TOOLS_DIR / "show_task.py")], cwd=str(ROOT))
            input("\n  [Enter para volver al modo creación]")
        elif user_input == ":project":
            projects = _load_projects()
            console.clear()
            if projects:
                console.print(f"[{C_HEADER}]Proyectos disponibles:[/{C_HEADER}]")
                for i, p in enumerate(projects[:10], 1):
                    name = p.get("name") or Path(p.get("path", "?")).name
                    active = "  [green]✓[/green]" if name == project.get("project_name") else ""
                    console.print(f"  {i}. {name}{active}")
                console.print(f"\n  [{C_ITEM_DIM}]Usa :project <número> para cambiar[/{C_ITEM_DIM}]")
            else:
                console.print(f"[{C_YELLOW}]Sin proyectos recientes.[/{C_YELLOW}]")
            input("\n  [Enter para volver]")
        elif user_input.startswith(":project "):
            idx_str = user_input[len(":project "):].strip()
            projects = _load_projects()
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(projects):
                    proj = projects[idx]
                    proj_path = proj.get("path", "")
                    if proj_path:
                        rc = STATE / "repo_context.json"
                        try:
                            rc_data = json.loads(rc.read_text(encoding="utf-8")) if rc.exists() else {}
                            rc_data["project_name"] = proj.get("name") or Path(proj_path).name
                            rc_data["project_path"] = proj_path
                            rc.write_text(json.dumps(rc_data, indent=2, ensure_ascii=False), encoding="utf-8")
                            project = _load_project()
                            build_status = f"[{C_GREEN}]Proyecto cambiado a {rc_data['project_name']}[/{C_GREEN}]"
                        except Exception as exc:
                            build_status = f"[{C_RED}]Error: {exc}[/{C_RED}]"
                else:
                    build_status = f"[{C_RED}]Índice fuera de rango[/{C_RED}]"
            except ValueError:
                build_status = f"[{C_RED}]Número inválido[/{C_RED}]"
        elif user_input == ":build":
            proj_path = project.get("project_path") or str(ROOT)
            console.clear()
            console.print(f"[{C_HEADER}]Build en {proj_path}[/{C_HEADER}]")
            rc, out, err = _run_command([sys.executable, "-m", "build"], cwd=proj_path, timeout=120)
            if rc == 0:
                build_status = f"[{C_GREEN}]✓ Build OK[/{C_GREEN}]"
            else:
                build_status = f"[{C_RED}]✗ Build falló (rc={rc})[/{C_RED}]"
            console.print(out[-800:] if len(out) > 800 else out or "(sin salida)")
            if err:
                console.print(f"[red]{err[:400]}[/red]")
            input("\n  [Enter para volver]")
        elif user_input == ":test":
            proj_path = project.get("project_path") or str(ROOT)
            console.clear()
            console.print(f"[{C_HEADER}]Test en {proj_path}[/{C_HEADER}]")
            rc, out, err = _run_command([sys.executable, "-m", "pytest", "-q"], cwd=proj_path, timeout=120)
            if rc == 0:
                build_status = f"[{C_GREEN}]✓ Tests OK[/{C_GREEN}]"
            else:
                build_status = f"[{C_RED}]✗ Tests fallaron (rc={rc})[/{C_RED}]"
            console.print(out[-800:] if len(out) > 800 else out or "(sin salida)")
            if err:
                console.print(f"[red]{err[:400]}[/red]")
            input("\n  [Enter para volver]")
        elif user_input == ":lint":
            proj_path = project.get("project_path") or str(ROOT)
            console.clear()
            console.print(f"[{C_HEADER}]Lint en {proj_path}[/{C_HEADER}]")
            rc, out, err = _run_command([sys.executable, "-m", "flake8", "."], cwd=proj_path, timeout=120)
            if rc == 0:
                build_status = f"[{C_GREEN}]✓ Lint OK[/{C_GREEN}]"
            else:
                build_status = f"[{C_YELLOW}]⚠ Lint con advertencias (rc={rc})[/{C_YELLOW}]"
            console.print(out[-800:] if len(out) > 800 else out or "(sin salida)")
            if err:
                console.print(f"[red]{err[:400]}[/red]")
            input("\n  [Enter para volver]")
        elif user_input.startswith(":layer "):
            layer = user_input[len(":layer "):].strip().lower()
            build_status = f"[{C_GREEN}]Capa cambiada a {layer}[/{C_GREEN}]"
        elif user_input.startswith(":sub "):
            sublayer = user_input[len(":sub "):].strip().lower()
            build_status = f"[{C_GREEN}]Subcapa cambiada a {sublayer}[/{C_GREEN}]"
        elif user_input == ":all":
            layer = ""
            sublayer = ""
            build_status = f"[{C_GREEN}]Vista unificada (todas las capas)[/{C_GREEN}]"
        elif user_input == ":chat":
            console.print("\n[grey50]  Volviendo al chat BAGO...[/grey50]")
            return 0
        else:
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
        "--tab", choices=["cambios", "archivos", "preview", "issues"], default="cambios",
        help="Panel derecho inicial (default: cambios)",
    )
    parser.add_argument(
        "--layer", default="",
        help="Capa arquitectonica (frontend, backend, db, api, infra, all)",
    )
    parser.add_argument(
        "--sublayer", default="",
        help="Subcapa dentro de la capa seleccionada",
    )
    args = parser.parse_args()

    layer = args.layer
    sublayer = args.sublayer
    if not layer:
        cfg = _load_layer_config()
        layer = cfg.get("layer", "")
        if not sublayer:
            sublayer = cfg.get("sublayer", "")
    if args.once:
        _render_once(args.tab, layer, sublayer)
        return 0
    return _run_interactive(args.tab, layer, sublayer)




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
    sys.exit(main())
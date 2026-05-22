"""creation_mode.renderer — Paneles Rich y layout de 3 columnas."""
from __future__ import annotations

from pathlib import Path

from .config import (
    C_HEADER, C_ITEM, C_ITEM_DIM, C_ACCENT, C_GREEN, C_YELLOW, C_RED,
    C_BORDER, console, Panel, Layout, Table, ROOT,
)
from .git_tools import git_status_lines, git_file_tree, preview_file


def panel(title: str, content, border_color: str = None) -> Panel:
    from .config import C_BORDER
    if border_color is None:
        border_color = C_BORDER
    return Panel(
        content,
        title=f"[bold {border_color}]{title}[/bold {border_color}]",
        border_style=border_color,
        padding=(0, 1),
    )


def build_left_panel(sessions, agents, tools_count) -> Panel:
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

    return panel("Sesiones", t)


def build_center_panel(active_task, project, last_input, build_status, layer: str = "", sublayer: str = "") -> Panel:
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

    return panel("Área de trabajo", t)


def build_right_panel(tab: str, root: Path, preview_path: str | None, issues, layer: str = "") -> Panel:
    if tab == "cambios":
        lines = git_status_lines(root, layer)
        content = "\n".join(lines[:28])
        title = f"Cambios [{layer}]" if layer else "Cambios"
        return panel(title, content)

    if tab == "archivos":
        lines = git_file_tree(root, layer)
        title = f"Archivos [{layer}]" if layer else "Archivos"
        return panel(title, "\n".join(lines))

    if tab == "preview":
        if preview_path:
            lines = preview_file(preview_path)
            header = f"[{C_HEADER}]{preview_path}[/{C_HEADER}]\n"
            return panel("Preview", header + "\n".join(lines))
        return panel("Preview", f"  [{C_ITEM_DIM}]Usa :preview <archivo>[/{C_ITEM_DIM}]")

    if tab == "issues":
        if not issues:
            return panel("Issues", f"  [{C_ITEM_DIM}]Sin issues abiertos[/{C_ITEM_DIM}]")
        t = Table(box=None, padding=(0, 0), show_header=False)
        t.add_column(style=C_ITEM, overflow="fold")
        for issue in issues[:10]:
            title = issue.get("title", "?")
            status = issue.get("status", "?")
            pri = issue.get("priority", 0)
            color = C_GREEN if status == "open" else C_YELLOW
            t.add_row(f"  [{color}]●[/{color}] [{C_ACCENT}]{title[:40]}[/{C_ACCENT}] [{C_ITEM_DIM}]({status} p{pri})[/{C_ITEM_DIM}]")
        return panel(f"Issues ({len(issues)})", t)

    return panel("Panel", "")


def build_layout(sessions, gs, agents, tools_count, active_task, project, issues, tab, last_input, preview_path, build_status, layer: str = "", sublayer: str = ""):
    layout = Layout()
    layout.split_row(
        Layout(name="left",   size=26),
        Layout(name="center", ratio=2),
        Layout(name="right",  size=38),
    )
    layout["left"].update(build_left_panel(sessions, agents, tools_count))
    layout["center"].update(build_center_panel(active_task, project, last_input, build_status, layer, sublayer))
    layout["right"].update(build_right_panel(tab, ROOT, preview_path, issues, layer))
    return layout

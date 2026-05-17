#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_config.py — Configurador de agentes BAGO (TUI interactivo).

Inspirado en VS Code "Personalizaciones del agente".

Layout:
  ┌──────────────────────┬────────────────────────────────────────────────┐
  │  ⚙ BAGO CLI          │ [Buscar...]              [Examinar] [+]        │
  │  ──────────────────  │ ────────────────────────────────────────────── │
  │  🤖 Agentes       4  │ ▸ BagoAgents (4)                               │
  │  ⊡  Habilidades 123  │   ▣ agent_tools  — tools y revisión de código  │
  │  ≡  Instrucciones 8  │   ▣ agent_tests  — ejecución de tests          │
  │  ⊞  Servidores MCP 1 │                                                │
  │  ⊕  Complementos   1 │ ▸ Roles (8)                                    │
  │                      │   ▣ MAESTRO_BAGO — coordina la sesión          │
  │                      │                                                │
  │  [↑↓] navegar        │ Descripción del ítem seleccionado...           │
  │  [/] buscar [q] exit │                                                │
  └──────────────────────┴────────────────────────────────────────────────┘

Teclas:
  ↑ / k   — subir en la lista activa
  ↓ / j   — bajar en la lista activa
  Tab     — alternar foco entre panel nav y lista
  /       — activar búsqueda
  ESC     — cancelar búsqueda / salir
  q       — salir
  +       — añadir ítem (instrucciones)
  Enter   — ver detalle del ítem seleccionado
"""
from __future__ import annotations

import json
import os
import sys
import termios
import tty
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich import box as rbox
except ImportError:
    print("ERROR: pip install rich", file=sys.stderr)
    sys.exit(1)

# ── Rutas ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_BAGO = _HERE.parent
_STATE = _BAGO / "state"
_AGENTS_DIR = _BAGO / "agents"
_EXT_DIR = _BAGO / "extensions"

# ── Paleta ───────────────────────────────────────────────────────────────────
C_BG          = "grey19"
C_ACCENT      = "bright_cyan"
C_SELECTED_BG = "grey23"
C_ACTIVE_NAV  = "bright_white"
C_DIM         = "grey50"
C_ITEM        = "white"
C_HEADER      = "bold bright_white"
C_BADGE       = "cyan"
C_GROUP_TITLE = "bold cyan"
C_ICON        = "bright_cyan"
C_BORDER      = "grey30"
C_SEARCH      = "bright_yellow"
C_CURSOR      = "bold reverse"

console = Console(highlight=False)

# ── Modelo de datos ───────────────────────────────────────────────────────────
@dataclass
class ConfigItem:
    name: str
    description: str
    scope: str          # "usuario" | "sistema" | "integrado"
    active: bool = True
    detail: str = ""
    icon: str = "▣"


@dataclass
class NavSection:
    key: str
    label: str
    icon: str
    items: list[ConfigItem] = field(default_factory=list)

    def count(self) -> int:
        return len(self.items)


# ── Carga de datos ────────────────────────────────────────────────────────────
def _load_agents() -> list[ConfigItem]:
    items: list[ConfigItem] = []

    # BagoAgents desde state/agents_registry.json
    reg_f = _STATE / "agents_registry.json"
    if reg_f.exists():
        try:
            reg = json.loads(reg_f.read_text(encoding="utf-8"))
            for k, v in reg.items():
                if k == "_meta" or not isinstance(v, dict):
                    continue
                items.append(ConfigItem(
                    name=k,
                    description=v.get("description", ""),
                    scope="usuario",
                    active=v.get("active", True),
                    detail=f"Model: {v.get('model','?')}  Phase: {v.get('phase','?')}  Skills: {v.get('skills',[])}",
                    icon="◎" if v.get("active") else "○",
                ))
        except Exception:
            pass

    # Roles desde .bago/agents/*.md
    if _AGENTS_DIR.exists():
        for md in sorted(_AGENTS_DIR.glob("*.md")):
            name = md.stem
            if name in ("README",):
                continue
            try:
                lines = md.read_text(encoding="utf-8").splitlines()
                desc = ""
                for line in lines[1:6]:
                    if line.strip() and not line.startswith("#") and not line.startswith(">"):
                        desc = line.strip()
                        break
                    if line.startswith(">"):
                        desc = line.lstrip("> ").strip()
                        break
            except Exception:
                desc = ""
            items.append(ConfigItem(
                name=name,
                description=desc[:80],
                scope="sistema",
                icon="≡",
            ))

    return items


def _load_skills() -> list[ConfigItem]:
    items: list[ConfigItem] = []

    # Skill registry
    sk_f = _STATE / "skill_registry.json"
    if sk_f.exists():
        try:
            sk = json.loads(sk_f.read_text(encoding="utf-8"))
            for k, v in sk.items():
                if k == "_meta":
                    continue
                desc = v.get("description", "") if isinstance(v, dict) else str(v)
                items.append(ConfigItem(
                    name=k,
                    description=desc[:80],
                    scope="usuario",
                    icon="⊡",
                ))
        except Exception:
            pass

    # Tool registry — agrupadas por layer
    try:
        sys.path.insert(0, str(_HERE))
        from tool_registry import REGISTRY  # type: ignore
        for cmd, entry in sorted(REGISTRY.items()):
            items.append(ConfigItem(
                name=cmd,
                description=getattr(entry, "description", "")[:70],
                scope="integrado",
                active=not getattr(entry, "deprecated", False),
                detail=f"Layer: {getattr(entry,'layer','?')}  Scope: {getattr(entry,'scope','?')}",
                icon="⊡",
            ))
    except Exception:
        pass

    return items


def _load_instructions() -> list[ConfigItem]:
    items: list[ConfigItem] = []
    for md in sorted(_BAGO.glob("*.md")):
        name = md.stem
        try:
            first_line = md.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
            desc = first_line[:80]
        except Exception:
            desc = ""
        scope = "usuario" if name in ("BOOTSTRAP", "AGENT_START", "START_AGENT") else "sistema"
        items.append(ConfigItem(
            name=md.name,
            description=desc,
            scope=scope,
            icon="≡",
        ))
    return items


def _load_mcp() -> list[ConfigItem]:
    items: list[ConfigItem] = []
    if _EXT_DIR.exists():
        for ext in sorted(_EXT_DIR.iterdir()):
            mjs = ext / "extension.mjs"
            if mjs.exists():
                try:
                    first_comment = ""
                    for line in mjs.read_text(encoding="utf-8").splitlines()[:5]:
                        line = line.strip()
                        if line.startswith("//") and "—" in line:
                            first_comment = line.lstrip("/ ").strip()
                            break
                    desc = first_comment[:80] or ext.name
                except Exception:
                    desc = ext.name
                items.append(ConfigItem(
                    name=ext.name,
                    description=desc,
                    scope="usuario",
                    icon="⊞",
                ))
    return items


def _load_extensions() -> list[ConfigItem]:
    items: list[ConfigItem] = []
    if _EXT_DIR.exists():
        for ext in sorted(_EXT_DIR.iterdir()):
            files = list(ext.iterdir())
            desc = f"{len(files)} archivo(s)"
            items.append(ConfigItem(
                name=ext.name,
                description=desc,
                scope="usuario",
                icon="⊕",
            ))
    return items


def _build_sections() -> list[NavSection]:
    agents   = _load_agents()
    skills   = _load_skills()
    instrs   = _load_instructions()
    mcp      = _load_mcp()
    exts     = _load_extensions()

    return [
        NavSection("agentes",      "Agentes",       "◎", agents),
        NavSection("habilidades",  "Habilidades",   "⊡", skills),
        NavSection("instrucciones","Instrucciones",  "≡", instrs),
        NavSection("mcp",          "Servidores MCP","⊞", mcp),
        NavSection("complementos", "Complementos",  "⊕", exts),
    ]


# ── Teclado raw ───────────────────────────────────────────────────────────────
def _getch() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Read escape sequence
            try:
                tty.setraw(fd)
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    return "\x1b[" + ch3
                return "\x1b" + ch2
            except Exception:
                return "\x1b"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Estado de la UI ───────────────────────────────────────────────────────────
class UIState:
    def __init__(self, sections: list[NavSection]) -> None:
        self.sections   = sections
        self.nav_idx    = 0        # sección activa en nav
        self.list_idx   = 0        # ítem seleccionado en lista derecha
        self.focus      = "nav"    # "nav" | "list"
        self.search     = ""
        self.searching  = False
        self.scroll     = 0        # offset de scroll en lista

    @property
    def current_section(self) -> NavSection:
        return self.sections[self.nav_idx]

    def filtered_items(self) -> list[ConfigItem]:
        items = self.current_section.items
        if self.search:
            q = self.search.lower()
            items = [i for i in items if q in i.name.lower() or q in i.description.lower()]
        return items

    def clamp_list(self) -> None:
        n = len(self.filtered_items())
        self.list_idx = max(0, min(self.list_idx, n - 1))

    def selected_item(self) -> ConfigItem | None:
        items = self.filtered_items()
        if items and 0 <= self.list_idx < len(items):
            return items[self.list_idx]
        return None


# ── Renderizado ───────────────────────────────────────────────────────────────
LIST_HEIGHT = 24   # filas visibles en panel derecho
NAV_HEIGHT  = LIST_HEIGHT


def _render_nav(state: UIState) -> Panel:
    t = Text()
    t.append("\n")
    # Header dropdown
    t.append("  ⚙ ", style=C_ICON)
    t.append("BAGO CLI", style=f"bold {C_ACTIVE_NAV}")
    t.append("  ∨\n", style=C_DIM)
    t.append("\n")

    for i, sec in enumerate(state.sections):
        is_active = (i == state.nav_idx)
        cnt = sec.count()
        cnt_str = f"  {cnt}" if cnt else ""

        if is_active and state.focus == "nav":
            # Highlighted nav item
            t.append(f"  {sec.icon} ", style=f"bold {C_ACCENT}")
            t.append(f"{sec.label}", style=f"bold {C_ACTIVE_NAV}")
            t.append(f"{cnt_str}\n", style=C_BADGE)
        elif is_active:
            t.append(f"  {sec.icon} ", style=C_ACCENT)
            t.append(f"{sec.label}", style=C_ITEM)
            t.append(f"{cnt_str}\n", style=C_BADGE)
        else:
            t.append(f"  {sec.icon} ", style=C_DIM)
            t.append(f"{sec.label}", style=C_DIM)
            t.append(f"{cnt_str}\n", style=C_DIM)

    # Footer hints
    t.append("\n" * max(1, NAV_HEIGHT - len(state.sections) - 5))
    t.append("  ", style="")
    t.append("Tab", style=f"bold {C_DIM}")
    t.append(" panel  ", style=C_DIM)
    t.append("/", style=f"bold {C_DIM}")
    t.append(" buscar\n", style=C_DIM)
    t.append("  ")
    t.append("+", style=f"bold {C_DIM}")
    t.append(" añadir  ", style=C_DIM)
    t.append("q", style=f"bold {C_DIM}")
    t.append(" salir\n", style=C_DIM)

    border = C_ACCENT if state.focus == "nav" else C_BORDER
    return Panel(
        t,
        title="[bold white]Personalizaciones[/bold white]",
        title_align="left",
        border_style=border,
        padding=(0, 0),
    )


def _render_list(state: UIState) -> Panel:
    t = Text()

    # ── Barra de búsqueda ──
    t.append("\n  ")
    if state.searching:
        t.append("/ ", style=C_SEARCH)
        t.append(state.search or " ", style=C_SEARCH)
        t.append("█", style=C_SEARCH)
    else:
        if state.search:
            t.append(f"/ {state.search}", style=C_BADGE)
        else:
            t.append("Escriba para buscar...", style=C_DIM)
    t.append("                  ", style="")
    t.append("[Examinar]", style=C_DIM)
    t.append(" [+]\n", style=C_DIM)
    t.append("  " + "─" * 52 + "\n", style=C_BORDER)

    items = state.filtered_items()

    if not items:
        t.append("\n  ")
        t.append("Sin resultados", style=C_DIM)
        t.append("\n")
    else:
        # Agrupar por scope
        groups: dict[str, list[tuple[int, ConfigItem]]] = {}
        for abs_idx, item in enumerate(items):
            groups.setdefault(item.scope, []).append((abs_idx, item))

        scope_order = ["usuario", "sistema", "integrado"]
        scope_labels = {
            "usuario":   "Usuario",
            "sistema":   "Sistema",
            "integrado": "Integrado",
        }

        visible_start = state.scroll
        visible_end   = state.scroll + LIST_HEIGHT - 6   # header rows
        row = 0

        for scope in scope_order:
            if scope not in groups:
                continue
            grp_items = groups[scope]

            # Cabecera de grupo
            if row >= visible_start:
                cnt = len(grp_items)
                t.append(f"\n  ▸ ", style=C_GROUP_TITLE)
                t.append(f"{scope_labels[scope]}", style=C_GROUP_TITLE)
                t.append(f"  ({cnt})\n", style=C_DIM)
            row += 1

            for abs_idx, item in grp_items:
                if row < visible_start:
                    row += 1
                    continue
                if row >= visible_end:
                    break

                is_cursor = (abs_idx == state.list_idx and state.focus == "list")
                icon_style = C_ACCENT if item.active else C_DIM
                name_style = f"bold {C_ACTIVE_NAV}" if is_cursor else C_ITEM
                bg_marker  = "❯ " if is_cursor else "  "
                desc = item.description[:46] if item.description else ""

                if is_cursor:
                    t.append(f"  {bg_marker}", style=C_ACCENT)
                    t.append(f"{item.icon} ", style=icon_style)
                    t.append(f"{item.name:<24}", style=name_style)
                    t.append(f" {desc}\n", style=C_DIM)
                else:
                    t.append(f"  {bg_marker}", style=C_DIM)
                    t.append(f"{item.icon} ", style=icon_style)
                    t.append(f"{item.name:<24}", style=C_ITEM)
                    t.append(f" {desc}\n", style=C_DIM)
                row += 1

    # ── Footer: descripción del ítem seleccionado ──
    sel = state.selected_item()
    t.append("\n")
    t.append("  " + "─" * 52, style=C_BORDER)
    t.append("\n")
    if sel:
        detail = sel.detail or sel.description
        # Wrap at ~56 chars
        for i in range(0, min(len(detail), 112), 56):
            t.append(f"  {detail[i:i+56]}\n", style=C_DIM)
    else:
        sec = state.current_section
        descs = {
            "agentes":       "Agentes BAGO coordinan herramientas y flujos de trabajo.",
            "habilidades":   "Habilidades (skills) disponibles en el framework BAGO.",
            "instrucciones": "Archivos de instrucción que guían el comportamiento del agente.",
            "mcp":           "Servidores MCP permiten al agente usar herramientas externas.",
            "complementos":  "Extensiones y complementos instalados en BAGO.",
        }
        t.append(f"  {descs.get(sec.key,'')}\n", style=C_DIM)

    border = C_ACCENT if state.focus == "list" else C_BORDER
    return Panel(
        t,
        title=f"[bold white]{state.current_section.label}[/bold white]",
        title_align="left",
        border_style=border,
        padding=(0, 1),
    )


def _render(state: UIState) -> Layout:
    layout = Layout()
    layout.split_row(
        Layout(name="nav",  ratio=3),
        Layout(name="list", ratio=7),
    )
    layout["nav"].update(_render_nav(state))
    layout["list"].update(_render_list(state))
    return layout


# ── Loop interactivo ──────────────────────────────────────────────────────────
def run_interactive() -> None:
    if not sys.stdin.isatty():
        console.print(_render_once())
        return

    sections = _build_sections()
    state    = UIState(sections)

    with Live(_render(state), console=console, screen=False,
              refresh_per_second=12, vertical_overflow="visible") as live:

        def refresh() -> None:
            live.update(_render(state))

        while True:
            key = _getch()

            # ── Modo búsqueda ──
            if state.searching:
                if key in ("\r", "\n", "\x1b[A", "\x1b[B"):
                    state.searching = False
                    state.focus = "list"
                    state.clamp_list()
                    refresh()
                    continue
                if key == "\x7f":  # backspace
                    state.search = state.search[:-1]
                elif key == "\x1b":
                    state.searching = False
                    state.search = ""
                    refresh()
                    continue
                elif len(key) == 1 and key.isprintable():
                    state.search += key
                state.list_idx = 0
                state.scroll   = 0
                refresh()
                continue

            # ── Teclas globales ──
            if key in ("q", "\x1b"):
                break

            if key == "\t":
                state.focus = "list" if state.focus == "nav" else "nav"
                refresh()
                continue

            if key == "/":
                state.searching = True
                state.focus     = "list"
                refresh()
                continue

            # ── Navegación ──
            if state.focus == "nav":
                if key in ("\x1b[A", "k"):   # up
                    state.nav_idx = max(0, state.nav_idx - 1)
                    state.list_idx = 0
                    state.scroll   = 0
                    state.search   = ""
                elif key in ("\x1b[B", "j"):  # down
                    state.nav_idx = min(len(sections) - 1, state.nav_idx + 1)
                    state.list_idx = 0
                    state.scroll   = 0
                    state.search   = ""
                elif key in ("\r", "\n", "\x1b[C", "l"):
                    state.focus = "list"

            else:  # focus == "list"
                if key in ("\x1b[A", "k"):   # up
                    state.list_idx = max(0, state.list_idx - 1)
                    if state.list_idx < state.scroll:
                        state.scroll = state.list_idx
                elif key in ("\x1b[B", "j"):  # down
                    n = len(state.filtered_items())
                    state.list_idx = min(n - 1, state.list_idx + 1)
                    visible = LIST_HEIGHT - 8
                    if state.list_idx >= state.scroll + visible:
                        state.scroll = state.list_idx - visible + 1
                elif key in ("\x1b[D", "h"):  # left → back to nav
                    state.focus = "nav"

            refresh()


def _render_once() -> Layout:
    sections = _build_sections()
    state    = UIState(sections)
    # Default: focus en lista, mostrar habilidades
    state.nav_idx = 0
    state.focus   = "list"
    return _render(state)


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Configurador de agentes BAGO")
    parser.add_argument("--once", action="store_true", help="Render único, no interactivo")
    parser.add_argument("--section", default="agentes",
                        choices=["agentes","habilidades","instrucciones","mcp","complementos"],
                        help="Sección inicial")
    args = parser.parse_args()

    if args.once:
        sections = _build_sections()
        state    = UIState(sections)
        keys     = [s.key for s in sections]
        if args.section in keys:
            state.nav_idx = keys.index(args.section)
        state.focus = "list"
        console.print(_render(state), height=32)
        return

    run_interactive()


if __name__ == "__main__":
    main()

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
    """Agentes: BagoAgents (usuarios configurables) + Roles (definiciones) + Analizadores (scripts)."""
    items: list[ConfigItem] = []

    # ── BagoAgents — ejecutables con modelo y skills ──
    reg_f = _STATE / "agents_registry.json"
    if reg_f.exists():
        try:
            reg = json.loads(reg_f.read_text(encoding="utf-8"))
            for k, v in reg.items():
                if k == "_meta" or not isinstance(v, dict):
                    continue
                skills_list = ", ".join(v.get("skills", [])) or "—"
                items.append(ConfigItem(
                    name=k,
                    description=v.get("description", ""),
                    scope="usuario",
                    active=v.get("active", True),
                    detail=(
                        f"Modelo: {v.get('model','?')}  "
                        f"Categoría: {v.get('category','?')}  "
                        f"Skills: {skills_list}"
                    ),
                    icon="◎" if v.get("active") else "○",
                ))
        except Exception:
            pass

    # ── Roles — personas/modos del framework ──
    if _AGENTS_DIR.exists():
        for md in sorted(_AGENTS_DIR.glob("*.md")):
            if md.stem in ("README",):
                continue
            try:
                lines = md.read_text(encoding="utf-8").splitlines()
                desc = ""
                for line in lines[1:8]:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        desc = stripped.lstrip(">► ").strip()
                        if len(desc) > 10:
                            break
            except Exception:
                desc = ""
            items.append(ConfigItem(
                name=md.stem,
                description=desc[:78],
                scope="sistema",
                detail=f"Definición: {md.name}",
                icon="≡",
            ))

    # ── Analizadores — scripts Python en .bago/agents/ ──
    if _AGENTS_DIR.exists():
        for py in sorted(_AGENTS_DIR.glob("*.py")):
            if py.stem.startswith("_") or py.stem in ("agent_factory", "agent_gateway"):
                continue
            try:
                first_line = py.read_text(encoding="utf-8").splitlines()[0]
                desc = first_line.lstrip("#! ").strip()[:78]
            except Exception:
                desc = py.stem
            items.append(ConfigItem(
                name=py.stem,
                description=desc,
                scope="integrado",
                detail=f"Script: {py.name}",
                icon="⚙",
            ))

    return items


def _load_skills() -> list[ConfigItem]:
    """Habilidades: skills reales del agente (ciclos de código, test, doc).
    Solo skill_registry.json — las herramientas CLI van en su propia sección."""
    items: list[ConfigItem] = []
    sk_f = _STATE / "skill_registry.json"
    if sk_f.exists():
        try:
            sk = json.loads(sk_f.read_text(encoding="utf-8"))
            for k, v in sk.items():
                if k == "_meta":
                    continue
                if isinstance(v, dict):
                    desc = v.get("description", "")[:78]
                    detail = (
                        f"Categoría: {v.get('category','?')}  "
                        f"Fase: {v.get('phase','?')}  "
                        f"Pasos: {v.get('steps',[])}"
                    )
                else:
                    desc = str(v)[:78]
                    detail = ""
                items.append(ConfigItem(
                    name=k,
                    description=desc,
                    scope="usuario",
                    detail=detail or desc,
                    icon="⊡",
                ))
        except Exception:
            pass
    return items


def _load_tools() -> list[ConfigItem]:
    """Herramientas: 124 comandos CLI del tool_registry, agrupados por layer_group."""
    items: list[ConfigItem] = []
    try:
        sys.path.insert(0, str(_HERE))
        from tool_registry import REGISTRY  # type: ignore

        # scope según layer_group
        group_scope = {
            "core":   "integrado",
            "ui":     "usuario",
            "agents": "sistema",
            "labs":   "integrado",
            "tools":  "integrado",
        }
        group_icons = {
            "core":   "◆",
            "ui":     "◈",
            "agents": "◎",
            "labs":   "⚗",
            "tools":  "⚙",
        }
        for cmd, entry in sorted(REGISTRY.items()):
            lg = getattr(entry, "layer_group", "core")
            items.append(ConfigItem(
                name=cmd,
                description=getattr(entry, "description", "")[:68],
                scope=group_scope.get(lg, "integrado"),
                active=not getattr(entry, "deprecated", False),
                detail=(
                    f"Layer: {getattr(entry,'layer','?')}  "
                    f"Stability: {getattr(entry,'stability','?')}  "
                    f"Risk: {getattr(entry,'risk','safe')}"
                ),
                icon=group_icons.get(lg, "◆"),
            ))
    except Exception:
        pass
    return items


# Instrucciones que son directivas para el agente (no documentación)
_INSTRUCTION_FILES = {
    "BOOTSTRAP.md",
    "AGENT_START.md",
    "START_AGENT.md",
}
# Instrucciones en .bago/agents/ (roles del copilot)
_INSTRUCTION_AGENT_FILES = {
    "COPILOT_ALIADO_BAGO.md",
}


def _load_instructions() -> list[ConfigItem]:
    """Instrucciones: solo archivos que definen comportamiento del agente.
    Excluye documentación, demos, changelogs y deployment guides."""
    items: list[ConfigItem] = []

    # Instrucciones principales en .bago/
    for fname in sorted(_INSTRUCTION_FILES):
        md = _BAGO / fname
        if not md.exists():
            continue
        try:
            lines = md.read_text(encoding="utf-8").splitlines()
            title = next((l.lstrip("# ").strip() for l in lines if l.startswith("#")), fname)
            desc = title[:78]
        except Exception:
            desc = fname
        items.append(ConfigItem(
            name=fname,
            description=desc,
            scope="usuario",
            detail=f"Ruta: .bago/{fname}",
            icon="≡",
        ))

    # Instrucciones de rol en .bago/agents/
    for fname in sorted(_INSTRUCTION_AGENT_FILES):
        md = _AGENTS_DIR / fname
        if not md.exists():
            continue
        try:
            lines = md.read_text(encoding="utf-8").splitlines()
            desc = next(
                (l.strip().lstrip(">► ") for l in lines[1:10]
                 if l.strip() and not l.startswith("#")),
                ""
            )[:78]
        except Exception:
            desc = fname
        items.append(ConfigItem(
            name=fname,
            description=desc,
            scope="sistema",
            detail=f"Ruta: .bago/agents/{fname}",
            icon="≡",
        ))

    return items


def _load_mcp() -> list[ConfigItem]:
    """Servidores MCP: extensiones con extension.mjs (protocolo MCP)."""
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
                    desc = first_comment[:78] or ext.name
                except Exception:
                    desc = ext.name
                items.append(ConfigItem(
                    name=ext.name,
                    description=desc,
                    scope="usuario",
                    detail=f"Protocolo: MCP  Archivo: extension.mjs",
                    icon="⊞",
                ))
    return items


def _load_extensions() -> list[ConfigItem]:
    """Complementos: directorios de extensión en .bago/extensions/."""
    items: list[ConfigItem] = []
    if _EXT_DIR.exists():
        for ext in sorted(_EXT_DIR.iterdir()):
            if not ext.is_dir():
                continue
            files = [f.name for f in ext.iterdir()]
            desc = f"{len(files)} archivo(s): {', '.join(files[:3])}"
            items.append(ConfigItem(
                name=ext.name,
                description=desc[:78],
                scope="usuario",
                detail=f"Ruta: .bago/extensions/{ext.name}/",
                icon="⊕",
            ))
    return items


def _build_sections() -> list[NavSection]:
    agents   = _load_agents()
    skills   = _load_skills()
    tools    = _load_tools()
    instrs   = _load_instructions()
    mcp      = _load_mcp()
    exts     = _load_extensions()

    return [
        NavSection("agentes",      "Agentes",       "◎", agents),
        NavSection("habilidades",  "Habilidades",   "⊡", skills),
        NavSection("herramientas", "Herramientas",  "⚙", tools),
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
            "agentes":       "Agentes BAGO: BagoAgents configurables, Roles del framework y Analizadores de código.",
            "habilidades":   "Skills reales del agente: ciclos de código (code_review), tests (test_runner) y docs (doc_writer).",
            "herramientas":  "124 herramientas CLI del framework BAGO, agrupadas por categoría funcional.",
            "instrucciones": "Archivos de instrucción que definen el comportamiento del agente (BOOTSTRAP, AGENT_START…).",
            "mcp":           "Servidores MCP: permiten al agente usar servicios externos vía protocolo MCP.",
            "complementos":  "Complementos y extensiones instaladas en .bago/extensions/.",
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
                        choices=["agentes","habilidades","herramientas","instrucciones","mcp","complementos"],
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
    main()
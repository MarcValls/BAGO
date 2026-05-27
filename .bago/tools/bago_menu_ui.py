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

import curses
import json
import subprocess
import sys

from bago_menu_data import MENU

# ── Restaurar Quick Edit Mode en Windows (curses lo deshabilita) ──────────────
def _restore_windows_quick_edit() -> None:
    """Re-habilitar clic-derecho → pegar en consola Windows bajo curses."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        _k = ctypes.windll.kernel32
        for _handle_id in (-10, -11):  # STD_INPUT, STD_OUTPUT
            _h = _k.GetStdHandle(_handle_id)
            _m = ctypes.c_ulong(0)
            if _k.GetConsoleMode(_h, ctypes.byref(_m)):
                _k.SetConsoleMode(_h, _m.value | 0x0040)  # ENABLE_QUICK_EDIT_MODE
    except Exception:
        pass
# ───────────────────────────────────────────────────────────────────────────────
from bago_menu_loaders import ROOT, STATE, _live_data

SIDEBAR_W = 20
PREVIEW_H = 6

# GAP-1: grupos visibles solo en devmode (hidden from user mode)
_IMPORTANT_CMDS: frozenset[str] = frozenset({
    "launch", "menu", "create", "start", "status", "ideas", "task",
    "next", "done", "setup", "devmode", "workspace-select",
})

_DEV_ONLY_GROUPS: frozenset[str] = frozenset({
    "✅  Calidad & Salud",
    "🔍  Análisis de código",
    "🤖  Agentes & IA",
    "🧠  Campo & Reactor",
    "🛠️  Infraestructura",
})


def _is_devmode() -> bool:
    try:
        gs = json.loads((STATE / "global_state.json").read_text(encoding="utf-8"))
        return bool(gs.get("devmode", False))
    except Exception:
        return False


def _active_menu() -> list:
    """Return MENU filtered by devmode. Dev sees all; user sees user-facing groups only."""
    if _is_devmode():
        return MENU
    return [
        (name, cmds) for name, cmds in MENU
        if name.split("  ", 1)[-1] not in {g.split("  ", 1)[-1] for g in _DEV_ONLY_GROUPS}
        and name not in _DEV_ONLY_GROUPS
    ]


# ── Sub-opciones modal ────────────────────────────────────────────────────────

def _draw_subopts(stdscr: "curses._CursesWindow", cmd: str,
                  opts: list[tuple[str, str, str]]) -> str | None:
    """Modal centrado para elegir sub-opción/flag de un comando.
    opts: [(args_a_añadir, etiqueta_corta, descripción)]
    Devuelve el comando completo elegido o None si se cancela.
    """
    h, w = stdscr.getmaxyx()
    lbl_w = max(len(o[1]) for o in opts) + 2
    title = f" bago {cmd} — elige una opción "
    modal_w = min(max(len(title) + 4, lbl_w + 50), w - 4)
    modal_h = len(opts) + 6
    my = max(1, (h - modal_h) // 2)
    mx = max(1, (w - modal_w) // 2)
    sel = 0

    while True:
        # Fondo semitransparente (sobreescribe área del modal)
        for row in range(my, min(my + modal_h, h - 1)):
            try:
                stdscr.addstr(row, mx, " " * (modal_w - 1), curses.color_pair(6))
            except curses.error:
                pass

        # Borde
        try:
            stdscr.addstr(my, mx, "┌" + title + "─" * max(0, modal_w - len(title) - 2) + "┐",
                          curses.color_pair(4) | curses.A_BOLD)
            for row in range(my + 1, my + modal_h - 1):
                stdscr.addstr(row, mx, "│", curses.color_pair(4))
                stdscr.addstr(row, mx + modal_w - 1, "│", curses.color_pair(4))
            footer_row = my + modal_h - 2
            foot = "  ↑↓ elegir · Enter ejecutar · Esc cancelar"
            stdscr.addstr(footer_row, mx + 1, foot[:modal_w - 2], curses.color_pair(4))
            stdscr.addstr(my + modal_h - 1, mx,
                          "└" + "─" * (modal_w - 2) + "┘", curses.color_pair(4))
        except curses.error:
            pass

        # Opciones
        for i, (args, label, desc) in enumerate(opts):
            row = my + 2 + i
            if row >= my + modal_h - 2:
                break
            full = f"bago {cmd} {args}".strip()
            if i == sel:
                bar = f" ▶  {label:<{lbl_w}}  {desc}"
                try:
                    stdscr.addstr(row, mx + 1, bar[:modal_w - 2].ljust(modal_w - 2),
                                  curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass
            else:
                try:
                    stdscr.addstr(row, mx + 4, f"{label:<{lbl_w}}", curses.color_pair(5))
                    desc_x = mx + 4 + lbl_w + 2
                    stdscr.addstr(row, desc_x, desc[:mx + modal_w - desc_x - 2],
                                  curses.color_pair(2))
                except curses.error:
                    pass

        stdscr.refresh()
        key = stdscr.getch()

        if key == 27:               # Esc → cancelar
            stdscr.touchwin()
            stdscr.refresh()
            return None
        elif key == curses.KEY_DOWN:
            sel = (sel + 1) % len(opts)
        elif key == curses.KEY_UP:
            sel = (sel - 1) % len(opts)
        elif key in (10, 13):       # Enter → ejecutar
            args = opts[sel][0]
            return f"bago {cmd} {args}".strip()


# ── Colores ───────────────────────────────────────────────────────────────────

def _init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    -1)                 # activo / resaltado
    curses.init_pair(2, 8,                    -1)                 # dim
    curses.init_pair(3, curses.COLOR_BLACK,   curses.COLOR_CYAN)  # seleccionado con foco
    curses.init_pair(4, curses.COLOR_YELLOW,  -1)                 # títulos / footer
    curses.init_pair(5, curses.COLOR_GREEN,   -1)                 # nombre de comando
    curses.init_pair(6, curses.COLOR_WHITE,   -1)                 # texto normal
    curses.init_pair(8, curses.COLOR_MAGENTA, -1)                 # preview cmd
    curses.init_pair(9, curses.COLOR_BLACK,   curses.COLOR_YELLOW)# header bar


def _clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


# ── Renderizado TUI ───────────────────────────────────────────────────────────

def _draw(stdscr: "curses._CursesWindow") -> str | None:
    _init_colors()
    curses.curs_set(0)
    _restore_windows_quick_edit()

    # GAP-1: filter menu based on devmode at draw time
    menu = _active_menu()

    active_group = 0
    active_cmd   = 0
    focus        = "sidebar"
    scroll_cmd   = 0
    result: str | None = None
    _prev_key    = None   # (group, cmd_idx) — cache key para live_data
    _cached_live: list[str] = []

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        list_x    = SIDEBAR_W + 1
        list_w    = w - list_x - 1
        list_area = h - PREVIEW_H - 3

        group_name, cmds = menu[active_group]

        # Recarga live_data solo cuando cambia la selección
        _cur_key = (active_group, active_cmd)
        if _cur_key != _prev_key and 0 <= active_cmd < len(cmds):
            entry = cmds[active_cmd]
            _cached_live = _live_data(entry[0], entry[2])
            _prev_key = _cur_key

        # ── Header ───────────────────────────────────────────────────────────
        mode_tag = " DEV" if _is_devmode() else " USR"
        right = f"{mode_tag} · {active_group + 1}/{len(menu)} · {group_name.split('  ', 1)[-1]} "
        stdscr.addstr(0, 0, " " * (w - 1), curses.color_pair(9))
        stdscr.addstr(0, 2, "BAGO", curses.color_pair(9) | curses.A_BOLD)
        stdscr.addstr(0, 7, "· Menú de Comandos", curses.color_pair(9))
        try:
            stdscr.addstr(0, w - len(right) - 1, right, curses.color_pair(9))
        except curses.error:
            pass

        # ── Sidebar de grupos ─────────────────────────────────────────────────
        for i, (gname, _) in enumerate(menu):
            y = 2 + i
            if y >= h - PREVIEW_H - 2:
                break
            label = f" {gname}"[:SIDEBAR_W].ljust(SIDEBAR_W)
            if i == active_group:
                attr = (curses.color_pair(3) | curses.A_BOLD) if focus == "sidebar" else (curses.color_pair(1) | curses.A_BOLD)
                stdscr.addstr(y, 0, label, attr)
            else:
                stdscr.addstr(y, 0, label, curses.color_pair(2))

        # Separador vertical
        for y in range(1, h - 1):
            try:
                stdscr.addstr(y, SIDEBAR_W, "│", curses.color_pair(2))
            except curses.error:
                pass

        # ── Cabecera de lista ─────────────────────────────────────────────────
        gname_clean = group_name.split("  ", 1)[-1] if "  " in group_name else group_name
        stdscr.addstr(1, list_x, f" {gname_clean}  ({len(cmds)} comandos)"[:list_w], curses.color_pair(4) | curses.A_BOLD)
        stdscr.addstr(2, list_x, "─" * (list_w - 1), curses.color_pair(2))

        # ── Lista de comandos ─────────────────────────────────────────────────
        visible = cmds[scroll_cmd: scroll_cmd + list_area]
        for i, entry in enumerate(visible):
            cmd, short = entry[0], entry[1]
            abs_i = scroll_cmd + i
            y = 3 + i
            if y >= h - PREVIEW_H - 1:
                break
            if abs_i == active_cmd and focus == "list":
                bar = f" ▶  bago {cmd}  ─  {short}"
                stdscr.addstr(y, list_x, bar[:list_w].ljust(list_w - 1), curses.color_pair(3) | curses.A_BOLD)
            elif abs_i == active_cmd:
                stdscr.addstr(y, list_x + 1, "▶ ", curses.color_pair(1))
                stdscr.addstr(y, list_x + 3, f"bago {cmd}", curses.color_pair(1) | curses.A_BOLD)
                desc_x = list_x + 3 + len(f"bago {cmd}") + 2
                if desc_x < w - 2:
                    stdscr.addstr(y, desc_x, short[:w - desc_x - 1], curses.color_pair(6))
            else:
                cmd_color = curses.color_pair(1) if cmd in _IMPORTANT_CMDS else curses.color_pair(5)
                stdscr.addstr(y, list_x + 3, "bago ", curses.color_pair(2))
                stdscr.addstr(y, list_x + 8, cmd, cmd_color | curses.A_BOLD if cmd in _IMPORTANT_CMDS else cmd_color)
                desc_x = list_x + 8 + len(cmd) + 2
                if desc_x < w - 2:
                    stdscr.addstr(y, desc_x, short[:w - desc_x - 1], curses.color_pair(2))

        # Indicadores de scroll
        if scroll_cmd > 0:
            try:
                stdscr.addstr(3, w - 3, "↑", curses.color_pair(4))
            except curses.error:
                pass
        if scroll_cmd + list_area < len(cmds):
            try:
                stdscr.addstr(2 + list_area, w - 3, "↓", curses.color_pair(4))
            except curses.error:
                pass

        # ── Preview del comando seleccionado ──────────────────────────────────
        prev_y = h - PREVIEW_H - 1
        stdscr.addstr(prev_y, list_x, "─" * (list_w - 1), curses.color_pair(2))
        if 0 <= active_cmd < len(cmds):
            entry = cmds[active_cmd]
            cmd_name = entry[0]
            has_opts = len(entry) > 3 and entry[3]
            opts_hint = "  [opciones ▸]" if has_opts else ""
            stdscr.addstr(prev_y + 1, list_x + 1,
                          f"bago {cmd_name}{opts_hint}"[:list_w - 2],
                          curses.color_pair(8) | curses.A_BOLD)
            for li, ln in enumerate(_cached_live[:PREVIEW_H - 2]):
                try:
                    stdscr.addstr(prev_y + 2 + li, list_x + 1, ln[:list_w - 2], curses.color_pair(6))
                except curses.error:
                    pass

        # ── Footer ────────────────────────────────────────────────────────────
        footer = "  ↑↓ navegar  →/Tab: lista  ←: grupos  Enter: ejecutar  q: salir  "
        stdscr.addstr(h - 1, 0, footer[:w - 1], curses.color_pair(4))

        stdscr.refresh()

        # ── Input ─────────────────────────────────────────────────────────────
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif key == 27:  # ESC: go back one level, don't quit
            if focus == "list":
                focus = "sidebar"
            else:
                break
        elif focus == "sidebar":
            if key == curses.KEY_DOWN:
                active_group = (active_group + 1) % len(menu)
                active_cmd = 0
                scroll_cmd = 0
            elif key == curses.KEY_UP:
                active_group = (active_group - 1) % len(menu)
                active_cmd = 0
                scroll_cmd = 0
            elif key in (ord('\t'), curses.KEY_RIGHT, 10, 13):
                focus = "list"
        else:
            if key == curses.KEY_DOWN:
                active_cmd = _clamp(active_cmd + 1, 0, len(cmds) - 1)
                if active_cmd >= scroll_cmd + list_area:
                    scroll_cmd += 1
            elif key == curses.KEY_UP:
                active_cmd = _clamp(active_cmd - 1, 0, len(cmds) - 1)
                if active_cmd < scroll_cmd:
                    scroll_cmd -= 1
            elif key == curses.KEY_LEFT:
                focus = "sidebar"
            elif key == ord('\t'):
                active_group = (active_group + 1) % len(menu)
                active_cmd = 0
                scroll_cmd = 0
                focus = "list"
            elif key in (10, 13):
                entry = cmds[active_cmd]
                cmd_name = entry[0]
                opts = entry[3] if len(entry) > 3 else None
                if opts:
                    chosen = _draw_subopts(stdscr, cmd_name, opts)
                    if chosen:
                        result = chosen
                        break
                    # Esc en modal → volver al menú sin ejecutar
                else:
                    result = f"bago {cmd_name}"
                    break

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


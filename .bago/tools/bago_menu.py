from __future__ import annotations

import curses
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from bago_menu_data import MENU
from bago_menu_loaders import ROOT, STATE, _LIVE_LOADERS, _live_data
from bago_menu_ui import _active_menu, _draw


# ── Modo --list (no interactivo) ──────────────────────────────────────────────

def _cmd_list() -> int:
    use_color = sys.stdout.isatty()

    def c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if use_color else text

    # GAP-1: filter by devmode
    effective_menu = _active_menu()
    for group_name, cmds in effective_menu:
        print()
        print(c("1;33", f"  {group_name}"))
        print(c("2", "  " + "─" * 52))
        for cmd, short, *_ in cmds:
            print(f"  {c('1;32', f'bago {cmd}'):<35}  {c('2', short)}")
    print()
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def _startup_sequence() -> None:
    """Arranque mínimo antes del menú: workspace_selector + record_project.

    GAP-2: En user mode con workspace='self', añade hint para configurar
    un proyecto externo, pero no bloquea el arranque.
    """
    tools = Path(__file__).parent
    try:
        import importlib.util as ilu

        def _load(name: str):
            spec = ilu.spec_from_file_location(name, tools / f"{name}.py")
            mod = ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

        ws = _load("workspace_selector")
        ctx = ws._load_context()
        devmode = _is_devmode()

        # GAP-2: user mode with workspace pointing at framework → show hint
        if not devmode and ctx.get("working_mode") == "self":
            print("\n  💡  Workspace activo: framework BAGO (self)")
            print("  Para trabajar en un proyecto externo: bago workspace-select\n")
            ws.select(skip_if_set=False)   # let them re-choose
        else:
            ws.select(skip_if_set=True)

        rp = _load("recent_projects")
        rp.record_project()
    except Exception:
        pass  # Nunca bloquear el arranque del menú


def _is_devmode() -> bool:
    """Read devmode from global_state.json."""
    try:
        gs = (STATE / "global_state.json")
        return bool(__import__("json").loads(gs.read_text(encoding="utf-8")).get("devmode", False))
    except Exception:
        return False


def main() -> None:
    args = sys.argv[1:]

    if "--list" in args:
        sys.exit(_cmd_list())

    if not sys.stdout.isatty():
        print("bago menu requiere un terminal interactivo. Usa --list para salida de texto.")
        sys.exit(1)

    _startup_sequence()

    # ── Elección de modo: manual vs asistente ──────────────────────────────
    import importlib.util as _ilu
    _chat_mod = None
    try:
        _spec = _ilu.spec_from_file_location("bago_chat", Path(__file__).parent / "bago_chat.py")
        _chat_mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_chat_mod)
    except Exception:
        pass

    # GAP-3: loop so ESC from chat returns to M/A choice
    while True:
        choice = "manual"
        if _chat_mod:
            try:
                choice = curses.wrapper(_chat_mod._startup_choice_curses)
            except Exception:
                choice = "manual"

        if choice == "asistente" and _chat_mod:
            try:
                result = curses.wrapper(_chat_mod._chat_curses)
            except Exception:
                result = None
            if result == "back":
                continue   # re-show M/A choice
            sys.exit(0)

        # Manual mode
        break

    result = curses.wrapper(_draw)

    if result:
        print(f"\n  ▶  {result}\n")
        bago_script = ROOT / "bago"
        cmd_parts = result.split()[1:]
        if bago_script.exists():
            sys.exit(subprocess.run([sys.executable, str(bago_script)] + cmd_parts).returncode)
    else:
        sys.exit(0)


def _self_test() -> None:
    assert len(MENU) == 10, f"Se esperaban 10 grupos, hay {len(MENU)}"
    for group_name, cmds in MENU:
        assert cmds, f"Grupo '{group_name}' sin comandos"
        for entry in cmds:
            assert len(entry) in (3, 4), f"Entrada malformada en '{group_name}': {entry}"
            if len(entry) == 4 and entry[3]:
                for opt in entry[3]:
                    assert len(opt) == 3, f"Sub-opción malformada en '{entry[0]}': {opt}"
    total = sum(len(c) for _, c in MENU)
    opts_count = sum(1 for _, c in MENU for e in c if len(e) > 3 and e[3])
    print(f"  3/3 tests pasaron  ({len(MENU)} grupos, {total} entradas, {opts_count} con sub-opciones)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()

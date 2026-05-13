from __future__ import annotations

import curses
import importlib.util
import subprocess
import sys
from pathlib import Path

from bago_menu_data import MENU
from bago_menu_loaders import ROOT, STATE, _LIVE_LOADERS, _live_data
from bago_menu_ui import _draw


# ── Modo --list (no interactivo) ──────────────────────────────────────────────

def _cmd_list() -> int:
    use_color = sys.stdout.isatty()

    def c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if use_color else text

    for group_name, cmds in MENU:
        print()
        print(c("1;33", f"  {group_name}"))
        print(c("2", "  " + "─" * 52))
        for cmd, short, _ in cmds:
            print(f"  {c('1;32', f'bago {cmd}'):<35}  {c('2', short)}")
    print()
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def _startup_sequence() -> None:
    """Ejecuta el arranque mínimo antes de mostrar el menú:
    - workspace_selector: elige modo si no está ya configurado
    - record_project: registra este proyecto como reciente
    Solo en TTY interactivo; silencioso si los módulos no están disponibles.
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
        ws.select(skip_if_set=True)

        rp = _load("recent_projects")
        rp.record_project()
    except Exception:
        pass  # Nunca bloquear el arranque del menú


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

    choice = "manual"
    if _chat_mod:
        try:
            choice = curses.wrapper(_chat_mod._startup_choice_curses)
        except Exception:
            choice = "manual"

    if choice == "asistente" and _chat_mod:
        try:
            curses.wrapper(_chat_mod._chat_curses)
        except Exception:
            pass
        sys.exit(0)

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

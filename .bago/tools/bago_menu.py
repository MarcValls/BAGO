from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from bago_menu_data import MENU
from bago_menu_loaders import ROOT, STATE, _LIVE_LOADERS, _live_data


_DEV_ONLY_GROUPS: frozenset[str] = frozenset({
    "✅  Calidad & Salud",
    "🔍  Análisis de código",
    "🤖  Agentes & IA",
    "🧠  Campo & Reactor",
    "🛠️  Infraestructura",
})


def _active_menu() -> list:
    """Return MENU filtered by devmode without importing curses UI helpers."""
    try:
        gs = json.loads((STATE / "global_state.json").read_text(encoding="utf-8"))
        if bool(gs.get("devmode", False)):
            return MENU
    except Exception:
        pass
    hidden = {g.split("  ", 1)[-1] for g in _DEV_ONLY_GROUPS}
    return [
        (name, cmds) for name, cmds in MENU
        if name.split("  ", 1)[-1] not in hidden and name not in _DEV_ONLY_GROUPS
    ]


# ── Modo --list (no interactivo) ──────────────────────────────────────────────

def _cmd_list() -> int:
    use_color = sys.stdout.isatty()

    def c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if use_color else text

    def dim(t: str) -> str:  return c("2", t)
    def bold(t: str) -> str: return c("1", t)
    def grn(t: str) -> str:  return c("1;32", t)
    def cyn(t: str) -> str:  return c("1;36", t)
    def yel(t: str) -> str:  return c("1;33", t)
    def mag(t: str) -> str:  return c("35", t)

    effective_menu = _active_menu()
    for group_name, cmds in effective_menu:
        print()
        print(yel(f"  {group_name}"))
        print(dim("  " + "─" * 56))
        for entry in cmds:
            cmd, short = entry[0], entry[1]
            long_desc  = entry[2] if len(entry) > 2 else ""
            has_opts   = len(entry) > 3 and entry[3]
            opts_hint  = dim("  [+opciones]") if has_opts else ""
            # Para agentes, extraer shortcut si está en el descriptor largo
            shortcut = ""
            if "Shortcuts:" in long_desc:
                sc_part = long_desc.split("Shortcuts:")[-1].strip()
                shortcut = "  " + mag(sc_part.split(".")[0].strip())
            print(f"  {grn(f'bago {cmd}'):<36}{dim(short)}{shortcut}{opts_hint}")
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

    try:
        import curses
    except ModuleNotFoundError:
        print("bago menu requiere curses, no disponible en este Python de Windows.")
        print("Usa `bago menu --list` o instala windows-curses en el entorno de BAGO.")
        sys.exit(1)

    from bago_menu_ui import _draw

    if not sys.stdout.isatty():
        # Modo no-interactivo: banner + catálogo completo
        banner = Path(__file__).parent / "bago_banner.py"
        if banner.exists():
            subprocess.run([sys.executable, str(banner), "--mini"])
        _cmd_list()
        sys.exit(0)

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
    assert len(MENU) == 11, f"Se esperaban 11 grupos, hay {len(MENU)}"
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

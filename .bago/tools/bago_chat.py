
#!/usr/bin/env python3
"""BAGO Orchestrator HUB — Entry point"""
import argparse, sys
from pathlib import Path

# ── Activar VT/ANSI en Windows CMD lo antes posible ──────────────────────────
if sys.platform == "win32":
    try:
        import ctypes as _ct
        _k = _ct.windll.kernel32
        _h = _k.GetStdHandle(-11)
        _m = _ct.c_ulong(0)
        if _k.GetConsoleMode(_h, _ct.byref(_m)):
            _k.SetConsoleMode(_h, _m.value | 0x0004)
    except Exception:
        pass
# ─────────────────────────────────────────────────────────────────────────────

from rich import box
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).parent))

from bago import (CredentialManager, load_providers, load_routing,
                  BagoSession, cmd, chat, console, pi, pe, banner, CtrlCGuard)
from bago.constants import BAGO_SYSTEM, USER_BAGO, BAGO_DIR
from bago.providers import auto_detect_provider, get_default_model, route_by_task
from bago.ui import show_response

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText, HTML
    from prompt_toolkit.key_binding import KeyBindings
except ImportError as e:
    print(f"ERROR: {e}"); sys.exit(1)

from bago.completer import BagoCompleter
import shutil as _shutil

import time as _time

# ── Rutas para la barra de estado ─────────────────────────────────────────────
_FW_ROOT = str(BAGO_DIR.parent)   # repo root: C:\...\BAGO

# Frames de la avispa asiática ASCII para la barra (alterna al refrescar el prompt)
_BEE_FRAMES = [">≡ᗑ≡< ", ">─ᗑ─< ", ">≡ᗑ≡< ", ">=ᗑ=< "]

def _bee_tick() -> str:
    """Frame actual de la abeja según el tiempo (cambia cada ~0.5s)."""
    return _BEE_FRAMES[int(_time.monotonic() * 2) % len(_BEE_FRAMES)]

def _topbar_prompt(route_mode: str) -> FormattedText:
    """Barra de estado superior: abeja animada + ◆ BAGO + path + cwd."""
    cols = _shutil.get_terminal_size((80, 24)).columns
    cwd  = Path.cwd()
    bee  = _bee_tick()
    # Avispa ASCII + badge: todos caracteres simples (ancho 1 cada uno)
    badge = f"{bee}◆ BAGO"
    sep   = "  │  "
    left  = f" {badge}{sep}{_FW_ROOT}"
    left_display_w = len(left)          # todos char ancho 1, sin corrección
    right_full  = f"{cwd.name}  ·  {cwd}  "
    right_short = f"{cwd.name}  "
    right = right_full if left_display_w + len(right_full) + 2 <= cols else right_short
    pad = max(1, cols - left_display_w - len(right))
    bar = (left + " " * pad + right)[:cols]
    return FormattedText([
        ("class:statusbar", bar),
        ("", "\n"),
        ("class:prompt", f"[BAGO|{route_mode}] > "),
    ])

def _bottom_bar() -> list:
    cols = _shutil.get_terminal_size((80, 24)).columns
    return [("class:statusbar", "─" * cols)]

def _startup_choice_curses(stdscr):
    """Curses UI: lets user choose Manual or Asistente mode. Returns 'manual' or 'asistente'."""
    import curses
    curses.curs_set(0)
    stdscr.clear()
    choices = ["Manual (bago menu)", "Asistente BAGO (chat IA)"]
    sel = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        title = "BAGO — Elige modo"
        stdscr.addstr(2, max(0, (w - len(title)) // 2), title, curses.A_BOLD)
        for i, c in enumerate(choices):
            attr = curses.A_REVERSE if i == sel else curses.A_NORMAL
            stdscr.addstr(4 + i, max(0, (w - len(c)) // 2), c, attr)
        stdscr.addstr(h - 2, 2, "↑↓ Mover  Enter Seleccionar  q Salir", curses.A_DIM)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')) and sel > 0:
            sel -= 1
        elif key in (curses.KEY_DOWN, ord('j')) and sel < len(choices) - 1:
            sel += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            return "asistente" if sel == 1 else "manual"
        elif key in (ord('q'), 27):
            return "manual"


def _chat_curses(stdscr):
    """Launches the prompt_toolkit REPL from inside a curses context. Returns None or 'back'."""
    import curses
    curses.endwin()   # Release curses so prompt_toolkit can take over the terminal
    try:
        main()
    except SystemExit:
        pass
    return None


def _prompt_indicator(session) -> str:
    """
    Construye el indicador de modo que aparece en el prompt.

    Lógica de prioridad:
      1. Si el último mensaje fue enrutado (chain/ensemble/single con motivo)
         → muestra ese modo en mayúsculas
      2. Si autoroute está ON pero aún no hay routing (arranque)
         → muestra AUTO
      3. Si autoroute está OFF
         → muestra MANUAL

    Extras que se añaden al final:
      · A  = modo autónomo activo
    """
    last = session.last_route or {}
    last_mode = last.get("mode", "")

    if last_mode and last_mode != "manual":
        # Un routing real ocurrió: CHAIN, ENSEMBLE, SINGLE...
        indicator = last_mode.upper()
    elif session.autoroute:
        indicator = "AUTO"
    else:
        indicator = "MANUAL"

    if session.autonomous:
        indicator += ":A"   # :A = Autónomo

    return indicator


def main():
    p = argparse.ArgumentParser(description="BAGO Orchestrator HUB")
    p.add_argument("--provider", default="")
    p.add_argument("--model", default="")
    p.add_argument("--task",  default="")
    args = p.parse_args()

    creds     = CredentialManager()
    providers = load_providers()
    routing   = load_routing()

    if args.model:
        # Modelo explicito
        name, wire, prov = None, None, args.provider or "codex"
        for pn, pd in providers.items():
            if args.model in pd.get("models", {}):
                name, wire, prov = args.model, pd["models"][args.model].get("wire_name", args.model), pn
                break
        if not name:
            console.print(f"[red]Modelo '{args.model}' no encontrado.[/red]"); sys.exit(1)
    elif args.task:
        name, wire, prov, _ = route_by_task(args.task, routing, providers)
        pi(f"Router BAGO → {name} ({prov}) para: {args.task}")
    else:
        pm = {"copilot":"copilot","codex":"codex","ollama":"ollama-local",
              "ollama-local":"ollama-local","ollama-cloud":"ollama-cloud","anthropic":"anthropic"}
        chosen = pm.get(args.provider, "") or auto_detect_provider(creds, providers)
        if not args.provider:
            pi(f"Provider detectado: {chosen}")
        name, wire, prov = get_default_model(chosen, providers)
        if not name:
            # Ningun provider activo — pedir login
            console.print(Panel(
                "[bold yellow]No hay providers activos.[/bold yellow]\n"
                "Usa [yellow]/login github[/yellow] para Copilot, "
                "[yellow]/login openai[/yellow] para GPT, "
                "[yellow]/login anthropic[/yellow] para Claude, "
                "[yellow]/login ollama[/yellow] para local.",
                title="BAGO — Login requerido", box=box.ROUNDED, border_style="yellow"))
            # Abrir el chat igualmente para que puedan hacer /login
            name, wire, prov = "sin-modelo", "sin-modelo", "none"

    session = BagoSession(prov, name, wire, creds)

    # ── Animación de inicio estilo Copilot ────────────────────────────────────
    if sys.stdout.isatty():
        try:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(
                "bago_intro", Path(__file__).parent / "bago_intro.py")
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _mod.play()
        except Exception:
            pass   # si falla, continúa sin animación

    banner(session)

    hist_file = USER_BAGO / "state" / "chat_input_history.txt"
    hist_file.parent.mkdir(parents=True, exist_ok=True)

    # Estilo del popup de autocompletado
    completion_style = Style.from_dict({
        "prompt":                  "bold cyan",
        # barras superior e inferior — alto contraste
        "statusbar":               "bg:#1e2a3a #7aa2f7 bold",
        "bottom-toolbar":          "bg:#1e2a3a #7aa2f7",
        # popup autocompletado
        "completion-menu":                  "bg:#1a1a2e #e0e0e0",
        "completion-menu.completion":       "bg:#1a1a2e #e0e0e0",
        "completion-menu.completion.current": "bg:#00aaff #000000 bold",
        "completion-menu.meta":             "bg:#111133 #888888",
        "completion-menu.meta.completion.current": "bg:#0055aa #cccccc",
        "scrollbar.background":             "bg:#1a1a2e",
        "scrollbar.button":                 "bg:#00aaff",
    })

    # Key binding: Tab para abrir completado incluso con buffer vacío (solo '/')
    kb = KeyBindings()

    pt = PromptSession(
        history=FileHistory(str(hist_file)),
        auto_suggest=AutoSuggestFromHistory(),
        style=completion_style,
        completer=BagoCompleter(),
        complete_while_typing=True,   # popup aparece al escribir '/'
        key_bindings=kb,
    )

    ctrl_c = CtrlCGuard()
    while True:
        try:
            route_mode = _prompt_indicator(session)
            line = pt.prompt(
                message=lambda: _topbar_prompt(_prompt_indicator(session)),
                bottom_toolbar=_bottom_bar,
            ).strip()
        except EOFError:
            console.print("\n[dim]BAGO terminado.[/dim]"); break
        except KeyboardInterrupt:
            if ctrl_c.press():
                console.print("[dim]BAGO terminado.[/dim]")
                break
            continue
        if not line: continue
        if line.startswith("/"):
            if not cmd(line, session): break
            continue
        try:
            result = chat(session, line)
            if result:   # None = ya mostrado por chain/ensemble
                show_response(result, session.model_name, session.provider)
        except RuntimeError as e:
            pe(str(e))
            console.print("[dim]  Prueba /login para registrar providers o /switch para cambiar modelo.[/dim]")

if __name__ == "__main__":
    main()

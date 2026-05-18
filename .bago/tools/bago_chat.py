
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
from bago.providers import auto_detect_provider, get_default_model, route_by_task, ollama_probe, ollama_pull, scan_provider_health, discover_ollama_url
from bago.llm import (_is_ollama_model_not_found, _is_ollama_unreachable,
                      _is_cloud_auth_error, _is_cloud_connection_error,
                      OllamaNoModelAvailable)
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
_BEE_FRAMES = ["╱◉╲ ", "─◉─ ", "╲◉╱ ", "─◉─ "]

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
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN,  -1)          # title / badge
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)   # selected row
        curses.init_pair(3, curses.COLOR_WHITE, -1)           # normal row
        curses.init_pair(4, curses.COLOR_BLACK, -1)           # dim / border

    choices = [
        ("manual",     "  ⚙  Manual      bago menu",     "Navega el menú interactivo"),
        ("asistente",  "  🤖  Asistente   chat IA",       "Habla directamente con BAGO"),
    ]
    sel = 0

    BOX_W = 46

    def draw():
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        cx = max(0, (w - BOX_W) // 2)
        cy = max(0, (h - 10) // 2)

        # ── Badge BAGO ────────────────────────────────────────────
        badge = "◆ BAGO — Elige modo de inicio"
        bx = max(0, (w - len(badge)) // 2)
        if curses.has_colors():
            stdscr.addstr(cy, bx, badge, curses.color_pair(1) | curses.A_BOLD)
        else:
            stdscr.addstr(cy, bx, badge, curses.A_BOLD)

        # ── Box border ────────────────────────────────────────────
        border_attr = curses.color_pair(4) if curses.has_colors() else curses.A_DIM
        top_line = "┌" + "─" * (BOX_W - 2) + "┐"
        bot_line = "└" + "─" * (BOX_W - 2) + "┘"
        try:
            stdscr.addstr(cy + 2, cx, top_line, border_attr)
            for row in range(len(choices) * 2 + 1):
                stdscr.addstr(cy + 3 + row, cx, "│" + " " * (BOX_W - 2) + "│", border_attr)
            stdscr.addstr(cy + 3 + len(choices) * 2 + 1, cx, bot_line, border_attr)
        except curses.error:
            pass

        # ── Choices ───────────────────────────────────────────────
        for i, (key, label, hint) in enumerate(choices):
            row_y = cy + 3 + i * 2 + 1
            if i == sel:
                attr = curses.color_pair(2) | curses.A_BOLD if curses.has_colors() else curses.A_REVERSE | curses.A_BOLD
                marker = "▶"
            else:
                attr = curses.color_pair(3) if curses.has_colors() else curses.A_NORMAL
                marker = " "
            try:
                entry = f" {marker} {label:<{BOX_W - 6}} "
                stdscr.addstr(row_y, cx + 1, entry[:BOX_W - 2], attr)
            except curses.error:
                pass
            # Hint below
            hint_attr = curses.color_pair(4) if curses.has_colors() else curses.A_DIM
            try:
                stdscr.addstr(row_y + 1, cx + 5, hint, hint_attr)
            except curses.error:
                pass

        # ── Footer ────────────────────────────────────────────────
        footer = " ↑/↓  Mover    Enter  Confirmar    q  Salir "
        fy = min(h - 1, cy + 3 + len(choices) * 2 + 3)
        fx = max(0, (w - len(footer)) // 2)
        hint_attr = curses.color_pair(4) if curses.has_colors() else curses.A_DIM
        try:
            stdscr.addstr(fy, fx, footer, hint_attr)
        except curses.error:
            pass

        stdscr.refresh()

    while True:
        draw()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')) and sel > 0:
            sel -= 1
        elif key in (curses.KEY_DOWN, ord('j')) and sel < len(choices) - 1:
            sel += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            return choices[sel][0]
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


# ── Flujo de recuperación Ollama ───────────────────────────────────────────────

def _ollama_recovery_flow(session, model_name: str) -> bool:
    """Recuperación interactiva cuando Ollama no tiene el modelo o no está activo.

    Retorna True si la sesión queda lista para reintentar la llamada LLM.
    """
    from bago.ui import _menu_select, _menu_input
    from bago.menus.auth import _cmd_login

    # ── 1. Probar Ollama ───────────────────────────────────────────────────────
    base_url = "http://127.0.0.1:11434"
    probe = ollama_probe(base_url)

    if not probe["running"]:
        console.print(
            f"\n  [yellow]⚠  Ollama no responde en [bold]{base_url}[/bold][/yellow]"
        )
        choices = [
            ("custom_url", "Sí — introduzco la URL donde está corriendo"),
            ("install",    "No — quiero arrancar / instalar Ollama"),
            ("other",      "Usar otro provider"),
        ]
        sel = _menu_select(
            "Ollama inaccesible",
            "¿Sabes si Ollama está instalado en una URL diferente?",
            choices,
        )

        if sel == "custom_url":
            url = _menu_input(
                "URL de Ollama",
                "Introduce la URL base de Ollama:",
                default="http://localhost:11434",
            )
            if url:
                probe2 = ollama_probe(url.strip())
                if probe2["running"]:
                    base_url = url.strip()
                    probe = probe2
                    console.print(f"  [green]✔ Ollama encontrado en {base_url}[/green]")
                    # Ollama accesible: limpiar exclusión
                    session.skip_providers.discard("ollama-local")
                    session.skip_providers.discard("ollama-cloud")
                else:
                    pe(f"No se pudo conectar a Ollama en {url}")
                    sel = "other"
            else:
                sel = "other"

        if sel == "install":
            console.print(
                "\n  [cyan]Para instalar Ollama visita:[/cyan] https://ollama.com/download\n"
                "  Una vez instalado, ejecuta en otra terminal:\n"
                f"    [bold]ollama serve[/bold]\n"
                f"    [bold]ollama pull {model_name or 'qwen2.5-coder:7b'}[/bold]\n"
                "  Luego vuelve a BAGO y escribe tu mensaje.\n"
            )
            return False

        if sel == "other" or not probe["running"]:
            return _fallback_to_other_provider(session)

    # ── 2. Ollama activo: ver qué modelos hay ──────────────────────────────────
    available = probe["models"]

    if not model_name:
        model_name = session.wire_name or "qwen2.5-coder:7b"

    # Modelo ya disponible (puede que la prueba anterior lo cargó)
    if any(model_name in m or m.startswith(model_name.split(":")[0]) for m in available):
        console.print(f"  [green]✔ Modelo '{model_name}' encontrado. Reintentando...[/green]")
        return True

    if available:
        console.print(
            f"\n  [yellow]⚠  Modelo [bold]{model_name}[/bold] no instalado.[/yellow]\n"
            f"  Modelos disponibles en Ollama: [cyan]{', '.join(available[:8])}[/cyan]"
        )
        choices_rows = [(m, m) for m in available[:8]]
        choices_rows += [
            ("install", f"Instalar '{model_name}' ahora  (ollama pull)"),
            ("other",   "Usar otro provider"),
        ]
        sel = _menu_select(
            "Modelo no encontrado",
            f"¿Qué hacemos con '{model_name}'?",
            choices_rows,
        )
        if sel == "install":
            return _do_ollama_pull(model_name, base_url, session)
        elif sel == "other":
            return _fallback_to_other_provider(session)
        else:
            # Cambiar al modelo seleccionado
            pi(f"Cambiando a {sel}...")
            session.wire_name = sel
            session.model_name = sel.split(":")[0]
            return True
    else:
        # Ollama activo pero vacío
        console.print(
            f"\n  [yellow]⚠  Ollama está activo pero no tiene modelos instalados.[/yellow]"
        )
        choices = [
            ("install", f"Instalar '{model_name}'  (ollama pull)"),
            ("other",   "Usar otro provider"),
        ]
        sel = _menu_select(
            "Sin modelos en Ollama",
            "¿Qué deseas hacer?",
            choices,
        )
        if sel == "install":
            return _do_ollama_pull(model_name, base_url, session)
        return _fallback_to_other_provider(session)


def _do_ollama_pull(model_name: str, base_url: str, session) -> bool:
    """Descarga el modelo y, si tiene éxito, actualiza la sesión."""
    console.print(f"\n  [cyan]⬇  Descargando [bold]{model_name}[/bold]...[/cyan]\n")
    ok = ollama_pull(model_name, base_url)
    if ok:
        console.print(f"\n  [green]✔ Modelo '{model_name}' instalado correctamente.[/green]")
        session.wire_name = model_name
        # Ollama vuelve a estar disponible: limpiar exclusión
        session.skip_providers.discard("ollama-local")
        session.skip_providers.discard("ollama-cloud")
        return True
    else:
        pe(f"No se pudo instalar '{model_name}'.")
        return _fallback_to_other_provider(session)


def _fallback_to_other_provider(session) -> bool:
    """Si hay otros providers activos, cambia; si no, redirige a /login."""
    from bago.menus.auth import _cmd_login

    # Marcar Ollama como no disponible para que autoroute no vuelva a él
    session.skip_providers.update({"ollama-local", "ollama-cloud"})

    active = session.creds.active_bago_providers()
    other = [p for p in active if p not in ("ollama-local", "ollama-cloud")]

    if other:
        prov = other[0]
        from bago.providers import get_default_model
        name, wire, _ = get_default_model(prov, session.providers)
        if name:
            old = session.model_name
            session.provider, session.model_name, session.wire_name = prov, name, wire
            pi(f"Cambiando a {name} ({prov}) — el modelo Ollama no está disponible.")
            return True

    console.print(
        "\n  [yellow]No hay providers alternativos activos.[/yellow]\n"
        "  Abriendo pantalla de registro de providers...\n"
    )
    _cmd_login(session)
    return False


def _cloud_recovery_flow(session, exc) -> bool:
    """Recovery para errores de autenticación o conexión en providers cloud.

    Muestra el motivo, marca el provider como no disponible y
    intenta cambiar a otro; si no hay ninguno, abre /login.
    Retorna True si la sesión queda lista para reintentar.
    """
    from bago.menus.auth import _cmd_login

    prov = session.provider
    if _is_cloud_auth_error(exc):
        console.print(
            f"\n  [yellow]⚠  Autenticación fallida en [bold]{prov}[/bold][/yellow]\n"
            f"  Token inválido o expirado. Ejecuta [cyan]/login {prov}[/cyan] para renovar."
        )
    else:
        console.print(
            f"\n  [yellow]⚠  Sin conexión con [bold]{prov}[/bold][/yellow]\n"
            f"  Comprueba tu acceso a internet o el estado del servicio."
        )

    # Excluir el provider actual del routing
    session.skip_providers.add(prov)

    active = session.creds.active_bago_providers()
    other = [p for p in active if p not in session.skip_providers]

    if other:
        new_prov = other[0]
        from bago.providers import get_default_model
        name, wire, _ = get_default_model(new_prov, session.providers)
        if name:
            session.provider, session.model_name, session.wire_name = new_prov, name, wire
            pi(f"Cambiando a {name} ({new_prov}) — {prov} no disponible.")
            return True

    console.print(
        "\n  [yellow]No hay providers alternativos disponibles.[/yellow]\n"
        "  Abriendo pantalla de registro de providers...\n"
    )
    _cmd_login(session)
    return False


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

    # ── Health scan en paralelo (no bloquea el arranque) ──────────────────────
    import concurrent.futures as _cf
    _health_future = None
    try:
        _health_executor = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="bago_health")
        _health_future = _health_executor.submit(
            scan_provider_health, creds, providers, 3
        )
    except Exception:
        pass

    # Mostrar banner inicial (sin health — aparece rápido)
    banner(session)

    # Esperar resultado del health scan (máx 4s) y actualizar el banner
    if _health_future:
        try:
            _health = _health_future.result(timeout=4)
            # Actualizar skip_providers para TODOS los providers según resultado real
            _active_creds = session.creds.active_bago_providers()
            for _pname, _phdata in _health.items():
                if _phdata.get("ok"):
                    session.skip_providers.discard(_pname)
                else:
                    # Solo excluir si el provider tiene credenciales pero falló la verificación
                    # (no excluir providers sin key — esos ya no aparecen en active_bago_providers)
                    if _pname in _active_creds or _pname in ("ollama-local", "ollama-cloud"):
                        session.skip_providers.add(_pname)
            # Re-imprimir banner con colores reales
            console.print()
            banner(session, health=_health)
            session._last_health = _health   # guardar para /status
            # Si todos los providers están en rojo → aviso proactivo
            _all_red = all(not v.get("ok") for v in _health.values())
            if _all_red:
                console.print(
                    "\n  [bold yellow]⚠  Ningún provider disponible.[/bold yellow]\n"
                    "  Usa [cyan]/login[/cyan] para configurar un provider "
                    "o ejecuta [cyan]ollama serve[/cyan] si tienes Ollama instalado."
                )
        except Exception:
            pass
    else:
        session._last_health = None

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

    # Key binding: '/' con buffer vacío → abre menú navegable inmediatamente
    kb = KeyBindings()

    @kb.add("/")
    def _slash_trigger(event):
        buf = event.app.current_buffer
        if not buf.text:
            # Buffer vacío: submit "/" directamente → cmd() abrirá _cmd_main_menu
            buf.text = "/"
            buf.validate_and_handle()
        else:
            # Buffer con texto: insertar '/' normalmente
            buf.insert_text("/")

    pt = PromptSession(
        history=FileHistory(str(hist_file)),
        auto_suggest=AutoSuggestFromHistory(),
        style=completion_style,
        completer=BagoCompleter(),
        complete_while_typing=True,
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
        except KeyboardInterrupt:
            console.print("\n[dim yellow]⚡ Interrumpido — modelo cancelado. Escribe tu siguiente mensaje.[/dim yellow]")
        except RuntimeError as e:
            # ── Sin modelo disponible: cadena agotada → pantalla de instalación ──
            if isinstance(e, OllamaNoModelAvailable):
                console.print(Panel(
                    f"[bold red]🚨 EMERGENCIA: Sin modelo disponible[/bold red]\n\n"
                    f"  El modelo [cyan]{e.missing}[/cyan] no está instalado\n"
                    f"  y todos los fallbacks fallaron.\n\n"
                    f"  [dim]Intentados: {', '.join(e.tried) or 'ninguno'}[/dim]",
                    title="BAGO — Sin Modelo",
                    border_style="red",
                    expand=False,
                ))
                _ollama_recovery_flow(session, e.missing)
                continue
            is_not_found, ol_model = _is_ollama_model_not_found(e)
            is_unreachable = _is_ollama_unreachable(e)
            if is_not_found or is_unreachable:
                recovered = _ollama_recovery_flow(
                    session,
                    ol_model or session.wire_name or "",
                )
                if recovered:
                    # Reintentar el mismo mensaje con el modelo/provider nuevo
                    try:
                        result = chat(session, line)
                        if result:
                            show_response(result, session.model_name, session.provider)
                    except RuntimeError as e2:
                        # Segundo nivel: detectar si el retry falló por otro tipo de error
                        if _is_cloud_auth_error(e2) or _is_cloud_connection_error(e2):
                            _cloud_recovery_flow(session, e2)
                        else:
                            pe(str(e2))
                            console.print("[dim]  Usa /switch para cambiar de modelo o /login para reconfigurar.[/dim]")
                    continue
            elif _is_cloud_auth_error(e) or _is_cloud_connection_error(e):
                _cloud_recovery_flow(session, e)
            else:
                pe(str(e))
                console.print("[dim]  Prueba /login para registrar providers o /switch para cambiar modelo.[/dim]")

if __name__ == "__main__":
    main()

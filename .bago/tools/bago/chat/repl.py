"""bago.chat.repl — PromptSession setup y bucle REPL principal."""

import sys
import os
from pathlib import Path

_PROMPT_TOOLKIT_AVAILABLE = os.environ.get("BAGO_NO_PROMPT_TOOLKIT", "0") != "1"
try:
    if not _PROMPT_TOOLKIT_AVAILABLE:
        raise ModuleNotFoundError("prompt_toolkit disabled by BAGO_NO_PROMPT_TOOLKIT=1")
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style
    from prompt_toolkit.key_binding import KeyBindings
except ModuleNotFoundError:
    _PROMPT_TOOLKIT_AVAILABLE = False
    PromptSession = object
    FileHistory = AutoSuggestFromHistory = Style = KeyBindings = None

from bago import cmd, console, pe, CtrlCGuard
from bago.constants import USER_BAGO
from bago.llm import (
    _is_ollama_model_not_found, _is_ollama_unreachable,
    _is_cloud_auth_error, _is_cloud_connection_error,
    OllamaNoModelAvailable,
)
from bago.tumba import tumba_add, tumba_has_placeholder, tumba_substitute
from bago.ui import show_response
from bago.api.bridge import chat_bridge

from rich.panel import Panel

if _PROMPT_TOOLKIT_AVAILABLE:
    from .statusbar import _topbar_prompt, _bottom_bar, _prompt_indicator
else:
    def _prompt_indicator(session) -> str:
        last = session.last_route or {}
        last_mode = last.get("mode", "")
        if last_mode and last_mode != "manual":
            indicator = last_mode.upper()
        elif session.autoroute:
            indicator = "AUTO"
        else:
            indicator = "MANUAL"
        if session.autonomous:
            indicator += ":A"
        if session.tumba_mode:
            indicator += " TUMBA"
        return indicator

    def _topbar_prompt(route_mode: str) -> str:
        return f"[BAGO|{route_mode}] > "

    def _bottom_bar() -> str:
        return ""
from .recovery import _ollama_recovery_flow, _cloud_recovery_flow


if _PROMPT_TOOLKIT_AVAILABLE:
    _COMPLETION_STYLE = Style.from_dict({
        "prompt":                  "bold cyan",
        "statusbar":               "bg:#1e2a3a #7aa2f7 bold",
        "bottom-toolbar":          "bg:#1e2a3a #7aa2f7",
        "completion-menu":                  "bg:#1a1a2e #e0e0e0",
        "completion-menu.completion":       "bg:#1a1a2e #e0e0e0",
        "completion-menu.completion.current": "bg:#00aaff #000000 bold",
        "completion-menu.meta":             "bg:#111133 #888888",
        "completion-menu.meta.completion.current": "bg:#0055aa #cccccc",
        "scrollbar.background":             "bg:#1a1a2e",
        "scrollbar.button":                 "bg:#00aaff",
    })
else:
    _COMPLETION_STYLE = None


class _SimplePromptSession:
    """Fallback REPL session sin prompt_toolkit."""
    def prompt(self, message=None, bottom_toolbar=None):
        if callable(message):
            m = message()
        else:
            m = message
        if not isinstance(m, str):
            m = "[BAGO] > "
        return input(m)


def build_prompt_session() -> PromptSession:
    """Crea y devuelve el PromptSession con historia, estilo y keybindings."""
    global _PROMPT_TOOLKIT_AVAILABLE
    if not _PROMPT_TOOLKIT_AVAILABLE:
        console.print(
            "[yellow]prompt_toolkit no instalado: usando REPL básico.[/yellow]\n"
            "[dim]Instala prompt_toolkit para autocompletado y barra avanzada.[/dim]"
        )
        return _SimplePromptSession()

    try:
        from bago.completer import BagoCompleter

        hist_file = USER_BAGO / "state" / "chat_input_history.txt"
        hist_file.parent.mkdir(parents=True, exist_ok=True)

        kb = KeyBindings()

        @kb.add("/")
        def _slash_trigger(event):
            buf = event.app.current_buffer
            if not buf.text:
                buf.text = "/"
                buf.validate_and_handle()
            else:
                buf.insert_text("/")

        return PromptSession(
            history=FileHistory(str(hist_file)),
            auto_suggest=AutoSuggestFromHistory(),
            style=_COMPLETION_STYLE,
            completer=BagoCompleter(),
            complete_while_typing=True,
            key_bindings=kb,
        )
    except Exception as exc:
        _PROMPT_TOOLKIT_AVAILABLE = False
        console.print(
            f"[yellow]prompt_toolkit no disponible en esta consola ({type(exc).__name__}); "
            "usando REPL básico.[/yellow]"
        )
        return _SimplePromptSession()


def run_repl(session, pt: PromptSession) -> None:
    """Bucle REPL principal — procesa comandos y mensajes de chat."""
    ctrl_c = CtrlCGuard()
    while True:
        try:
            if _PROMPT_TOOLKIT_AVAILABLE:
                line = pt.prompt(
                    message=lambda: _topbar_prompt(_prompt_indicator(session)),
                    bottom_toolbar=_bottom_bar,
                ).strip()
            else:
                line = pt.prompt(message=f"[BAGO|{_prompt_indicator(session)}] > ").strip()
        except EOFError:
            console.print("\n[dim]BAGO terminado.[/dim]")
            break
        except KeyboardInterrupt:
            if ctrl_c.press():
                console.print("[dim]BAGO terminado.[/dim]")
                break
            continue

        if not line:
            continue
        if line.startswith("/"):
            if not cmd(line, session):
                break
            continue

        # ── Modo Tumba: copia el contenido sin enviarlo al LLM ───────────────
        if session.tumba_mode:
            ok, name, msg = tumba_add(line)
            console.print(msg)
            continue

        # ── Sustituir {{placeholders}} de la tumba antes de enviar al LLM ───
        llm_input = line   # lo que ve el LLM (puede tener secretos sustituidos)
        if tumba_has_placeholder(line):
            substituted, used = tumba_substitute(line)
            if used:
                keys_str = ", ".join(f"[bold]{k}[/bold]" for k in used)
                console.print(f"  [dim cyan]🪦 Tumba: insertando {keys_str}[/dim cyan]")
                llm_input = substituted  # el LLM ve el valor; history conserva {{key}}

        try:
            result = chat_bridge(session, llm_input, history_input=line)
            if result:
                show_response(result, session.model_name, session.provider)
        except KeyboardInterrupt:
            console.print(
                "\n[dim yellow]⚡ Interrumpido — modelo cancelado. "
                "Escribe tu siguiente mensaje.[/dim yellow]"
            )
        except RuntimeError as exc:
            # Sin modelo disponible: cadena agotada → pantalla de instalación
            if isinstance(exc, OllamaNoModelAvailable):
                console.print(Panel(
                    f"[bold red]🚨 EMERGENCIA: Sin modelo disponible[/bold red]\n\n"
                    f"  El modelo [cyan]{exc.missing}[/cyan] no está instalado\n"
                    f"  y todos los fallbacks fallaron.\n\n"
                    f"  [dim]Intentados: {', '.join(exc.tried) or 'ninguno'}[/dim]",
                    title="BAGO — Sin Modelo",
                    border_style="red",
                    expand=False,
                ))
                _ollama_recovery_flow(session, exc.missing)
                continue

            is_not_found, ol_model = _is_ollama_model_not_found(exc)
            is_unreachable = _is_ollama_unreachable(exc)
            if is_not_found or is_unreachable:
                recovered = _ollama_recovery_flow(
                    session,
                    ol_model or session.wire_name or "",
                )
                if recovered:
                    try:
                        result = chat_bridge(session, llm_input, history_input=line)
                        if result:
                            show_response(result, session.model_name, session.provider)
                    except RuntimeError as exc2:
                        if _is_cloud_auth_error(exc2) or _is_cloud_connection_error(exc2):
                            _cloud_recovery_flow(session, exc2)
                        else:
                            pe(str(exc2))
                            console.print(
                                "[dim]  Usa /switch para cambiar de modelo "
                                "o /login para reconfigurar.[/dim]"
                            )
                continue
            elif _is_cloud_auth_error(exc) or _is_cloud_connection_error(exc):
                _cloud_recovery_flow(session, exc)
            else:
                pe(str(exc))
                console.print(
                    "[dim]  Prueba /login para registrar providers "
                    "o /switch para cambiar modelo.[/dim]"
                )


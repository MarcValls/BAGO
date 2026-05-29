"""bago.chat.repl — PromptSession setup y bucle REPL principal."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import sys
import os
import time
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
from bago.providers import get_default_model
from bago.llm import (
    _is_ollama_model_not_found, _is_ollama_unreachable,
    _is_cloud_auth_error, _is_cloud_connection_error,
    OllamaNoModelAvailable,
)
from bago.tumba import tumba_add, tumba_has_placeholder, tumba_substitute
from bago.ui import show_response
from bago.api.bridge import chat_bridge

from rich.panel import Panel

# ── Shadow Mode RL ──────────────────────────────────────────────────────
_RL_AVAILABLE = os.environ.get("BAGO_RL_SHADOW", "0").lower() in ("1", "true", "yes")
_shadow = None

def _init_shadow():
    global _shadow
    if _shadow is not None:
        return
    try:
        import sys
        _rl_dir = Path(__file__).resolve().parents[4] / ".bago" / "rl" / "adapters"
        if str(_rl_dir) not in sys.path:
            sys.path.insert(0, str(_rl_dir))
        from bago_rl_shadow import ShadowMode
        _shadow = ShadowMode()
    except Exception as exc:
        console.print(f"[dim yellow][Shadow] No disponible: {exc}[/dim yellow]")
        _shadow = None

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


def _try_local_intent_response(session, line: str) -> bool:
    """Respuestas deterministas para intenciones que un modelo pequeno suele perder."""
    try:
        from intent_router import resolve_intent
        plan = resolve_intent(line)
    except Exception:
        return False

    if plan.get("intent") != "idea_feature_config_provider_disable":
        return False

    response = (
        "Detecto una idea de producto: permitir desactivar providers o modelos completos. "
        "La forma canónica es `enabled=false`: BAGO debe ocultarlos del menú, excluirlos "
        "del routing y no usarlos en fallback. Ya existe el control operativo: "
        "`/provider off <provider>` y `/provider on <provider>`."
    )
    try:
        session.history.append({"role": "user", "content": line})
        session.history.append({"role": "assistant", "content": response})
        session.add_timeline("intent", plan.get("intent", ""), plan.get("rewrite", "")[:160], level="route")
    except Exception:
        pass
    show_response(response, session.model_name, session.provider, label="BAGO")
    return True


if _PROMPT_TOOLKIT_AVAILABLE:
    _COMPLETION_STYLE = Style.from_dict({
        "prompt":                  "bold cyan",
        "statusbar":               "bg:#1e2a3a #7aa2f7 bold",
        "bottom-toolbar":          "bg:#1e2a3a #7aa2f7",
        "timeline.title":          "bg:#1e2a3a #7dd3fc bold",
        "timeline.meta":           "bg:#1e2a3a #94a3b8",
        "timeline.event":          "bg:#111827 #cbd5e1",
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


def build_prompt_session(session=None) -> PromptSession:
    """Crea y devuelve el PromptSession con historia, estilo y keybindings."""
    global _PROMPT_TOOLKIT_AVAILABLE
    if not _PROMPT_TOOLKIT_AVAILABLE:
        console.print(
            "[yellow]prompt_toolkit no instalado: usando REPL básico.[/yellow]\n"
            "[dim]Instala prompt_toolkit para autocompletado y barra avanzada.[/dim]"
        )
        if sys.stdin.isatty():
            try:
                ans = input("  ¿Instalar ahora? [s/n] ").strip().lower()
            except EOFError:
                ans = "n"
            if ans in ("s", "si", "y", "yes"):
                import subprocess
                try:
                    console.print("[cyan]  Instalando prompt_toolkit...[/cyan]")
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "prompt_toolkit", "-q"],
                        capture_output=True, text=True, timeout=60,
                    )
                    if result.returncode == 0:
                        console.print("[green]  ✓ prompt_toolkit instalado. Reinicia BAGO para activar.[/green]")
                    else:
                        console.print(f"[red]  ✗ Error: {result.stderr[:200]}[/red]")
                except Exception as exc:
                    console.print(f"[red]  ✗ No se pudo instalar: {exc}[/red]")
        return _SimplePromptSession()

    try:
        from bago.completer import BagoCompleter

        hist_file = USER_BAGO / "state" / "chat_input_history.txt"
        try:
            hist_file.parent.mkdir(parents=True, exist_ok=True)
            hist_file.touch(exist_ok=True)
        except Exception:
            # fallback: usar directorio temporal si no se puede crear o escribir en USER_BAGO
            import tempfile
            hist_file = Path(tempfile.gettempdir()) / "bago_history.txt"
            try:
                hist_file.parent.mkdir(parents=True, exist_ok=True)
                hist_file.touch(exist_ok=True)
            except Exception:
                pass

        try:
            history = FileHistory(str(hist_file))
        except Exception:
            import tempfile
            hist_file = Path(tempfile.gettempdir()) / "bago_history.txt"
            history = FileHistory(str(hist_file))

        kb = KeyBindings()

        @kb.add("c-t", eager=True)
        def _toggle_timeline(event):
            if session is None:
                return
            session.timeline_visible = not getattr(session, "timeline_visible", False)
            state = "visible" if session.timeline_visible else "oculta"
            try:
                session.add_timeline("ui", "timeline", state, level="ui")
            except Exception:
                pass
            event.app.invalidate()

        @kb.add("/")
        def _slash_trigger(event):
            buf = event.app.current_buffer
            if not buf.text:
                buf.text = "/"
                buf.validate_and_handle()
            else:
                buf.insert_text("/")

        return PromptSession(
            history=history,
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


def _auto_switch_model(session) -> bool:
    """Si el modelo actual es 'sin-modelo', intenta auto-switch al primer provider SANO disponible."""
    if getattr(session, "model_name", None) != "sin-modelo" and getattr(session, "provider", None) != "none":
        return False
    providers = getattr(session, "providers", {})
    if not providers:
        return False

    # Health check rápido de todos los providers activos
    try:
        from bago.provider_health import scan_provider_health
        health = scan_provider_health(session.creds, providers, timeout=3)
    except Exception:
        health = {}

    active = session.creds.active_bago_providers() if hasattr(session.creds, "active_bago_providers") else set(providers.keys())

    # Orden: github-models (más confiable, 43 modelos) > codex > copilot > anthropic > ollama-cloud > ollama-local
    for prov_name in ("github-models", "codex", "copilot", "anthropic", "ollama-cloud", "ollama-local"):
        if prov_name not in active:
            continue
        prov_health = health.get(prov_name, {})
        if not prov_health.get("ok"):
            continue  # Saltar providers enfermos (auth errors, rate limits, etc.)
        prov_data = providers.get(prov_name)
        if not prov_data:
            continue
        model_name, wire, _ = get_default_model(prov_name, providers)
        if not model_name:
            continue
        old = session.model_name
        session.provider, session.model_name, session.wire_name = prov_name, model_name, wire
        source = session._update_model_origin(prov_name, model_name, wire)
        session.switches = getattr(session, "switches", 0) + 1
        session.last_route = {
            "mode": "auto",
            "provider": prov_name,
            "model": model_name,
            "reason": f"auto-switch desde {old}",
            "service": source.get("service", ""),
            "route": source.get("route", ""),
            "backend": source.get("backend", ""),
        }
        console.print(f"  [dim cyan][Auto-switch] {old} → {model_name} ({prov_name}) ✓[/dim cyan]")
        return True

    # Fallback: si ninguno pasa health check, elegir el primero que tenga modelos (último recurso)
    for prov_name in ("github-models", "codex", "copilot", "anthropic", "ollama-cloud", "ollama-local"):
        if prov_name not in active:
            continue
        prov_data = providers.get(prov_name)
        if not prov_data:
            continue
        model_name, wire, _ = get_default_model(prov_name, providers)
        if not model_name:
            continue
        old = session.model_name
        session.provider, session.model_name, session.wire_name = prov_name, model_name, wire
        source = session._update_model_origin(prov_name, model_name, wire)
        session.switches = getattr(session, "switches", 0) + 1
        session.last_route = {
            "mode": "auto",
            "provider": prov_name,
            "model": model_name,
            "reason": f"auto-switch fallback desde {old}",
            "service": source.get("service", ""),
            "route": source.get("route", ""),
            "backend": source.get("backend", ""),
        }
        console.print(f"  [dim yellow][Auto-switch] {old} → {model_name} ({prov_name}) ⚠ sin health check[/dim yellow]")
        return True
    return False


def run_repl(session, pt: PromptSession) -> None:
    """Bucle REPL principal — procesa comandos y mensajes de chat."""
    ctrl_c = CtrlCGuard()
    try:
        session.add_timeline("ui", "repl", f"{session.provider}/{session.model_name}")
    except Exception:
        pass
    while True:
        _auto_switch_model(session)
        try:
            if _PROMPT_TOOLKIT_AVAILABLE:
                line = pt.prompt(
                    message=lambda: _topbar_prompt(_prompt_indicator(session)),
                    bottom_toolbar=lambda: _bottom_bar(session),
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
        if line == "/timeline":
            session.timeline_visible = not getattr(session, "timeline_visible", False)
            try:
                session.add_timeline("ui", "timeline", "visible" if session.timeline_visible else "oculta", level="ui")
            except Exception:
                pass
            continue
        if line.startswith(("/", "\\")):
            try:
                cmd_name = line.split()[0].lstrip("/\\")
                session.add_timeline("command", cmd_name, line[:120], level="command")
            except Exception:
                pass
            if line.startswith("\\"):
                line = line[1:]
            if not cmd(line, session):
                break
            continue

        # ── Modo Tumba: copia el contenido sin enviarlo al LLM ───────────────
        if session.tumba_mode:
            ok, name, msg = tumba_add(line)
            console.print(msg)
            continue

        if _try_local_intent_response(session, line):
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
            session.add_timeline("user", "input", line[:120], level="user")
        except Exception:
            pass

        history_before = len(getattr(session, "history", []))
        _init_shadow()
        if _shadow:
            _shadow.on_pre_chat(session, llm_input)
        _chat_exc = None
        _t0 = None
        try:
            _t0 = time.time()
            result = chat_bridge(session, llm_input, history_input=line)
            _elapsed = time.time() - _t0 if _t0 else 0.0
            if _shadow:
                _shadow.on_post_chat(session, result, None, _elapsed)
            if result and len(getattr(session, "history", [])) == history_before:
                session.history.append({"role": "user", "content": line})
                session.history.append({"role": "assistant", "content": result})
            if result:
                show_response(result, session.model_name, session.provider)
            assistant_text = result
            if not assistant_text and getattr(session, "history", None):
                last_msg = session.history[-1] if session.history else {}
                if last_msg.get("role") == "assistant":
                    assistant_text = last_msg.get("content", "")
            route = session.last_route or {}
            route_text = f"{route.get('mode', 'manual')} {route.get('provider', session.provider)}/{route.get('model', session.model_name)}"
            if route.get("reason"):
                route_text += f" | {route.get('reason')}"
            if assistant_text:
                try:
                    session.add_timeline("route", "decision", route_text, level="route")
                    session.add_timeline("assistant", "reply", assistant_text[:160].replace("\n", " "), level="assistant")
                except Exception:
                    pass
        except KeyboardInterrupt:
            if _shadow and _t0:
                _shadow.on_post_chat(session, None, KeyboardInterrupt(), time.time() - _t0)
            console.print(
                "\n[dim yellow]⚡ Interrumpido — modelo cancelado. "
                "Escribe tu siguiente mensaje.[/dim yellow]"
            )
            try:
                session.add_timeline("error", "cancelled", "KeyboardInterrupt", level="error")
            except Exception:
                pass
        except RuntimeError as exc:
            if _shadow and _t0:
                _shadow.on_post_chat(session, None, exc, time.time() - _t0)
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
                try:
                    session.add_timeline("error", "no-model", f"{exc.missing}", level="error")
                except Exception:
                    pass
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
                    _t0_rec = time.time()
                    try:
                        result = chat_bridge(session, llm_input, history_input=line)
                        _elapsed = time.time() - _t0_rec
                        if _shadow:
                            _shadow.on_post_chat(session, result, None, _elapsed)
                        if result and len(getattr(session, "history", [])) == history_before:
                            session.history.append({"role": "user", "content": line})
                            session.history.append({"role": "assistant", "content": result})
                        if result:
                            show_response(result, session.model_name, session.provider)
                    except RuntimeError as exc2:
                        if _shadow:
                            _shadow.on_post_chat(session, None, exc2, time.time() - _t0_rec)
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
                try:
                    session.add_timeline("error", type(exc).__name__, str(exc)[:160].replace("\n", " "), level="error")
                except Exception:
                    pass



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

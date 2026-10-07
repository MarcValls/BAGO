"""repl_startup.py — Mixin de arranque, input y navegación para BagoREPL.

Métodos extraídos de repl.py que gestionan:
- Banner, status, advertencias de init
- Startup interactivo (selección de provider/modelo)
- Auto-evolución al arrancar
- Readline / prompt_toolkit
- Input con timeout
- Navegación de menús (flechas)
- Wizard de configuración
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import ANSI
except Exception:
    PromptSession = None  # type: ignore[assignment]
    ANSI = None  # type: ignore[assignment]

from repl_history import GatewayFileHistory, save_readline_history

# CANON[CHAT-004]: startup reads session state and renders it; it does not author it.
# LEGACY[CHAT-L004]: keep local imports working when tests load the module by file path.
CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

import renderer as R
from version import CURRENT as BAGO_VERSION
from switch_engine import SwitchEngine
from repl_utils import (
    load_keybinds,
    read_key,
    key_action,
    enable_vt,
    restore_windows_console,
    fit,
    draw_navigate,
    navigation_hint,
    ui_glyph,
    terminal_supports_unicode,
    clear_terminal,
)

# Ajustes editables desde /config
CONFIG_EDITABLE: list[tuple[str, str, str]] = [
    ("temperature", "number", "Creatividad del modelo (0.0 - 1.0)"),
    ("features.streaming", "bool", "Respuestas en streaming"),
    ("features.tool_calling", "bool", "El modelo puede invocar herramientas"),
    ("features.tool_approval_policy", "choice", "Aprobación de tools (ask/always)"),
    ("features.compression_on_downgrade", "bool", "Comprimir contexto al bajar de modelo"),
    ("features.rl_learning", "bool", "Aprendizaje por refuerzo activo"),
    ("features.auto_evolve_on_start", "bool", "Autoevolución al arrancar"),
    ("features.workspace_retrieval", "bool", "Recuperación de workspace"),
    ("features.directory_context", "bool", "Contexto de directorio"),
    ("ui.color", "bool", "Colores ANSI en terminal"),
    ("ui.history", "bool", "Historial de comandos"),
    ("ui.multiline", "bool", "Modo multiline con ```"),
    ("ui.prompt_provider_on_start", "bool", "Preguntar provider al arrancar"),
    ("default_provider", "text", "Provider por defecto"),
    ("default_model", "text", "Modelo por defecto"),
]


class BagoReplStartupMixin:
    """Mixin: métodos de arranque, input y navegación para BagoREPL."""

    # ─── Banner + Status ───────────────────────────────────────────────

    def _print_banner(self) -> None:
        print(R.banner())
        print()
        print(R.info(f"Bienvenido a BAGO {BAGO_VERSION}. Escribe / para comandos."))
        print(R.dim("El contexto de sesión sobrevive al cambio de provider."))
        print(R.response_contract_line())
        print()

    def _print_startup_guide(self) -> None:
        """Muestra una guía corta de arranque basada en el estado real."""
        try:
            workspace = self.mgr.workspace_state()
            welcome = self.mgr.welcome_state()
        except Exception:
            workspace = {}
            welcome = {}

        workspace_state = str(workspace.get("workspace_state", "")).lower()
        workspace_root = str(workspace.get("workspace_state_root", "") or workspace.get("project_root", "")).strip()
        provider = str(getattr(self.mgr, "provider", "") or "").strip()
        model = str(getattr(self.mgr, "model", "") or "").strip()

        print(R.bold("Inicio guiado"))
        if workspace_state == "linked_confirmed":
            print(R.ok(f"Workspace confirmado: {workspace_root or '—'}"))
        else:
            summary = str(welcome.get("summary", "") or "Workspace pendiente").strip()
            print(R.warn(summary))
            print(R.dim("1) Elige o vincula workspace"))
            print(R.dim("   - usa el selector de workspace o /workspace/list"))
            print(R.dim("2) Confirma provider/modelo"))
        print(R.dim(f"3) Provider actual: {provider or '—'} / {model or '—'}"))
        print(R.dim("4) Si cambias modelo manualmente, el modo auto se desactiva"))
        print()

    def _print_status(self) -> None:
        s = self.mgr.status()
        line = R.status_line(s["provider"], s["model"], s["total_tokens"], s["health"]["ok"])
        print(R.dim("═" * 60))
        print(line)
        print(R.response_contract_line())
        print(R.dim("═" * 60))

    def _print_chat_prompt(self) -> None:
        print(R.dim("─" * 60))
        print(R.accent("bago") + R.bright_black(" ❯ "), end="", flush=True)

    def _print_init_warnings(self) -> None:
        """Muestra advertencias si el modelo fue auto-corregido."""
        info = getattr(self.mgr, "_init_info", {})
        if info.get("corrected"):
            requested = info.get("requested", "?")
            actual = info.get("actual", "?")
            available = info.get("available", [])
            print(R.warn(f"⚠ Modelo '{requested}' no disponible. Usando '{actual}'."))
            if available:
                print(R.dim(f"   Modelos disponibles: {', '.join(available[:5])}"))
                if len(available) > 5:
                    print(R.dim(f"   ... y {len(available) - 5} más. Usa /models para ver todos."))
            print()

    # ─── Readline + Prompt toolkit ─────────────────────────────────────

    def _setup_readline(self) -> None:
        if not bool(self.mgr.config.get("ui.history", True)):
            return
        try:
            import readline
            histfile = self.base_path / ".bago" / "state" / ".bago_history"
            try:
                readline.read_history_file(str(histfile))
            except FileNotFoundError:
                pass
            import atexit
            atexit.register(
                save_readline_history,
                readline,
                histfile,
                trusted_root=self.base_path,
                session_id=str(getattr(self.mgr, "session_id", "") or ""),
            )
        except ImportError:
            pass

    def _use_prompt_toolkit(self) -> bool:
        if os.environ.get("BAGO_NO_PROMPT_TOOLKIT", "").strip().lower() in {"1", "true", "yes", "on"}:
            return False
        return bool(PromptSession) and sys.stdin.isatty() and sys.stdout.isatty()

    def _read_main_input(self, prompt: str) -> str:
        history_enabled = bool(self.mgr.config.get("ui.history", True))
        if self._use_prompt_toolkit():
            try:
                if self._chat_session is None:
                    if GatewayFileHistory is not None and history_enabled:
                        history = GatewayFileHistory(
                            self._chat_history_path,
                            trusted_root=self.state_root,
                            session_id=str(getattr(self.mgr, "session_id", "") or ""),
                        )
                    else:
                        history = None
                    self._chat_session = PromptSession(
                        history=history,
                        enable_history_search=history_enabled,
                    )
                if ANSI is not None:
                    return self._chat_session.prompt(ANSI(prompt))
                return self._chat_session.prompt(prompt)
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                self._chat_session = None
        return input(prompt)

    # ─── Timeout input ─────────────────────────────────────────────────

    def _timed_input(self, prompt: str, timeout: int = 60) -> str | None:
        import threading
        result: list[str | None] = [None]
        done = threading.Event()

        def _reader() -> None:
            try:
                val = input(prompt)
                result[0] = val
            except (EOFError, KeyboardInterrupt):
                result[0] = None
            finally:
                done.set()

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        remaining = timeout
        while remaining > 0 and not done.wait(timeout=min(10, remaining)):
            remaining -= 10
            if remaining > 0 and not done.is_set():
                sys.stdout.write(f"\r{R.dim(f'[{remaining}s restantes]')} {prompt}")
                sys.stdout.flush()

        if not done.is_set():
            print(f"\n{R.warn(f'Timeout ({timeout}s). Wizard cerrado automáticamente.')}")
            return None
        return result[0]

    # ─── Navegación ────────────────────────────────────────────────────

    def _navigate(self, title: str, labels: list[str], hint: str | None = None) -> int | None:
        """Selector navegable con flechas. Retorna índice o None si cancela."""
        if not labels:
            return None
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return None
        hint = hint or (self.keybinds.get("_hint") if terminal_supports_unicode() else navigation_hint())
        vt_ok = enable_vt()
        selected = 0
        drawn = draw_navigate(title, labels, selected, hint)
        try:
            while True:
                try:
                    key = read_key()
                except (KeyboardInterrupt, EOFError):
                    return None
                action = key_action(key, self.keybinds, "menu")
                if action == "up":
                    selected = (selected - 1) % len(labels)
                elif action == "down":
                    selected = (selected + 1) % len(labels)
                elif action == "select":
                    return selected
                elif action == "back":
                    return None
                else:
                    continue
                if not vt_ok:
                    clear_terminal(False)
                drawn = draw_navigate(title, labels, selected, hint, redraw_lines=drawn if vt_ok else 0)
        finally:
            restore_windows_console()

    # ─── Startup interactivo ───────────────────────────────────────────

    def _interactive_startup(self) -> None:
        """Ofrece selección interactiva de provider/modelo si estamos en TTY."""
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            return

        prompt_enabled = bool(getattr(self, "_startup_prompt_enabled", True))
        if not prompt_enabled:
            return

        providers = self.mgr.available_providers()
        configured = [p for p in providers if p["configured"]]
        if not configured:
            print(R.error("No hay providers configurados."))
            return

        labels = [
            f"{item['name']} {ui_glyph('·', '-')} {len(item['models'])} modelos"
            f"{' ' + ui_glyph('·', '-') + ' actual' if item['name'] == self.mgr.provider else ''}"
            for item in configured
        ]
        idx = self._navigate(f"Provider {ui_glyph('·', '-')} {navigation_hint()}", labels)
        if idx is None:
            return

        prov = configured[idx]
        models = prov["models"]
        if not models:
            print(R.warn("Este provider no tiene modelos disponibles."))
            return

        model_labels = [
            f"{model}{' ' + ui_glyph('·', '-') + ' actual' if prov['name'] == self.mgr.provider and model == self.mgr.model else ''}"
            for model in models
        ]
        model_idx = self._navigate(f"Modelo de {prov['name']} {ui_glyph('·', '-')} {navigation_hint()}", model_labels)
        if model_idx is None:
            return

        new_model = models[model_idx]
        # El usuario acaba de escoger explícitamente provider y modelo: no
        # bloquear el arranque por una equivalencia aún no catalogada.
        result = self.mgr.switch(prov["name"], new_model, force=True)
        if result["ok"]:
            print(R.ok(f"✓ Conectado a {prov['name']}/{new_model}"))
            self.engine = SwitchEngine(self.mgr.adapters)
        else:
            detail = result.get("error") or result.get("message") or "; ".join(result.get("warnings") or []) or "sin detalle"
            print(R.error(f"Error: {detail}"))

    # ─── Auto-evolución ────────────────────────────────────────────────

    def _auto_evolve_startup(self) -> None:
        """BAGO START autoevoluciona al arrancar: reentrena intent + BC."""
        try:
            enabled = self.mgr.config.get("features.auto_evolve_on_start", True)
        except Exception:
            enabled = True
        if not enabled:
            return

        print(R.dim("🧬 Autoevolución: aprendiendo de tu historial…"))
        res = self.mgr.auto_evolve()
        if res.get("ok"):
            counts = res.get("counts", {})
            detail = " · ".join(f"{k}:{v}" for k, v in counts.items()) or "sin datos"
            print(R.ok(f"Autoevolución completada — {res.get('total', 0)} ejemplos ({detail})"))
            bc = res.get("bc") or {}
            if bc.get("ok"):
                print(R.ok(f"Política BC entrenada — {bc.get('samples', 0)} muestras "
                           f"(fuente: {bc.get('source', '?')}, loss: {bc.get('loss', 0):.3f})"))
            elif bc.get("reason"):
                print(R.dim(f"  BC no entrenada: {bc['reason']}"))
        else:
            print(R.warn(f"Autoevolución no completada — {res.get('causa', res.get('message', '?'))}"))
            if res.get("responsable"):
                print(R.dim(f"  responsable: {res['responsable']}"))
            if res.get("prevencion"):
                print(R.dim(f"  prevención: {res['prevencion']}"))
        print()

    # ─── Config wizard ─────────────────────────────────────────────────

    def _config_wizard(self) -> bool:
        """Asistente guiado para cambiar ajustes en una sola vista."""
        return self._config_hub_wizard()

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
    from prompt_toolkit.history import FileHistory
except Exception:
    PromptSession = None  # type: ignore[assignment]
    ANSI = None  # type: ignore[assignment]
    FileHistory = None  # type: ignore[assignment]

# CANON[CHAT-004]: startup reads session state and renders it; it does not author it.
# LEGACY[CHAT-L004]: keep local imports working when tests load the module by file path.
CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

import renderer as R
from version import CURRENT as BAGO_VERSION
from repl_utils import (
    load_keybinds,
    read_key,
    key_action,
    enable_vt,
    restore_windows_console,
    fit,
    draw_navigate,
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
            histfile.parent.mkdir(parents=True, exist_ok=True)
            try:
                readline.read_history_file(str(histfile))
            except FileNotFoundError:
                pass
            import atexit
            atexit.register(readline.write_history_file, str(histfile))
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
                    if history_enabled:
                        self._chat_history_path.parent.mkdir(parents=True, exist_ok=True)
                    if FileHistory is not None and history_enabled:
                        history = FileHistory(str(self._chat_history_path))
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
        hint = hint or self.keybinds.get("_hint", "↑↓ navegar   Enter seleccionar   Esc/q cancelar")
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
                drawn = draw_navigate(title, labels, selected, hint, redraw_lines=drawn if vt_ok else 0)
        finally:
            restore_windows_console()

    # ─── Startup interactivo ───────────────────────────────────────────

    def _interactive_startup(self) -> None:
        """Ofrece selección interactiva de provider/modelo si estamos en TTY."""
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            return

        info = getattr(self.mgr, "_init_info", {})
        prompt_enabled = bool(getattr(self, "_startup_prompt_enabled", True))
        if not info.get("corrected") and not prompt_enabled:
            return
        if info.get("corrected"):
            print(R.info("¿Quieres elegir otro modelo? (s/n)"), end=" ")
            choice = self._timed_input("", timeout=15)
            if choice is None or choice.strip().lower() not in ("s", "si", "y", "yes"):
                return
        else:
            print(R.info(f"Provider actual: {R.bold(self.mgr.provider)}/{R.bold(self.mgr.model)}"))
            if prompt_enabled:
                print(R.dim("Presiona Enter para continuar, o escribe 'cambiar' para elegir otro:"), end=" ")
            else:
                print(R.dim("Escribe 'cambiar' para elegir otro provider/modelo, o Enter para continuar:"), end=" ")
            choice = self._timed_input("", timeout=15)
            if choice is None or choice.strip().lower() not in ("cambiar", "change", "c"):
                return

        providers = self.mgr.available_providers()
        configured = [p for p in providers if p["configured"]]
        if not configured:
            print(R.error("No hay providers configurados."))
            return

        print(R.bold("\nProviders configurados:"))
        for i, p in enumerate(configured, 1):
            print(f"  {R.accent(str(i))} {p['name']} ({len(p['models'])} modelos)")
        print(R.dim("  0 Cancelar"))

        sel = self._timed_input(R.dim("Elige: "), timeout=30)
        if sel is None or sel.strip() == "0":
            return
        try:
            idx = int(sel.strip()) - 1
            if idx < 0 or idx >= len(configured):
                print(R.error("Selección inválida."))
                return
        except ValueError:
            print(R.error("Debes introducir un número."))
            return

        prov = configured[idx]
        models = prov["models"]
        if not models:
            print(R.warn("Este provider no tiene modelos disponibles."))
            return

        print(R.bold(f"\nModelos disponibles en {prov['name']}:"))
        for i, m in enumerate(models[:10], 1):
            print(f"  {R.accent(str(i))} {m}")
        if len(models) > 10:
            print(R.dim(f"   ... y {len(models) - 10} más."))
        print(R.dim("  0 Cancelar"))

        sel = self._timed_input(R.dim("Elige: "), timeout=30)
        if sel is None or sel.strip() == "0":
            return
        try:
            idx = int(sel.strip()) - 1
            if idx < 0 or idx >= len(models):
                print(R.error("Selección inválida."))
                return
        except ValueError:
            print(R.error("Debes introducir un número."))
            return

        new_model = models[idx]
        result = self.mgr.switch(prov["name"], new_model)
        if result["ok"]:
            print(R.ok(f"✓ Conectado a {prov['name']}/{new_model}"))
            self.engine = SwitchEngine(self.mgr.adapters)
        else:
            print(R.error(f"Error: {result.get('error', 'unknown')}"))

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

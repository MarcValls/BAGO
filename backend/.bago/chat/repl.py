#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
repl.py — BAGO 4.1.5 Chat REPL (Rediseño Completo)

Loop principal de chat multi-provider.
- Barra de estado persistente
- Comandos slash (/switch, /models, /status, ...)
- Sin gates: el modelo actúa con capacidades nativas
- Colores ANSI, banner, notificaciones visuales
- Soporte multiline (``` para bloques)
- Historial con readline
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# CANON[CHAT-003]: the REPL is the interactive surface, not a second source of truth.
# LEGACY[CHAT-L003]: load peer chat modules from the local directory when imported by path.
CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

# Ensure core path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root → bago_core package
from session_manager import SessionManager
from switch_engine import SwitchEngine
from state_paths import resolve_state_root
from context_budget import AlertLevel

import renderer as R
import commands
from commands import execute
from repl_menu import BagoReplMenuMixin
from repl_startup import BagoReplStartupMixin
from repl_inventory import print_workspace_inventory
from repl_utils import (
    is_transcript,
    wrap_transcript,
    load_keybinds,
)

MENU_SECTIONS = commands.MENU_SECTIONS


class BagoREPL(BagoReplStartupMixin, BagoReplMenuMixin):
    """REPL principal de BAGO."""

    def __init__(
        self,
        provider: str = "ollama-local",
        model: str = "llama3.2:3b",
        system_prompt: str = "",
        base_path: str | None = None,
        state_root: str | None = None,
        active_bridges: list[str] | None = None,
        startup_prompt: bool = True,
    ):
        self.base_path = Path(base_path or os.getcwd())
        self.state_root = resolve_state_root(state_root)
        self.mgr = SessionManager(
            provider=provider,
            model=model,
            base_path=str(self.base_path),
            state_root=str(self.state_root),
            system_prompt=system_prompt,
            active_bridges=active_bridges,
        )
        R.set_color_enabled(bool(self.mgr.config.get("ui.color", True)))
        self.engine = SwitchEngine(self.mgr.adapters)

        self.keybinds = load_keybinds()
        self.running = False
        self._multiline_buffer: list[str] = []
        self._in_multiline = False
        self._chat_session = None
        self._chat_history_path = self.state_root / ".bago_prompt_history"
        self._startup_prompt_enabled = startup_prompt

    # ─── Chat + Comandos ──────────────────────────────────────────────

    def _handle_pasted_block(self, text: str) -> bool:
        pasted = text.rstrip("\r\n")
        if not pasted.strip():
            return True
        R.print_message("user", pasted)
        self._handle_chat(pasted)
        self._print_status()
        return True

    def _dispatch_command_intent(self, cmd: str) -> bool:
        """Despacha un comando deducido por el engine de intención natural."""
        short = self._WIZARD_COMMANDS.get(cmd)
        if short:
            return self._run_wizard(short)
        if cmd == "/":
            return self._show_command_palette()
        return self._handle_command(cmd)

    def _handle_command(self, line: str) -> bool:
        """Ejecuta un comando slash. Retorna True si debe continuar, False si quit."""
        low = line.strip().lower()
        if low == "/":
            return self._show_menu()
        if len(low.split()) == 1 and low in {"/providers", "/models", "/switch", "/bridges"}:
            return self._provider_hub_wizard()
        if low == "/tools":
            return self._tools_wizard()
        if low == "/config":
            return self._config_hub_wizard()
        if low in ("/credentials set", "/credentials add", "/login", "/cred"):
            return self._credential_wizard()
        short = self._WIZARD_COMMANDS.get(low)
        if short:
            return self._run_wizard(short)
        result = execute(line, self.mgr, self.engine)
        if result.get("action") == "quit":
            print(R.ok(result["message"]))
            return False
        if result.get("action") == "menu":
            return self._show_menu()
        if result.get("action") == "streamed":
            return True

        if result.get("is_chat"):
            return True

        if result["ok"]:
            print(R.ok(result["message"]))
        else:
            print(R.error(result["message"]))

        if line.startswith("/switch") and result.get("ok") and result.get("result"):
            R.print_switch_notification(result["result"].__dict__ if hasattr(result["result"], "__dict__") else {})

        return True

    def _handle_chat(self, text: str, *, route_info: dict | None = None, echo_user: bool = True) -> None:
        """Envía mensaje al LLM y muestra respuesta. Usa streaming si está activo."""
        if is_transcript(text):
            print(R.warn(
                "⚠ Transcript detectado — tratando el bloque como contexto no ejecutable."
            ))
            text = wrap_transcript(text)
        try:
            if self.mgr.config.feature_streaming and self.mgr._adapter and self.mgr._adapter.supports_streaming():
                gen = self.mgr.send_stream(text, route_info=route_info)
                try:
                    first_chunk = next(gen)
                except StopIteration:
                    return
                budget = self.mgr.last_budget_report
                if budget and budget.alert_level != AlertLevel.GREEN:
                    print(budget.banner(color=bool(self.mgr.config.get("ui.color", True))), end="")
                print(R.accent("BAGO"), end=" ")
                sys.stdout.flush()
                print(first_chunk, end="", flush=True)
                chunks = [first_chunk]
                for chunk in gen:
                    print(chunk, end="", flush=True)
                    chunks.append(chunk)
                print()
            else:
                response = self.mgr.send(text, route_info=route_info)
                budget = self.mgr.last_budget_report
                if budget and budget.alert_level != AlertLevel.GREEN:
                    print(budget.banner(color=bool(self.mgr.config.get("ui.color", True))), end="")
                R.print_message("assistant", response)
            if hasattr(self, "_pending_tool_approval_wizard"):
                self._pending_tool_approval_wizard()
        except KeyboardInterrupt:
            print()
            print(R.warn("⏹️ Interrumpido por el usuario."))
        except Exception as exc:
            print(R.error(f"Error de provider: {exc}"))

    def _prompt(self) -> str:
        if self._in_multiline:
            return R.dim("... ")
        return R.accent("bago") + R.bright_black(" ❯ ")

    # ─── Loop principal ───────────────────────────────────────────────

    def run(self) -> None:
        """REPL principal de BAGO — Chat CLI limpio."""
        try:
            self._setup_readline()
            self._print_banner()
            self._print_init_warnings()
            self._auto_evolve_startup()
            self._interactive_startup()
            self._print_status()
            print_workspace_inventory(self.base_path)
            self.running = True

            while self.running:
                self._print_chat_prompt()
                try:
                    line = self._read_main_input("")
                except (EOFError, KeyboardInterrupt):
                    print()
                    print(R.ok("Bye."))
                    break

                # Pasted multiline
                if ("\n" in line or "\r" in line) and not self._in_multiline:
                    self._handle_pasted_block(line)
                    continue

                stripped = line.strip()
                multiline_enabled = bool(self.mgr.config.get("ui.multiline", True))
                if not multiline_enabled and self._in_multiline:
                    self._in_multiline = False
                    self._multiline_buffer = []

                # Multiline ```
                if multiline_enabled:
                    if stripped.startswith("```") and not self._in_multiline:
                        self._in_multiline = True
                        self._multiline_buffer = []
                        continue
                    if stripped == "```" and self._in_multiline:
                        self._in_multiline = False
                        text = "\n".join(self._multiline_buffer)
                        self._multiline_buffer = []
                        R.print_message("user", text)
                        self._handle_chat(text)
                        self._print_status()
                        continue
                    if self._in_multiline:
                        self._multiline_buffer.append(line)
                        continue

                # Enter vacío → solo redibujar
                if not stripped:
                    continue

                # Comandos slash
                if stripped.startswith("/"):
                    if not self._handle_command(stripped):
                        break
                    self._print_status()
                    continue

                route_info = self.mgr.route_user_message(stripped)
                if route_info.get("kind") == "command" and route_info.get("command"):
                    cmd_line = str(route_info["command"])
                    args = route_info.get("args") or []
                    if isinstance(args, list) and args:
                        cmd_line = cmd_line + " " + " ".join(str(arg) for arg in args if str(arg).strip())
                    if not self._dispatch_command_intent(cmd_line):
                        break
                    if not cmd_line.startswith("/quit") and cmd_line not in {"/", "/menu"}:
                        self._handle_chat(stripped, route_info={"kind": "chat", "source": "post_command"}, echo_user=False)
                    self._print_status()
                    continue

                # Chat normal
                R.print_message("user", stripped)
                self._handle_chat(stripped, route_info=route_info)
                self._print_status()
        finally:
            try:
                self.mgr.save()
                print(R.dim(f"Sesión guardada automáticamente: {self.mgr.session_id}"))
            except Exception as exc:
                print(R.warn(f"No se pudo guardar sesión: {exc}"))
            finally:
                self.mgr.close()


def _run_tests() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repl = BagoREPL(base_path=td)
        assert repl.mgr.session_id
        assert not repl.running
        repl.mgr.close()
        print("repl.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    # If run directly, start REPL with defaults
    BagoREPL().run()

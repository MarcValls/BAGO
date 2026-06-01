#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
repl.py â€” BAGO 4.1.5 Chat REPL (RediseÃ±o Completo)

Loop principal de chat multi-provider.
- Barra de estado persistente
- Comandos slash (/switch, /models, /status, ...)
- Sin gates: el modelo actÃºa con capacidades nativas
- Colores ANSI, banner, notificaciones visuales
- Soporte multiline (``` para bloques)
- Historial con readline
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure core path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from session_manager import SessionManager
from switch_engine import SwitchEngine

sys.path.insert(0, str(Path(__file__).resolve().parent))
import renderer as R
from renderer import Color
from commands import execute

MENU_SECTIONS: list[dict[str, Any]] = [
    {
        "title": "Sesion y estado",
        "description": "Estado de la conversacion y sesiones guardadas.",
        "items": [
            {"command": "/status", "description": "Resumen rapido de la sesion actual."},
            {"command": "/session", "description": "Detalles completos de la sesion."},
            {"command": "/save", "description": "Guardar la sesion actual en disco."},
            {"command": "/load", "description": "Cargar una sesion guardada.", "args_prompt": "<session_id>"},
        ],
    },
    {
        "title": "Providers y modelos",
        "description": "Cambiar provider, ver modelos y consultar sugerencias.",
        "items": [
            {"command": "/providers", "description": "Lista providers registrados."},
            {"command": "/models", "description": "Ver modelos del provider actual."},
            {"command": "/switch", "description": "Cambiar provider o modelo.", "args_prompt": "<provider> [modelo] [--force]"},
            {"command": "/suggest", "description": "Sugerencia automatica de provider/modelo."},
        ],
    },
    {
        "title": "Herramientas y automatizacion",
        "description": "Tools, planes y ejecucion autonoma.",
        "items": [
            {"command": "/tools", "description": "Listar herramientas disponibles."},
            {"command": "/scripts", "description": "Listar scripts y baterias registradas."},
            {"command": "/allow", "description": "Aprobar herramientas pendientes."},
            {"command": "/deny", "description": "Rechazar herramientas pendientes."},
            {"command": "/plan", "description": "Generar un plan paso a paso.", "args_prompt": "<tarea>"},
            {"command": "/autopilot", "description": "Ejecutar una tarea autonomamente.", "args_prompt": "<tarea>"},
        ],
    },
    {
        "title": "Agentes y memoria",
        "description": "Agentes especializados y base de conocimiento.",
        "items": [
            {"command": "/agents", "description": "Ver agentes disponibles."},
            {"command": "/agent", "description": "Activar un agente.", "args_prompt": "<nombre>"},
            {"command": "/memory", "description": "Listar recuerdos recientes."},
            {"command": "/good", "description": "Marcar el ultimo mensaje como importante."},
            {"command": "/feedback", "description": "Registrar feedback explicito.", "args_prompt": "<rating>"},
        ],
    },
    {
        "title": "Configuracion y ayuda",
        "description": "Config, credenciales y ayuda del chat.",
        "items": [
            {"command": "/config", "description": "Ver configuracion actual."},
            {"command": "/credentials", "description": "Ver credenciales configuradas."},
            {"command": "/update", "description": "Actualizar BAGO a la ultima version.", "confirm": True},
            {"command": "/help", "description": "Mostrar la ayuda completa."},
            {"command": "/quit", "description": "Salir del chat.", "confirm": True},
        ],
    },
]


class BagoREPL:
    """REPL principal de BAGO 4.1.5."""

    def __init__(
        self,
        provider: str = "ollama-local",
        model: str = "llama3.2:3b",
        system_prompt: str = "",
        base_path: str | None = None,
    ):
        self.base_path = Path(base_path or os.getcwd())
        self.mgr = SessionManager(
            provider=provider,
            model=model,
            base_path=str(self.base_path),
            system_prompt=system_prompt,
        )
        self.engine = SwitchEngine(self.mgr.adapters)

        self.running = False
        self._multiline_buffer: list[str] = []
        self._in_multiline = False

    def _print_init_warnings(self) -> None:
        """Muestra advertencias si el modelo fue auto-corrigido."""
        info = getattr(self.mgr, "_init_info", {})
        if info.get("corrected"):
            requested = info.get("requested", "?")
            actual = info.get("actual", "?")
            available = info.get("available", [])
            print(R.warn(f"âš  Modelo '{requested}' no disponible. Usando '{actual}'."))
            if available:
                print(R.dim(f"   Modelos disponibles: {', '.join(available[:5])}"))
                if len(available) > 5:
                    print(R.dim(f"   ... y {len(available) - 5} mÃ¡s. Usa /models para ver todos."))
            print()

    def _interactive_startup(self) -> None:
        """Ofrece selecciÃ³n interactiva de provider/modelo si estamos en TTY."""
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            return

        info = getattr(self.mgr, "_init_info", {})
        if not info.get("corrected") and not self.mgr.config.get("ui.prompt_provider_on_start", False):
            return
        if info.get("corrected"):
            print(R.info("Â¿Quieres elegir otro modelo? (s/n)"), end=" ")
            try:
                choice = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if choice not in ("s", "si", "y", "yes"):
                return
        else:
            print(R.info(f"Provider actual: {R.bold(self.mgr.provider)}/{R.bold(self.mgr.model)}"))
            print(R.dim("Presiona Enter para continuar, o escribe 'cambiar' para elegir otro:"), end=" ")
            try:
                choice = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if choice not in ("cambiar", "change", "c"):
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

        try:
            sel = input(R.dim("Elige: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if sel == "0":
            return
        try:
            idx = int(sel) - 1
            if idx < 0 or idx >= len(configured):
                print(R.error("SelecciÃ³n invÃ¡lida."))
                return
        except ValueError:
            print(R.error("Debes introducir un nÃºmero."))
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
            print(R.dim(f"   ... y {len(models) - 10} mÃ¡s."))
        print(R.dim("  0 Cancelar"))

        try:
            sel = input(R.dim("Elige: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if sel == "0":
            return
        try:
            idx = int(sel) - 1
            if idx < 0 or idx >= len(models):
                print(R.error("SelecciÃ³n invÃ¡lida."))
                return
        except ValueError:
            print(R.error("Debes introducir un nÃºmero."))
            return

        new_model = models[idx]
        result = self.mgr.switch(prov["name"], new_model)
        if result["ok"]:
            print(R.ok(f"âœ“ Conectado a {prov['name']}/{new_model}"))
            self.engine = SwitchEngine(self.mgr.adapters)
        else:
            print(R.error(f"Error: {result.get('error', 'unknown')}"))

    def _setup_readline(self) -> None:
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

    def _print_status(self) -> None:
        s = self.mgr.status()
        line = R.status_line(s["provider"], s["model"], s["total_tokens"], s["health"]["ok"])
        print(R.dim("â”€" * 60))
        print(line)
        print(R.dim("â”€" * 60))

    def _print_banner(self) -> None:
        print(R.banner())
        print()
        print(R.info("Bienvenido a BAGO 4.1.5. Escribe /help para ver comandos o /menu para navegar."))
        print(R.dim("El contexto de sesiÃ³n sobrevive al cambio de provider."))
        print()

    def _show_menu(self) -> bool:
        """Muestra un menu interactivo para acceder a funciones del chat."""
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            print(R.warn("Menu no disponible en modo no interactivo. Usa /help."))
            return True

        while True:
            lines = [
                f"{R.accent(str(i))}. {R.bold(section['title'])} â€” {section['description']}"
                for i, section in enumerate(MENU_SECTIONS, 1)
            ]
            lines.extend([
                "",
                R.dim("0. Volver al chat"),
            ])
            print(R.box("Menu de funciones", lines, width=84))
            try:
                choice = input(R.dim("Elige una seccion: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return True

            if choice in ("", "0"):
                return True

            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(MENU_SECTIONS):
                    raise ValueError
            except ValueError:
                print(R.error("Seleccion invalida."))
                continue

            result = self._show_menu_section(MENU_SECTIONS[idx])
            if result is None:
                continue
            return result

    def _show_menu_section(self, section: dict[str, Any]) -> bool | None:
        while True:
            lines = []
            for i, item in enumerate(section["items"], 1):
                suffix = f" {R.dim(item['args_prompt'])}" if item.get("args_prompt") else ""
                lines.append(
                    f"{R.accent(str(i))}. {R.bold(item['command'])}{suffix} â€” {item['description']}"
                )
            lines.extend([
                "",
                R.dim("0. Volver al menu"),
            ])
            print(R.box(section["title"], lines, width=92))
            try:
                choice = input(R.dim("Elige una opcion: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return True

            if choice in ("", "0"):
                return None

            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(section["items"]):
                    raise ValueError
            except ValueError:
                print(R.error("Seleccion invalida."))
                continue

            return self._run_menu_item(section["items"][idx])

    def _run_menu_item(self, item: dict[str, Any]) -> bool:
        command_line = item["command"]
        if item.get("confirm"):
            try:
                confirm = input(R.warn(f"Confirma {command_line} (s/N): ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return True
            if confirm not in ("s", "si", "y", "yes"):
                print(R.dim("Operacion cancelada."))
                return True

        if item.get("args_prompt"):
            try:
                tail = input(R.dim(f"{command_line} {item['args_prompt']}: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return True
            if not tail:
                print(R.dim("Operacion cancelada."))
                return True
            command_line = f"{command_line} {tail}"

        return self._handle_command(command_line)

    def _handle_command(self, line: str) -> bool:
        """Ejecuta un comando slash. Retorna True si debe continuar, False si quit."""
        result = execute(line, self.mgr, self.engine)
        if result.get("action") == "quit":
            print(R.ok(result["message"]))
            return False
        if result.get("action") == "menu":
            return self._show_menu()

        if result.get("is_chat"):
            # Not a command, should be treated as chat (fallback)
            return True

        if result["ok"]:
            print(R.ok(result["message"]))
        else:
            print(R.error(result["message"]))

        # Si fue switch exitoso, notificaciÃ³n visual extra
        if line.startswith("/switch") and result.get("ok") and result.get("result"):
            R.print_switch_notification(result["result"].__dict__ if hasattr(result["result"], "__dict__") else {})

        return True

    def _handle_chat(self, text: str) -> None:
        """EnvÃ­a mensaje al LLM y muestra respuesta. Usa streaming si estÃ¡ activo."""
        try:
            if self.mgr.config.feature_streaming and self.mgr._adapter and self.mgr._adapter.supports_streaming():
                print(R.accent("BAGO"), end=" ")
                sys.stdout.flush()
                chunks: list[str] = []
                for chunk in self.mgr.send_stream(text):
                    print(chunk, end="", flush=True)
                    chunks.append(chunk)
                print()
            else:
                response = self.mgr.send(text)
                R.print_message("assistant", response)
        except Exception as exc:
            print(R.error(f"Error de provider: {exc}"))

    def _prompt(self) -> str:
        if self._in_multiline:
            return R.dim("... ")
        return R.accent("bago") + R.bright_black(" â¯ ")

    def run(self) -> None:
        try:
            self._setup_readline()
            self._print_banner()
            self._print_init_warnings()
            self._interactive_startup()
            self._print_status()
            self.running = True

            while self.running:
                try:
                    line = input(self._prompt())
                except (EOFError, KeyboardInterrupt):
                    print()
                    print(R.ok("Bye."))
                    break

                # Multiline detection: lines starting/ending with ```
                stripped = line.strip()
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

                # Empty line
                if not stripped:
                    continue

                # Commands
                if stripped.startswith("/"):
                    if not self._handle_command(stripped):
                        break
                    self._print_status()
                    continue

                # Normal chat
                R.print_message("user", stripped)
                self._handle_chat(stripped)
                self._print_status()
        finally:
            try:
                self.mgr.save()
                print(R.dim(f"SesiÃ³n guardada automÃ¡ticamente: {self.mgr.session_id}"))
            except Exception as exc:
                print(R.warn(f"No se pudo guardar sesiÃ³n: {exc}"))
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

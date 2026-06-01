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

import json
import os
import shutil
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

# ─── Keybinds ────────────────────────────────────────────────────────────────

_KEYBINDS_PATH = Path(__file__).resolve().parents[2] / ".bago" / "keybinds.json"

_DEFAULT_KEYBINDS: dict = {
    "_hint": "↑↓ navegar   Enter seleccionar   Esc/q cancelar",
    "menu": {
        "up":     ["UP", "k"],
        "down":   ["DOWN", "j"],
        "select": ["ENTER"],
        "back":   ["ESC", "q", "LEFT"],
    },
}


def _load_keybinds() -> dict:
    try:
        return json.loads(_KEYBINDS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _DEFAULT_KEYBINDS


def _read_key() -> str:
    """Lee una pulsación y devuelve su nombre canónico.
    Lanza KeyboardInterrupt si se pulsa Ctrl+C (en raw mode no llega como señal)."""
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getwch()  # getwch: soporta Unicode (acentos en keybinds)
        if ch in ("\x00", "\xe0"):  # prefijo de tecla especial
            ch2 = msvcrt.getwch()
            return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(ch2, "")
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\r":
            return "ENTER"
        if ch == "\x1b":
            return "ESC"
        return ch
    else:
        import select
        import termios
        import tty
        fd = sys.stdin.fileno()
        try:
            old = termios.tcgetattr(fd)
        except termios.error:
            return ""  # stdin no es un TTY real
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x1b":
                # Esc solo: sin más bytes en 50ms lo tratamos como ESC (no bloquear)
                if not select.select([sys.stdin], [], [], 0.05)[0]:
                    return "ESC"
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    if not select.select([sys.stdin], [], [], 0.05)[0]:
                        return "ESC"
                    ch3 = sys.stdin.read(1)
                    return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(ch3, "ESC")
                return "ESC"
            if ch in ("\r", "\n"):
                return "ENTER"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _enable_vt() -> bool:
    """Garantiza Virtual Terminal Processing en Windows (para ANSI). True si está disponible."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        return bool(kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
    except Exception:
        return False


def _fit(text: str, width: int) -> str:
    """Recorta texto plano a `width` columnas para evitar wrap (rompería el redibujado)."""
    if width < 1:
        return ""
    if len(text) > width:
        return text[: max(1, width - 1)] + "…"
    return text


def _key_action(key: str, kb: dict, section: str = "menu") -> str:
    """Devuelve la acción asociada a una tecla según los keybinds cargados."""
    for action, keys in kb.get(section, {}).items():
        if action.startswith("_"):
            continue
        if key in keys:
            return action
    return ""


def _draw_navigate(
    title: str,
    options: list[str],
    selected: int,
    hint: str,
    redraw_lines: int = 0,
) -> int:
    """Dibuja el menú navegable. Trunca al ancho del terminal para que ninguna
    línea haga wrap (un wrap descuadraría el cursor-up del redibujado).
    Retorna el número de líneas impresas (= líneas físicas, sin wrap)."""
    cols = shutil.get_terminal_size((80, 24)).columns
    avail = max(10, cols - 5)  # margen para "  ❯ " + seguridad

    rows = []
    rows.append(f"  {R.bold(_fit(title, avail))}")
    rows.append(R.dim("  " + "─" * min(52, avail)))
    for i, opt in enumerate(options):
        cursor = R.accent("❯") if i == selected else " "
        body = _fit(opt, avail)
        text = R.bold(body) if i == selected else R.dim(body)
        rows.append(f"  {cursor} {text}")
    rows.append("")
    rows.append(R.dim(f"  {_fit(hint, avail)}"))

    if redraw_lines:
        sys.stdout.write(f"\033[{redraw_lines}A")
        for row in rows:
            sys.stdout.write("\033[2K\r" + row + "\n")
    else:
        for row in rows:
            print(row)
    sys.stdout.flush()
    return len(rows)

def _restore_windows_console() -> None:
    """Fuerza Quick Edit ON en Windows tras la navegación (decisión deliberada de UX:
    el usuario quiere poder pegar con clic derecho; lección de sesiones previas).
    No es un 'restore' del modo previo: habilita Quick Edit aunque estuviera off."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_EXTENDED_FLAGS = 0x0080
            ENABLE_QUICK_EDIT_MODE = 0x0040
            ENABLE_PROCESSED_INPUT = 0x0001
            new_mode = mode.value | ENABLE_EXTENDED_FLAGS | ENABLE_QUICK_EDIT_MODE | ENABLE_PROCESSED_INPUT
            kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass


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
            {"command": "/evolve", "description": "Autoevolucionar: reentrenar intenciones desde el historial."},
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

        self.keybinds = _load_keybinds()
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
            print(R.warn(f"⚠ Modelo '{requested}' no disponible. Usando '{actual}'."))
            if available:
                print(R.dim(f"   Modelos disponibles: {', '.join(available[:5])}"))
                if len(available) > 5:
                    print(R.dim(f"   ... y {len(available) - 5} más. Usa /models para ver todos."))
            print()

    def _interactive_startup(self) -> None:
        """Ofrece selección interactiva de provider/modelo si estamos en TTY."""
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            return

        info = getattr(self.mgr, "_init_info", {})
        if not info.get("corrected") and not self.mgr.config.get("ui.prompt_provider_on_start", False):
            return
        if info.get("corrected"):
            print(R.info("¿Quieres elegir otro modelo? (s/n)"), end=" ")
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

    def _auto_evolve_startup(self) -> None:
        """BAGO START autoevoluciona: al arrancar, reentrena el clasificador de
        intenciones con todo el historial y recarga el few-shot en caliente.

        Es una 'puerta' configurable (features.auto_evolve_on_start, por defecto
        activada). Nunca aborta el arranque: ante fallo registra culpa técnica."""
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
            # Culpa técnica visible, sin tumbar el arranque
            print(R.warn(f"Autoevolución no completada — {res.get('causa', res.get('message', '?'))}"))
            if res.get("responsable"):
                print(R.dim(f"  responsable: {res['responsable']}"))
            if res.get("prevencion"):
                print(R.dim(f"  prevención: {res['prevencion']}"))
        print()

    def _print_status(self) -> None:
        s = self.mgr.status()
        line = R.status_line(s["provider"], s["model"], s["total_tokens"], s["health"]["ok"])
        print(R.dim("─" * 60))
        print(line)
        print(R.dim("─" * 60))

    def _print_banner(self) -> None:
        print(R.banner())
        print()
        print(R.info("Bienvenido a BAGO 4.1.5. Escribe / para la paleta de comandos o pulsa Enter (Ctrl+M) para el menu."))
        print(R.dim("El contexto de sesión sobrevive al cambio de provider."))
        print()

    def _navigate(self, title: str, labels: list[str], hint: str | None = None) -> int | None:
        """Selector navegable con flechas. Retorna índice elegido o None si se cancela."""
        if not labels:
            return None
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return None
        hint = hint or self.keybinds.get("_hint", "↑↓ navegar   Enter seleccionar   Esc/q cancelar")
        vt_ok = _enable_vt()  # si falla, no usamos redibujado in-place (evita basura ANSI)
        selected = 0
        drawn = _draw_navigate(title, labels, selected, hint)
        try:
            while True:
                try:
                    key = _read_key()
                except (KeyboardInterrupt, EOFError):
                    return None
                action = _key_action(key, self.keybinds, "menu")
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
                drawn = _draw_navigate(title, labels, selected, hint, redraw_lines=drawn if vt_ok else 0)
        finally:
            _restore_windows_console()

    def _command_catalog(self) -> list[dict[str, Any]]:
        """Lista plana de todos los comandos con su sección de origen."""
        catalog: list[dict[str, Any]] = []
        for section in MENU_SECTIONS:
            for item in section["items"]:
                catalog.append({**item, "section": section["title"]})
        return catalog

    def _show_command_palette(self) -> bool:
        """Paleta navegable con TODOS los comandos y subcomandos (se abre al escribir '/')."""
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            print(R.warn("Paleta no disponible en modo no interactivo. Usa /help."))
            return True
        catalog = self._command_catalog()
        labels = []
        for it in catalog:
            args = f" {it['args_prompt']}" if it.get("args_prompt") else ""
            labels.append(f"{it['command']}{args}  —  {it['description']}")
        idx = self._navigate("Comandos de BAGO  ·  escribe / para abrir", labels)
        if idx is None:
            print(R.dim("Paleta cerrada."))
            return True
        return self._run_menu_item(catalog[idx])

    def _show_menu(self) -> bool:
        """Menu interactivo por secciones (se abre con /menu o Ctrl+M)."""
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            print(R.warn("Menu no disponible en modo no interactivo. Usa /help."))
            return True
        while True:
            labels = [
                f"{section['title']}  —  {section['description']}"
                for section in MENU_SECTIONS
            ]
            idx = self._navigate("Menu de funciones", labels)
            if idx is None:
                print(R.dim("Menu cerrado."))
                return True
            result = self._show_menu_section(MENU_SECTIONS[idx])
            if result is None:
                continue
            return result

    def _show_menu_section(self, section: dict[str, Any]) -> bool | None:
        labels = []
        for item in section["items"]:
            args = f" {item['args_prompt']}" if item.get("args_prompt") else ""
            labels.append(f"{item['command']}{args}  —  {item['description']}")
        idx = self._navigate(section["title"], labels)
        if idx is None:
            return None
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

        # Si fue switch exitoso, notificación visual extra
        if line.startswith("/switch") and result.get("ok") and result.get("result"):
            R.print_switch_notification(result["result"].__dict__ if hasattr(result["result"], "__dict__") else {})

        return True

    def _handle_chat(self, text: str) -> None:
        """Envía mensaje al LLM y muestra respuesta. Usa streaming si está activo."""
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
        return R.accent("bago") + R.bright_black(" ❯ ")

    def run(self) -> None:
        try:
            self._setup_readline()
            self._print_banner()
            self._print_init_warnings()
            self._auto_evolve_startup()
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

                # Empty line (Enter solo = Ctrl+M) → abre el menu interactivo en TTY
                if not stripped:
                    if not (sys.stdin.isatty() and sys.stdout.isatty()):
                        continue
                    if not self._show_menu():
                        break
                    self._print_status()
                    continue

                # "/" solo → paleta navegable con todos los comandos
                if stripped == "/":
                    if not self._show_command_palette():
                        break
                    self._print_status()
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

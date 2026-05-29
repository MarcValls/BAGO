"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               BAGO  —  REGLAS OBLIGATORIAS DE MENÚS / UI                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  REGLA 1 — Widget correcto para cada tipo de interacción:                  ║
║   · Una opción de N (radio/pick)     →  _menu_pick()                       ║
║   · Opciones ON/OFF + acciones       →  _toggle_menu()                     ║
║   · Varias de N (checkbox)           →  _menu_multiselect()                ║
║   · Confirmación Sí / No             →  _menu_confirm()                    ║
║   · Entrada de texto libre           →  _menu_input()                      ║
║   · Botones de acción directa        →  _menu_action()                     ║
║                                                                              ║
║  REGLA 2 — Cuándo usar botones explícitos:                                 ║
║   _menu_multiselect: Aceptar/Cancelar  (N de N, confirma selección)        ║
║   _menu_confirm:     Sí/No             (decisión binaria irreversible)      ║
║   _menu_input:       OK/Cancel         (texto libre, necesita confirmación) ║
║   _menu_pick:        sin botones       (elegir ítem = acción inmediata)     ║
║   _toggle_menu:      sin botones       (toggles se aplican al elegir acción)║
║                                                                              ║
║  REGLA 3 — Un único camino de salida:                                      ║
║   Nunca duplicar la salida con ítem "__exit__" Y botón Cancelar.           ║
║   Solo un mecanismo: Esc / C-c.                                             ║
║                                                                              ║
║  REGLA 4 — Esc = atrás / sin ejecutar:                                     ║
║   Esc cierra sin ejecutar ninguna acción ni guardar ningún estado.         ║
║   En _toggle_menu: el llamador descarta result["toggles"] cuando           ║
║   result["action"] is None  —  Esc nunca aplica cambios.                   ║
║                                                                              ║
║  REGLA 5 — ON/OFF usa _toggle_menu; vocabulario diferenciado:              ║
║   ELEGIR  = ítem acción + Enter  →  cierra el menú                         ║
║   CONMUTAR = toggle + Space/Enter →  edición in-place, NO cierra           ║
║   Esc → cierra; llamador descarta cambios (action is None)                 ║
║                                                                              ║
║  REGLA 6 — Sin bucles implícitos en el widget:                             ║
║   ELEGIR una acción cierra el menú.  CONMUTAR no cierra (no es bucle).     ║
║   Si el llamador necesita volver al menú tras sub-acción → while True.     ║
║                                                                              ║
║  REGLA 7 — Hint de teclas siempre visible al pie del menú:                 ║
║   Formato:  "Arriba/Abajo navegar   [tecla específica]   Esc volver"       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from pathlib import Path

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import re
import threading
import shutil as _shutil
import getpass
import os
import sys


def _enable_win_vt() -> bool:
    """Activa Virtual Terminal en Windows cuando sea posible."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-11)
        mode = ctypes.c_ulong(0)
        if k32.GetConsoleMode(handle, ctypes.byref(mode)):
            return bool(k32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        pass
    return False


_VT_OK = _enable_win_vt()


def _strip_rich(text: str) -> str:
    """Elimina etiquetas de markup Rich de un string para usarlo en prompt_toolkit."""
    return re.sub(r"\[/?[^\[\]]*\]", "", text)

_PROMPT_TOOLKIT_AVAILABLE = os.environ.get("BAGO_NO_PROMPT_TOOLKIT", "0") != "1"
try:
    if not _PROMPT_TOOLKIT_AVAILABLE:
        raise ModuleNotFoundError("prompt_toolkit disabled by BAGO_NO_PROMPT_TOOLKIT=1")
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import FormattedTextControl, Layout, HSplit, Window
    from prompt_toolkit.shortcuts import button_dialog, checkboxlist_dialog, input_dialog, yes_no_dialog
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import Frame, Label
except ModuleNotFoundError:
    _PROMPT_TOOLKIT_AVAILABLE = False
    Application = KeyBindings = FormattedTextControl = Layout = HSplit = Window = None
    button_dialog = checkboxlist_dialog = input_dialog = yes_no_dialog = None
    Frame = Label = None

    class Style:
        @staticmethod
        def from_dict(data):
            return data

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .constants import COLORS, BAGO_VERSION

console = Console(force_terminal=sys.stdout.isatty() and _VT_OK, highlight=False, markup=True,
                  safe_box=True, emoji=False)

_PT_FALLBACK_WARNED = False


def _install_prompt_toolkit() -> bool:
    """Intenta instalar prompt_toolkit vía pip. Devuelve True si éxito."""
    import subprocess, sys
    try:
        console.print("[cyan]  Instalando prompt_toolkit...[/cyan]")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "prompt_toolkit", "-q"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            console.print("[green]  ✓ prompt_toolkit instalado. Reinicia BAGO para activar.[/green]")
            return True
        else:
            console.print(f"[red]  ✗ Error: {result.stderr[:200]}[/red]")
            return False
    except Exception as exc:
        console.print(f"[red]  ✗ No se pudo instalar: {exc}[/red]")
        return False


def _warn_prompt_toolkit_fallback():
    global _PT_FALLBACK_WARNED
    if _PT_FALLBACK_WARNED:
        return
    _PT_FALLBACK_WARNED = True
    console.print(
        "[yellow]prompt_toolkit no instalado. Usando UI básica por texto.[/yellow]\n"
        "[dim]Para experiencia completa: pip install prompt_toolkit[/dim]"
    )
    if sys.stdin.isatty():
        ans = input("  ¿Instalar ahora? [s/n] ").strip().lower()
        if ans in ("s", "si", "y", "yes"):
            if _install_prompt_toolkit():
                console.print("[dim]  Reinicia BAGO para usar prompt_toolkit.[/dim]")


def _stdin_prompt(label: str, is_password: bool = False) -> str:
    try:
        if is_password:
            return getpass.getpass(label)
        return input(label)
    except (EOFError, KeyboardInterrupt):
        return ""

def show_response(text, model_name, provider, label=None):
    try:    content = Markdown(text)
    except: content = text
    if label:
        title = label
        border = COLORS.get(provider, "cyan")
    else:
        via = ""
        if model_name and model_name not in ("BAGO", "sin-modelo", ""):
            via = f"  [dim]vía {model_name}/{provider}[/dim]"
        title = f"[bold cyan]BAGO[/bold cyan]{via}"
        border = "cyan"
    cols = _shutil.get_terminal_size((80, 24)).columns
    width = max(60, min(cols - 2, 120))
    console.print(Panel(content, title=title, border_style=border, box=box.ROUNDED, width=width))

pi = lambda m: console.print(f"[dim cyan]  {m}[/dim cyan]")
pe = lambda m: console.print(f"[bold red]  X {m}[/bold red]")


class CtrlCGuard:
    """
    Protección contra Ctrl+C accidental en el REPL principal de BAGO.

    Comportamiento:
      1ª pulsación  → avisa que copiar = clic derecho; pide 2 más para salir.
      2ª pulsación  → avisa que queda 1 pulsación para salir.
      3ª pulsación  → devuelve True → el caller termina.

    El contador se resetea si pasan más de TIMEOUT segundos sin nueva pulsación.
    """
    TIMEOUT = 3.0   # segundos entre pulsaciones para considerarlas "seguidas"

    _W  = "\033[1;33m"   # amarillo negrita
    _R  = "\033[1;31m"   # rojo negrita
    _D  = "\033[2m"      # dim
    _X  = "\033[0m"      # reset

    def __init__(self):
        self._count = 0
        self._timer: threading.Timer | None = None

    def _reset(self):
        self._count = 0
        self._timer = None

    def _restart_timer(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.TIMEOUT, self._reset)
        self._timer.daemon = True
        self._timer.start()

    def press(self) -> bool:
        """
        Llama en cada KeyboardInterrupt del REPL.
        Devuelve True sólo en la 3ª pulsación consecutiva (el caller debe salir).
        """
        self._count += 1
        self._restart_timer()

        if self._count == 1:
            print(
                f"\n{self._W}  ℹ  Para COPIAR usa clic derecho "
                f"(o Ctrl+Shift+C en terminales que lo soporten).{self._X}\n"
                f"{self._D}     Pulsa Ctrl+C dos veces más seguidas para salir de BAGO.{self._X}"
            )
            return False
        elif self._count == 2:
            print(
                f"\n{self._R}  ⚠  Una pulsación más de Ctrl+C para salir de BAGO.{self._X}"
            )
            return False
        else:
            if self._timer:
                self._timer.cancel()
            print(f"\n{self._R}  🛑  Saliendo de BAGO...{self._X}")
            return True


def banner(session, health: "dict | None" = None):
    active = session.creds.active_bago_providers()
    c = COLORS.get(session.provider, "white")

    # ── Indicadores de provider con color real ────────────────────────────────
    def _provider_badge(p: str) -> str:
        if health:
            h = health.get(p, {})
            if h.get("ok"):
                col = "green"
                detail = h.get("detail", "")
                # Para Ollama sin modelos: amarillo
                if p == "ollama-local" and not h.get("models"):
                    col = "yellow"
                suffix = f" [dim]{detail}[/dim]" if detail else ""
                return f"[{col}]●[/{col}] [{col}]{p}[/{col}]{suffix}"
            else:
                return f"[red]●[/red] [red]{p}[/red]"
        else:
            col = "green" if p in active else "red"
            return f"[{col}]●[/{col}] [{col}]{p}[/{col}]"

    prov_keys = list(COLORS.keys())
    badges = "  ".join(_provider_badge(p) for p in prov_keys)

    # ── Modos activos ──────────────────────────────────────────────────────────
    def _flag(label, on, on_color="cyan"):
        if on:
            return f"[bold {on_color}]{label}[/bold {on_color}]"
        return f"[dim]{label}: OFF[/dim]"

    modo_str  = f"[bold]{session.orch_mode.upper()}[/bold]"
    auto_str  = _flag("AUTONOMO", session.autonomous, "yellow")
    plan_str  = _flag("PLAN", session.plan_mode, "magenta")
    brain_str = _flag("BRAINSTORM", session.brainstorm, "green")

    # ── Traza de routing ───────────────────────────────────────────────────────
    rt = session.last_route or {}
    rt_mode   = rt.get("mode", "manual").upper()
    rt_model  = rt.get("model", session.model_name)
    rt_prov   = rt.get("provider", session.provider)
    rt_reason = rt.get("reason", "—")
    routing_line = (
        f"[dim]Routing: [bold]{rt_mode}[/bold] "
        f"→ [{c}]{rt_model}[/{c}] / {rt_prov}  "
        f"[italic]\"{rt_reason}\"[/italic][/dim]"
    )

    try:
        console.print(Panel(
            f"[bold cyan]BAGO CLI  v{BAGO_VERSION}[/bold cyan]  [dim]·  A.M. TECHNOLOGIES[/dim]\n"
            f"[dim]Motor: [{c}]{session.model_name}[/{c}] ({session.provider})[/dim]\n"
            f"{badges}\n"
            f"\n"
            f"Modo: {modo_str}   {auto_str}   {plan_str}   {brain_str}\n"
            f"{routing_line}\n"
            f"[dim]Escalado automático: local → local-grande → cloud[/dim]",
            box=box.ROUNDED, border_style="cyan", width=82))
        console.print("[dim]  [bold cyan]/[/bold cyan]  menú[/dim]")
    except Exception:
        print(f"\n=== BAGO CLI v{BAGO_VERSION} · A.M. TECHNOLOGIES ===")
        print(f"Motor: {session.model_name} ({session.provider})")
        print(f"Modo: {session.orch_mode.upper()} | Autónomo: {session.autonomous} | Plan: {session.plan_mode} | Brainstorm: {session.brainstorm}")
        print(f"Routing: {rt_mode} → {rt_model} ({rt_prov}) — {rt_reason}")
        print("/ para menú\n")


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

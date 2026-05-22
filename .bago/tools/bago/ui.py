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

import re
import threading
import shutil as _shutil
import getpass
import os


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

console = Console(force_terminal=True, highlight=False, markup=True,
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


_MENU_STYLE = Style.from_dict({
    "dialog":             "bg:#1e1e2e",
    "dialog.body":        "bg:#1e1e2e fg:#cdd6f4",
    "dialog frame.label": "fg:#89b4fa bold",
    "frame.border":       "fg:#45475a",
    "button":             "bg:#313244 fg:#cdd6f4",
    "button.focused":     "bg:#89b4fa fg:#1e1e2e bold",
    "label":              "bg:#1e1e2e fg:#6c7086",
    # _menu_pick — contraste por fila
    "pick.cursor":        "fg:#89b4fa bold",          # '>>' azul brillante
    "pick.focused":       "bg:#313244 fg:#cdf4a1 bold",  # fila activa: fondo + texto claro
    "pick.item":          "fg:#585b70",               # filas inactivas: gris tenue
    "pick.sep":           "bold",                      # separador — visible en cualquier terminal
    # conmutadores
    "toggle.on":          "bg:ansibrightgreen fg:ansiblack bold",
    "toggle.off":         "bg:#444444 fg:#888888",
    "toggle.cursor":      "fg:#89b4fa bold",
})

# ---------------------------------------------------------------------------
# _menu_pick — seleccion unica con contraste visual completo
# ---------------------------------------------------------------------------

def _menu_pick(title: str, text: str, values: list):
    """
    Menu de seleccion unica con cursor y contraste por fila.
    values: lista de (key, label)  o  None como separador ("sep", "──...")
    Enter sobre un item => acepta inmediatamente.
    Esc / Ctrl-C => cancela (devuelve None).
    Sin botones OK/Cancelar.  (R1 / R2)

    MODO PESTAÑAS (tipo BIOS): se activa automáticamente cuando hay más
    de 15 items navegables. Los separadores (key=None) delimitan pestañas.
    Tab/Shift+Tab cambia de pestaña. Flechas navegan dentro.
    """
    if not values:
        return None

    # --- Preprocesar: separar en pestañas por grupos delimitados por None ---
    tabs = []
    current_tab = []
    tab_labels = []
    current_label = None
    for key, label in values:
        if key is None:
            next_label = _strip_rich(label).strip("- ─")
            if not next_label:
                next_label = f"Grupo {len(tabs)+1}"
            if current_label is not None and current_tab:
                tab_labels.append(current_label)
                tabs.append(current_tab)
                current_tab = []
            current_label = next_label
        else:
            current_tab.append((key, label))
    if current_tab:
        tab_labels.append(current_label or f"Grupo {len(tabs)+1}")
        tabs.append(current_tab)
    # Si solo hay 1 tab o pocos items, comportamiento clásico
    use_tabs = len(tabs) > 1 and sum(len(t) for t in tabs) > 15

    if not _PROMPT_TOOLKIT_AVAILABLE:
        _warn_prompt_toolkit_fallback()
        if use_tabs:
            console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
            for ti, (tlabel, trows) in enumerate(zip(tab_labels, tabs), start=1):
                console.print(f"\n[bold cyan]── {ti}. {tlabel} ──[/bold cyan]")
                for idx, (_, lbl) in enumerate(trows, start=1):
                    console.print(f"  {idx}. {_strip_rich(lbl)}")
            raw = _stdin_prompt("Pestaña número (Enter cancela): ").strip()
            if not raw:
                return None
            try:
                tpos = int(raw)
            except ValueError:
                return None
            if tpos < 1 or tpos > len(tabs):
                return None
            rows = tabs[tpos - 1]
            if not rows:
                return None
            raw = _stdin_prompt("Ítem número (Enter cancela): ").strip()
            if not raw:
                return None
            try:
                ipos = int(raw)
            except ValueError:
                return None
            if ipos < 1 or ipos > len(rows):
                return None
            return rows[ipos - 1][0]
        else:
            rows = [(k, _strip_rich(lbl)) for k, lbl in values if k is not None]
            if not rows:
                return None
            console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
            for idx, (_, lbl) in enumerate(rows, start=1):
                console.print(f"  {idx}. {lbl}")
            raw = _stdin_prompt("Selecciona número (Enter cancela): ").strip()
            if not raw:
                return None
            try:
                pos = int(raw)
            except ValueError:
                return None
            if pos < 1 or pos > len(rows):
                return None
            return rows[pos - 1][0]

    # --- Modo prompt_toolkit ---
    if use_tabs:
        return _menu_pick_tabs(title, text, tab_labels, tabs)

    # Índices navegables (excluye separadores marcados como None en key)
    nav_idx = [i for i, v in enumerate(values) if v[0] is not None]
    if not nav_idx:
        return None

    focus = [0]   # posición dentro de nav_idx
    result = [None]

    def render():
        out = []
        for i, (key, label) in enumerate(values):
            clean = _strip_rich(label)
            # Separador
            if key is None:
                out.append(("class:pick.sep", f"    {clean}\n"))
                continue
            is_focused = (i == nav_idx[focus[0]])
            if is_focused:
                out.append(("class:pick.cursor", " >> "))
                out.append(("class:pick.focused", f" {clean} \n"))
            else:
                out.append(("", "    "))
                out.append(("class:pick.item", f" {clean} \n"))
        return out

    content = FormattedTextControl(render, focusable=True)
    win = Window(content=content, dont_extend_height=True)

    kb = KeyBindings()

    @kb.add("up",   eager=True)
    @kb.add("k",    eager=True)
    def _up(event):
        focus[0] = max(0, focus[0] - 1)
        event.app.invalidate()

    @kb.add("down", eager=True)
    @kb.add("j",    eager=True)
    def _down(event):
        focus[0] = min(len(nav_idx) - 1, focus[0] + 1)
        event.app.invalidate()

    @kb.add("enter", eager=True)
    def _accept(event):
        result[0] = values[nav_idx[focus[0]]][0]
        event.app.exit()

    @kb.add("escape", eager=True)
    @kb.add("c-c",    eager=True)
    def _cancel(event):
        event.app.exit()

    layout = Layout(
        Frame(
            HSplit([
                Label(f" {_strip_rich(text)}"),
                Window(height=1),
                win,
                Window(height=1),
                Label(" ↑/↓  navegar    Enter  seleccionar    Esc  volver",
                      style="class:label"),
            ]),
            title=f" {title} ",
            style="class:dialog",
        ),
        focused_element=win,
    )

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=_MENU_STYLE,
        full_screen=False,
        mouse_support=True,
    )
    try:
        app.run()
    except Exception:
        pass
    return result[0]


def _menu_pick_tabs(title: str, text: str, tab_labels: list, tabs: list):
    """Modo pestañas tipo BIOS para menus grandes."""
    active_tab = [0]
    focus = [0]   # posición dentro de la pestaña activa
    result = [None]

    def render_tab_bar():
        out = []
        out.append(("", "  "))
        for ti, tlabel in enumerate(tab_labels):
            if ti == active_tab[0]:
                out.append(("class:pick.focused", f" ┌─ {tlabel} ─┐ "))
            else:
                out.append(("class:pick.item", f"  {tlabel}  "))
            if ti < len(tab_labels) - 1:
                out.append(("class:pick.sep", "│"))
        out.append(("", "\n"))
        return out

    def render_items():
        out = []
        current = tabs[active_tab[0]]
        for fi, (key, label) in enumerate(current):
            clean = _strip_rich(label)
            is_focused = (fi == focus[0])
            if is_focused:
                out.append(("class:pick.cursor", " >> "))
                out.append(("class:pick.focused", f" {clean} \n"))
            else:
                out.append(("", "    "))
                out.append(("class:pick.item", f" {clean} \n"))
        return out

    def render():
        return render_tab_bar() + render_items()

    content = FormattedTextControl(render, focusable=True)
    win = Window(content=content, dont_extend_height=True)

    kb = KeyBindings()

    @kb.add("up", eager=True)
    @kb.add("k",  eager=True)
    def _up(event):
        focus[0] = max(0, focus[0] - 1)
        event.app.invalidate()

    @kb.add("down", eager=True)
    @kb.add("j", eager=True)
    def _down(event):
        current = tabs[active_tab[0]]
        focus[0] = min(len(current) - 1, focus[0] + 1)
        event.app.invalidate()

    @kb.add("tab", eager=True)
    def _next_tab(event):
        active_tab[0] = (active_tab[0] + 1) % len(tabs)
        focus[0] = 0
        event.app.invalidate()

    @kb.add("s-tab", eager=True)
    def _prev_tab(event):
        active_tab[0] = (active_tab[0] - 1) % len(tabs)
        focus[0] = 0
        event.app.invalidate()

    @kb.add("right", eager=True)
    @kb.add("l", eager=True)
    def _right(event):
        active_tab[0] = (active_tab[0] + 1) % len(tabs)
        focus[0] = 0
        event.app.invalidate()

    @kb.add("left", eager=True)
    @kb.add("h", eager=True)
    def _left(event):
        active_tab[0] = (active_tab[0] - 1) % len(tabs)
        focus[0] = 0
        event.app.invalidate()

    @kb.add("enter", eager=True)
    def _accept(event):
        current = tabs[active_tab[0]]
        result[0] = current[focus[0]][0]
        event.app.exit()

    @kb.add("escape", eager=True)
    @kb.add("c-c", eager=True)
    def _cancel(event):
        event.app.exit()

    layout = Layout(
        Frame(
            HSplit([
                Label(f" {_strip_rich(text)}"),
                Window(height=1),
                win,
                Window(height=1),
                Label(" ←/→  pestaña    ↑/↓  item    Enter  seleccionar    Esc  volver",
                      style="class:label"),
            ]),
            title=f" {title} ",
            style="class:dialog",
        ),
        focused_element=win,
    )

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=_MENU_STYLE,
        full_screen=False,
        mouse_support=True,
    )
    try:
        app.run()
    except Exception:
        pass
    return result[0]


# ---------------------------------------------------------------------------
# _toggle_menu — panel con conmutadores ON/OFF y acciones
# ---------------------------------------------------------------------------

def _toggle_menu(title: str, text: str, items: list):
    """
    Panel que mezcla conmutadores ON/OFF y acciones normales.

    Formato de items:
      {"type": "toggle", "key": "k", "label": "Etiqueta", "value": True/False}
      {"type": "action", "key": "k", "label": "Etiqueta"}
      {"type": "sep"}   -- separador visual

    Teclas:
      Arriba / Abajo (o j/k) : navegar
      Espacio                 : conmutar toggle (sin cerrar menu)
      Enter  en toggle        : conmutar (sin cerrar)
      Enter  en accion        : cerrar y devolver accion
      Esc / Ctrl-C            : cerrar (devuelve action=None)

    Devuelve:
      {"action": key_o_None, "toggles": {key: bool_actual, ...}}
    """
    if not items:
        return {"action": None, "toggles": {}}

    # Estado mutable de los toggles
    state = {
        item["key"]: bool(item.get("value", False))
        for item in items if item.get("type") == "toggle"
    }

    if not _PROMPT_TOOLKIT_AVAILABLE:
        _warn_prompt_toolkit_fallback()
        while True:
            console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
            options = []
            idx = 1
            for item in items:
                itype = item.get("type", "action")
                if itype == "sep":
                    continue
                label = _strip_rich(item.get("label", ""))
                if itype == "toggle":
                    label = f"[{'ON' if state[item['key']] else 'OFF'}] {label}"
                console.print(f"  {idx}. {label}")
                options.append(item)
                idx += 1
            console.print("  q. salir")
            raw = _stdin_prompt("Elige opción: ").strip().lower()
            if not raw or raw == "q":
                return {"action": None, "toggles": dict(state)}
            try:
                pos = int(raw)
            except ValueError:
                continue
            if pos < 1 or pos > len(options):
                continue
            selected = options[pos - 1]
            if selected.get("type") == "toggle":
                state[selected["key"]] = not state[selected["key"]]
                continue
            return {"action": selected.get("key"), "toggles": dict(state)}

    # Indices navegables (excluye separadores)
    nav_idx = [i for i, it in enumerate(items) if it.get("type") != "sep"]
    focus = [0]  # posicion en nav_idx

    result = {"action": None, "toggles": {}}

    def current_item():
        return items[nav_idx[focus[0]]]

    # --- Renderizado ---
    def render():
        out = []
        for i, item in enumerate(items):
            itype = item.get("type", "action")

            if itype == "sep":
                out += [("class:label", "  "), ("class:label", "-" * 40 + "\n")]
                continue

            is_focused = (i == nav_idx[focus[0]])

            if is_focused:
                out.append(("class:toggle.cursor", " >> "))
            else:
                out.append(("", "    "))

            if itype == "toggle":
                val = state[item["key"]]
                if val:
                    out.append(("class:toggle.on",  " ON  "))
                else:
                    out.append(("class:toggle.off", " OFF "))
                out.append(("", "  "))

            lbl = _strip_rich(item.get("label", ""))
            if is_focused:
                out.append(("bold", lbl + "\n"))
            else:
                out.append(("", lbl + "\n"))

        return out

    content = FormattedTextControl(render, focusable=True)
    win = Window(content=content, dont_extend_height=True)

    kb = KeyBindings()

    @kb.add("up",   eager=True)
    @kb.add("k",    eager=True)
    def _up(event):
        focus[0] = max(0, focus[0] - 1)
        event.app.invalidate()

    @kb.add("down", eager=True)
    @kb.add("j",    eager=True)
    def _down(event):
        focus[0] = min(len(nav_idx) - 1, focus[0] + 1)
        event.app.invalidate()

    def _do_toggle(event):
        item = current_item()
        if item.get("type") == "toggle":
            state[item["key"]] = not state[item["key"]]
            event.app.invalidate()
        else:
            result["action"]  = item["key"]
            result["toggles"] = dict(state)
            event.app.exit()

    @kb.add("space", eager=True)
    def _space(event): _do_toggle(event)

    @kb.add("enter", eager=True)
    def _enter(event): _do_toggle(event)

    @kb.add("escape", eager=True)
    @kb.add("c-c",    eager=True)
    def _cancel(event):
        result["action"]  = None
        result["toggles"] = dict(state)
        event.app.exit()

    layout = Layout(
        Frame(
            HSplit([
                Label(f" {_strip_rich(text)}"),
                Window(height=1),
                win,
                Window(height=1),
                Label(" Arriba/Abajo navegar   Espacio/Enter conmutar o seleccionar   Esc volver",
                      style="class:label"),
            ]),
            title=f" {title} ",
            style="class:dialog",
        ),
        focused_element=win,
    )

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=_MENU_STYLE,
        full_screen=False,
        mouse_support=True,
    )
    try:
        app.run()
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# _menu_multiselect — checkboxlist (varios de N, con botones)
# ---------------------------------------------------------------------------

def _menu_multiselect(title: str, text: str, values: list, defaults: list = None):
    """Checkboxlist: el usuario marca varias opciones y confirma con Aceptar."""
    if not _PROMPT_TOOLKIT_AVAILABLE:
        _warn_prompt_toolkit_fallback()
        rows = list(values or [])
        if not rows:
            return []
        console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
        for idx, (_, lbl) in enumerate(rows, start=1):
            console.print(f"  {idx}. {_strip_rich(lbl)}")
        raw = _stdin_prompt("Números separados por coma (Enter cancela): ").strip()
        if not raw:
            return None
        out = []
        for tok in raw.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                pos = int(tok)
            except ValueError:
                continue
            if 1 <= pos <= len(rows):
                out.append(rows[pos - 1][0])
        return out
    try:
        return checkboxlist_dialog(
            title=title, text=text,
            values=values,
            default_values=defaults or [],
            ok_text="Aceptar",
            cancel_text="Cancelar",
            style=_MENU_STYLE,
        ).run()
    except Exception:
        return None


# Alias de compatibilidad
def _menu_select(title, text, values, cancel_label=None, ok_label=None):
    return _menu_pick(title, text, values)


def _menu_action(title, text, buttons):
    if not _PROMPT_TOOLKIT_AVAILABLE:
        _warn_prompt_toolkit_fallback()
        rows = list(buttons or [])
        if not rows:
            return None
        console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
        for idx, (lbl, _) in enumerate(rows, start=1):
            console.print(f"  {idx}. {_strip_rich(lbl)}")
        raw = _stdin_prompt("Selecciona número (Enter cancela): ").strip()
        if not raw:
            return None
        try:
            pos = int(raw)
        except ValueError:
            return None
        if pos < 1 or pos > len(rows):
            return None
        return rows[pos - 1][1]
    try:
        return button_dialog(title=title, text=text,
                             buttons=buttons, style=_MENU_STYLE).run()
    except Exception:
        return None

def _menu_input(title, text, default=""):
    if not _PROMPT_TOOLKIT_AVAILABLE:
        _warn_prompt_toolkit_fallback()
        console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
        raw = _stdin_prompt(f"[{default}] > " if default else "> ")
        if raw == "":
            return default
        return raw
    try:
        return input_dialog(title=title, text=text,
                            default=default, style=_MENU_STYLE).run()
    except Exception:
        return None

def _menu_confirm(title, text):
    if not _PROMPT_TOOLKIT_AVAILABLE:
        _warn_prompt_toolkit_fallback()
        console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
        raw = _stdin_prompt("¿Sí/No? [s/N]: ").strip().lower()
        return raw in ("s", "si", "y", "yes")
    try:
        return yes_no_dialog(title=title, text=text,
                             yes_text="Sí",
                             no_text="No",
                             style=_MENU_STYLE).run()
    except Exception:
        return False

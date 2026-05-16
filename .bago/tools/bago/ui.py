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

import threading

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, HSplit, Window
from prompt_toolkit.shortcuts import button_dialog, checkboxlist_dialog, input_dialog, yes_no_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, Label
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .constants import COLORS, BAGO_VERSION

console = Console(force_terminal=True, highlight=False, markup=True,
                  safe_box=True, emoji=False)

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
    console.print(Panel(content, title=title, border_style=border, box=box.ROUNDED))

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


def banner(session):
    active = session.creds.active_bago_providers()
    c = COLORS.get(session.provider, "white")
    providers_str = "  ".join(
        f"[{'green' if p in active else 'red'}]{p}[/{'green' if p in active else 'red'}]"
        for p in COLORS
    )

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
            f"Providers: {providers_str}\n"
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
    "pick.sep":           "fg:#313244",               # separador
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
    """
    if not values:
        return None

    # Índices navegables (excluye separadores marcados como None en key)
    nav_idx = [i for i, v in enumerate(values) if v[0] is not None]
    if not nav_idx:
        return None

    focus = [0]   # posición dentro de nav_idx
    result = [None]

    def render():
        out = []
        for i, (key, label) in enumerate(values):
            # Separador
            if key is None:
                out.append(("class:pick.sep", f"    {label}\n"))
                continue
            is_focused = (i == nav_idx[focus[0]])
            if is_focused:
                out.append(("class:pick.cursor", " >> "))
                out.append(("class:pick.focused", f" {label} \n"))
            else:
                out.append(("", "    "))
                out.append(("class:pick.item", f" {label} \n"))
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
                Label(f" {text}"),
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

            lbl = item.get("label", "")
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
                Label(f" {text}"),
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
    try:
        return button_dialog(title=title, text=text,
                             buttons=buttons, style=_MENU_STYLE).run()
    except Exception:
        return None

def _menu_input(title, text, default=""):
    try:
        return input_dialog(title=title, text=text,
                            default=default, style=_MENU_STYLE).run()
    except Exception:
        return None

def _menu_confirm(title, text):
    try:
        return yes_no_dialog(title=title, text=text,
                             yes_text="Si",
                             no_text="No",
                             style=_MENU_STYLE).run()
    except Exception:
        return False

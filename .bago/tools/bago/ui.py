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

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, HSplit, Window
from prompt_toolkit.shortcuts import button_dialog, checkboxlist_dialog, input_dialog, yes_no_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, Label, RadioList
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .constants import COLORS

console = Console(force_terminal=True, highlight=False, markup=True,
                  safe_box=True, emoji=False)

def show_response(text, model_name, provider, label=None):
    c = COLORS.get(provider, "white")
    try:    content = Markdown(text)
    except: content = text
    title = label or f"[{c}]{model_name}[/{c}] . [dim]{provider}[/dim]"
    console.print(Panel(content, title=title, border_style=c, box=box.ROUNDED))

pi = lambda m: console.print(f"[dim cyan]  {m}[/dim cyan]")
pe = lambda m: console.print(f"[bold red]  X {m}[/bold red]")

def banner(session):
    active = session.creds.active_bago_providers()
    c = COLORS.get(session.provider, "white")
    providers_str = "  ".join(f"[{'green' if p in active else 'red'}]{p}[/{'green' if p in active else 'red'}]"
                               for p in COLORS)
    try:
        console.print(Panel(
            f"[bold {c}]BAGO Orchestrator HUB[/bold {c}]  >>  [{c}]{session.model_name}[/{c}] ({session.provider})\n"
            f"[dim]Routing: {session.last_route.get('mode','manual').upper()} | motivo: {session.last_route.get('reason','--')}[/dim]\n"
            f"Providers: {providers_str}\n"
            "[dim]Modo automatico activo | /help para comandos   /login para registrar providers[/dim]",
            box=box.ASCII, border_style=c))
    except Exception:
        print(f"\n=== BAGO Orchestrator HUB === [{session.model_name}] ({session.provider})")
        print(f"Providers: {', '.join(COLORS.keys())}")
        print("Modo automatico activo | /help para comandos\n")


_MENU_STYLE = Style.from_dict({
    "dialog":             "bg:#1e1e2e",
    "dialog.body":        "bg:#1e1e2e fg:#cdd6f4",
    "dialog frame.label": "fg:#89b4fa bold",
    "frame.border":       "fg:#313244",
    "button":             "bg:#313244 fg:#cdd6f4",
    "button.focused":     "bg:#89b4fa fg:#1e1e2e bold",
    "radio-list":         "bg:#1e1e2e fg:#cdd6f4",
    "radio-selected":     "fg:#a6e3a1 bold",
    "label":              "bg:#1e1e2e fg:#6c7086",
    # conmutadores
    "toggle.on":          "bg:ansibrightgreen fg:ansiblack bold",
    "toggle.off":         "bg:#444444 fg:#888888",
    "toggle.cursor":      "fg:#89b4fa bold",
})

# ---------------------------------------------------------------------------
# _menu_pick — seleccion unica instantanea (sin botones)
# ---------------------------------------------------------------------------

def _menu_pick(title: str, text: str, values: list):
    """
    Menu de seleccion unica.
    Enter sobre un item => acepta inmediatamente.
    Esc / Ctrl-C => cancela (devuelve None).
    Sin botones OK/Cancelar.
    """
    if not values:
        return None

    radio = RadioList(values=values)
    _result = [None]
    kb = KeyBindings()

    @kb.add("enter", eager=True)
    def _accept(event):
        _result[0] = radio.current_value
        event.app.exit()

    @kb.add("escape", eager=True)
    @kb.add("c-c", eager=True)
    def _cancel(event):
        event.app.exit()

    layout = Layout(
        Frame(
            HSplit([
                Label(f" {text}"),
                Window(height=1),
                radio,
                Window(height=1),
                Label(" Arriba/Abajo navegar   Enter seleccionar   Esc volver",
                      style="class:label"),
            ]),
            title=f" {title} ",
            style="class:dialog",
        )
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
    return _result[0]


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

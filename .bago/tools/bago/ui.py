
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
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
    title = label or f"[{c}]{model_name}[/{c}] · [dim]{provider}[/dim]"
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
})


def _menu_pick(title: str, text: str, values: list):
    """
    Menu de seleccion unica — SIN botones.
    Seleccionar una opcion con Enter la acepta de inmediato.
    Esc / Ctrl-C cancela y devuelve None.

    Usar para TODO menú radiolist (una opcion de N).
    Para seleccion multiple usar _menu_multiselect.
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
        event.app.exit()  # _result queda None

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


def _menu_multiselect(title: str, text: str, values: list, defaults: list = None):
    """
    Menu de seleccion multiple (checkboxlist).
    SI tiene botones Aceptar/Cancelar porque el usuario marca
    varias opciones antes de confirmar el conjunto.
    Devuelve lista de valores seleccionados, o None si cancela.
    """
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


# Alias de compatibilidad — los menus existentes que llamen _menu_select
# usaran la nueva logica instantanea.
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

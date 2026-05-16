
from prompt_toolkit.shortcuts import button_dialog, input_dialog, radiolist_dialog, yes_no_dialog
from prompt_toolkit.styles import Style
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
    title = label or f"[{c}]{model_name}[/{c}]"
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
            f"Providers: {providers_str}\n"
            "[dim]Modo automatico activo | /help para comandos   /login para registrar providers[/dim]",
            box=box.ASCII, border_style=c))
    except Exception:
        print(f"\n=== BAGO Orchestrator HUB === [{session.model_name}] ({session.provider})")
        print(f"Providers: {', '.join(COLORS.keys())}")
        print("Modo automatico activo | /help para comandos\n")


_MENU_STYLE = Style.from_dict({
    "dialog":            "bg:#1e1e2e",
    "dialog.body":       "bg:#1e1e2e fg:#cdd6f4",
    "dialog frame.label":"fg:#89b4fa bold",
    "button":            "bg:#313244 fg:#cdd6f4",
    "button.focused":    "bg:#89b4fa fg:#1e1e2e bold",
    "radio-list":        "bg:#1e1e2e fg:#cdd6f4",
    "radio-selected":    "fg:#a6e3a1 bold",
})

def _menu_select(title, text, values, cancel_label="← Volver", ok_label="▶ Aceptar"):
    try:
        return radiolist_dialog(title=title, text=text,
                                values=values,
                                ok_text=ok_label,
                                cancel_text=cancel_label,
                                style=_MENU_STYLE).run()
    except Exception:
        return None

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
        return yes_no_dialog(title=title, text=text, style=_MENU_STYLE).run()
    except Exception:
        return False

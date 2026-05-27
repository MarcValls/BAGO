"""bago.ui_dialogs - menus interactivos de BAGO."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, HSplit, Window
from prompt_toolkit.shortcuts import button_dialog, checkboxlist_dialog, input_dialog, yes_no_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, Label

from rich import box

from .ui_base import console, _strip_rich, _warn_prompt_toolkit_fallback, _stdin_prompt

_PROMPT_TOOLKIT_AVAILABLE = os.environ.get("BAGO_NO_PROMPT_TOOLKIT", "0") != "1"
try:
    if not _PROMPT_TOOLKIT_AVAILABLE:
        raise ModuleNotFoundError("prompt_toolkit disabled by BAGO_NO_PROMPT_TOOLKIT=1")
except ModuleNotFoundError:
    _PROMPT_TOOLKIT_AVAILABLE = False
    Application = KeyBindings = FormattedTextControl = Layout = HSplit = Window = None
    button_dialog = checkboxlist_dialog = input_dialog = yes_no_dialog = None
    Frame = Label = None

    class Style:
        @staticmethod
        def from_dict(data):
            return data

_MENU_STYLE = Style.from_dict({
    "dialog":             "bg:#1e1e2e",
    "dialog.body":        "bg:#1e1e2e fg:#cdd6f4",
    "dialog frame.label": "fg:#89b4fa bold",
    "frame.border":       "fg:#45475a",
    "button":             "bg:#313244 fg:#cdd6f4",
    "button.focused":     "bg:#89b4fa fg:#1e1e2e bold",
    "label":              "bg:#1e1e2e fg:#6c7086",
    "pick.cursor":        "fg:#89b4fa bold",          # '>>' azul brillante
    "pick.focused":       "bg:#313244 fg:#cdf4a1 bold",  # fila activa: fondo + texto claro
    "pick.item":          "fg:#585b70",               # filas inactivas: gris tenue
    "pick.recommended":   "fg:#f9e2af bold",         # badge recomendado
    "pick.sep":           "bold",                      # separador — visible en cualquier terminal
    "toggle.on":          "bg:ansibrightgreen fg:ansiblack bold",
    "toggle.off":         "bg:#444444 fg:#888888",
    "toggle.cursor":      "fg:#89b4fa bold",
})

def _menu_pick(title: str, text: str, values: list):
    """
from pathlib import Path
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

    if use_tabs:
        return _menu_pick_tabs(title, text, tab_labels, tabs)

    nav_idx = [i for i, v in enumerate(values) if v[0] is not None]
    if not nav_idx:
        return None

    focus = [0]   # posición dentro de nav_idx
    result = [None]

    def render():
        out = []
        for i, (key, label) in enumerate(values):
            clean = _strip_rich(label)
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


def _menu_pick_provider_model(title: str, text: str, providers: dict, provider_order: list | None = None,
                              current_provider: str | None = None, current_model: str | None = None):
    """Selector 2D: izquierda/derecha cambia provider, arriba/abajo cambia modelo."""
    provider_order = list(provider_order or [])
    available_providers = []
    seen = set()
    for pname in provider_order:
        models = list(providers.get(pname, []) or [])
        if models and pname not in seen:
            available_providers.append(pname)
            seen.add(pname)
    for pname in sorted(providers):
        models = list(providers.get(pname, []) or [])
        if models and pname not in seen:
            available_providers.append(pname)
            seen.add(pname)

    if not available_providers:
        return None

    provider_models = {}
    for pname in available_providers:
        entries = list(providers.get(pname, []) or [])
        provider_models[pname] = sorted(
            entries,
            key=lambda item: (
                0 if item.get("recommended") else 1,
                item.get("name", ""),
            ),
        )

    def _default_model_index(model_list: list[dict], preferred_name: str | None = None) -> int:
        names = [item.get("name", "") for item in model_list]
        if preferred_name and preferred_name in names:
            return names.index(preferred_name)
        for idx, item in enumerate(model_list):
            if item.get("recommended"):
                return idx
        return 0

    pidx = available_providers.index(current_provider) if current_provider in available_providers else 0
    current_provider = available_providers[pidx]
    models = provider_models[current_provider]
    midx = _default_model_index(models, current_model)
    result = [None]

    def _sync_model_index():
        nonlocal models, midx, current_provider
        models = provider_models[current_provider]
        if not models:
            midx = 0
            return
        if midx >= len(models):
            midx = _default_model_index(models, current_model)

    def render_provider_bar():
        out = []
        out.append(("class:label", "  Proveedor: "))
        for idx, pname in enumerate(available_providers):
            if idx == pidx:
                out.append(("class:pick.focused", f" [ {pname} ] "))
            else:
                out.append(("class:pick.item", f"  {pname}  "))
            if idx < len(available_providers) - 1:
                out.append(("class:pick.sep", "│"))
        out.append(("", "\n"))
        return out

    def render_model_list():
        out = []
        out.append(("class:label", f"  Modelos de {current_provider}:\n"))
        if not models:
            out.append(("class:pick.item", "    (sin modelos)\n"))
            return out
        for idx, model in enumerate(models):
            name = model.get("name", "?")
            is_current = idx == midx
            recommended = bool(model.get("recommended"))
            prefix = "●" if is_current else " "
            if is_current:
                out.append(("class:pick.cursor", " >> "))
                out.append(("class:pick.focused", f" {prefix} {name} "))
                if recommended:
                    out.append(("class:pick.recommended", "[recomendado]"))
                out.append(("class:pick.focused", " [actual]\n"))
            else:
                out.append(("", "    "))
                out.append(("class:pick.item", f" {prefix} {name} "))
                if recommended:
                    out.append(("class:pick.recommended", "[recomendado]"))
                out.append(("class:pick.item", "\n"))
        return out

    def render():
        return [
            ("class:label", f" {_strip_rich(text)}\n"),
            ("", "\n"),
        ] + render_provider_bar() + render_model_list()

    if not _PROMPT_TOOLKIT_AVAILABLE:
        _warn_prompt_toolkit_fallback()
        console.print(f"\n[bold]{title}[/bold]\n{_strip_rich(text)}")
        console.print("Proveedores disponibles:")
        for idx, pname in enumerate(available_providers, start=1):
            console.print(f"  {idx}. {pname}")
        raw = _stdin_prompt("Proveedor número (Enter cancela): ").strip()
        if not raw:
            return None
        try:
            psel = int(raw)
        except ValueError:
            return None
        if psel < 1 or psel > len(available_providers):
            return None
        current_provider = available_providers[psel - 1]
        models = provider_models[current_provider]
        console.print(f"Modelos de {current_provider}:")
        for idx, model in enumerate(models, start=1):
            name = model.get("name", "?")
            tag = " [recomendado]" if model.get("recommended") else ""
            console.print(f"  {idx}. {name}{tag}")
        raw = _stdin_prompt("Modelo número (Enter cancela): ").strip()
        if not raw:
            return None
        try:
            msel = int(raw)
        except ValueError:
            return None
        if msel < 1 or msel > len(models):
            return None
        return current_provider, models[msel - 1].get("name")

    content = FormattedTextControl(render, focusable=True)
    win = Window(content=content, dont_extend_height=True)

    kb = KeyBindings()

    @kb.add("left", eager=True)
    @kb.add("h", eager=True)
    def _left(event):
        nonlocal pidx, current_provider, midx
        previous_model = models[midx].get("name") if models else None
        pidx = (pidx - 1) % len(available_providers)
        current_provider = available_providers[pidx]
        _sync_model_index()
        model_names = [item.get("name", "") for item in models]
        if previous_model in model_names:
            midx = model_names.index(previous_model)
        else:
            midx = _default_model_index(models, current_model)
        event.app.invalidate()

    @kb.add("right", eager=True)
    @kb.add("l", eager=True)
    def _right(event):
        nonlocal pidx, current_provider, midx
        previous_model = models[midx].get("name") if models else None
        pidx = (pidx + 1) % len(available_providers)
        current_provider = available_providers[pidx]
        _sync_model_index()
        model_names = [item.get("name", "") for item in models]
        if previous_model in model_names:
            midx = model_names.index(previous_model)
        else:
            midx = _default_model_index(models, current_model)
        event.app.invalidate()

    @kb.add("up", eager=True)
    @kb.add("k", eager=True)
    def _up(event):
        nonlocal midx
        if models:
            midx = max(0, midx - 1)
        event.app.invalidate()

    @kb.add("down", eager=True)
    @kb.add("j", eager=True)
    def _down(event):
        nonlocal midx
        if models:
            midx = min(len(models) - 1, midx + 1)
        event.app.invalidate()

    @kb.add("enter", eager=True)
    def _accept(event):
        if not models:
            event.app.exit()
            return
        result[0] = (current_provider, models[midx].get("name"))
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
                Label(" ←/→  proveedor    ↑/↓  modelo    Enter  seleccionar    Esc  volver",
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

    nav_idx = [i for i, it in enumerate(items) if it.get("type") != "sep"]
    focus = [0]  # posicion en nav_idx

    result = {"action": None, "toggles": {}}

    def current_item():
        return items[nav_idx[focus[0]]]

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


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

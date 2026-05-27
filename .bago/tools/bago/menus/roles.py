import sys
from pathlib import Path

from ..storage import ORCH_FILE, _load_json
from ..ui import _menu_action, _menu_select

_MODE_ALIASES = {"economico": "eco", "estandar": "standard"}


def _display_mode_name(name):
    return _MODE_ALIASES.get(name, name)


def _cmd_roles(arg):
    data = _load_json(ORCH_FILE)
    modes = data.get("modes", {})
    tasks = data.get("task_preference", {})

    root_choices = [
        ("modes", "Modos del orquestador  (offline / eco / standard / full)"),
        ("tasks", "Preferencias por tipo de tarea"),
    ]
    section = _menu_select("BAGO / Roles", "Que seccion quieres ver?", root_choices)
    if not section:
        return

    if section == "modes":
        while True:
            choices = [
                (name, f"{_display_mode_name(name):<12}  providers: {', '.join(m.get('allowed_providers', []))}")
                for name, m in modes.items()
            ]
            sel = _menu_select("Modos del orquestador", "Selecciona un modo:", choices)
            if sel is None:
                break
            m = modes[sel]
            info = (f"Descripcion:    {m.get('description', '')}\n"
                    f"Providers:      {', '.join(m.get('allowed_providers', []))}\n"
                    f"Modelo default: {m.get('default_model', '?')}\n"
                    f"Fallback chain: {' -> '.join(m.get('fallback_chain', []))}")
            _menu_action(f"Modo: {_display_mode_name(sel)}", info, [("Cerrar", "ok")])

    elif section == "tasks":
        while True:
            choices = [
                (name, f"{name:<20}  {', '.join(tk.get('models', []))}")
                for name, tk in tasks.items()
            ]
            sel = _menu_select("Preferencias por tarea", "Selecciona una tarea:", choices)
            if sel is None:
                break
            tk = tasks[sel]
            info = (f"Modelos:  {', '.join(tk.get('models', []))}\n"
                    f"Razon:    {tk.get('reason', '')}")
            _menu_action(f"Tarea: {sel}", info, [("Cerrar", "ok")])


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

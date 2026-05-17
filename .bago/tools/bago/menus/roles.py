
from ..storage import ORCH_FILE, _load_json
from ..ui import _menu_action, _menu_select

def _cmd_roles(arg):
    data  = _load_json(ORCH_FILE)
    modes = data.get("modes", {})
    tasks = data.get("task_preference", {})

    root_choices = [
        ("modes", "Modos del orquestador  (offline / economico / estandar / full)"),
        ("tasks", "Preferencias por tipo de tarea"),
    ]
    section = _menu_select("BAGO / Roles", "Que seccion quieres ver?", root_choices)
    if not section: return

    if section == "modes":
        while True:
            choices = [(name,
                        f"{name:<12}  providers: {', '.join(m.get('allowed_providers',[]))}")
                       for name, m in modes.items()]
            sel = _menu_select("Modos del orquestador", "Selecciona un modo:", choices)
            if sel is None: break
            m = modes[sel]
            info = (f"Descripcion:    {m.get('description','')}\n"
                    f"Providers:      {', '.join(m.get('allowed_providers',[]))}\n"
                    f"Modelo default: {m.get('default_model','?')}\n"
                    f"Fallback chain: {' -> '.join(m.get('fallback_chain',[]))}")
            _menu_action(f"Modo: {sel}", info, [("Cerrar", "ok")])

    elif section == "tasks":
        while True:
            choices = [(name,
                        f"{name:<20}  {', '.join(tk.get('models',[]))}")
                       for name, tk in tasks.items()]
            sel = _menu_select("Preferencias por tarea", "Selecciona una tarea:", choices)
            if sel is None: break
            tk = tasks[sel]
            info = (f"Modelos:  {', '.join(tk.get('models',[]))}\n"
                    f"Razon:    {tk.get('reason','')}")
            _menu_action(f"Tarea: {sel}", info, [("Cerrar", "ok")])

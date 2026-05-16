
from ..storage import AGENTS_FILE, _load_json, _save_json
from ..ui import _menu_action, _menu_confirm, _menu_input, _menu_select, pe, pi

def _cmd_agents(arg):
    data = _load_json(AGENTS_FILE)
    agents = {k: v for k, v in data.items() if not k.startswith("_")}
    parts = arg.split(None, 1)
    direct = parts[0] if parts and parts[0] in agents else None

    while True:
        if not direct:
            choices = [(name,
                        f"{'[ON]' if ag.get('active') else '[--]'} {name}  |  "
                        f"{ag.get('model','?')}  |  {', '.join(ag.get('skills',[]))}")
                       for name, ag in agents.items()]
            choices += [("__add__", "+ Crear nuevo agente"), ("__exit__", "Salir")]
            sel = _menu_select("BAGO / Agentes", "Selecciona un agente:", choices)
            if sel is None or sel == "__exit__": break
            if sel == "__add__":
                _agents_create(data, agents)
                data = _load_json(AGENTS_FILE)
                agents = {k: v for k, v in data.items() if not k.startswith("_")}
                continue
            direct = sel

        ag = agents.get(direct, {})
        activo = ag.get("active", True)
        info = (f"Modelo:    {ag.get('model','?')}\n"
                f"Skills:    {', '.join(ag.get('skills',[]))}\n"
                f"Fase:      {ag.get('phase','?')}\n"
                f"Categoria: {ag.get('category','?')}\n"
                f"Desc:      {ag.get('description','')}\n"
                f"Activo:    {'SI' if activo else 'NO'}")
        action = _menu_action(f"Agente: {direct}", info,
                              [("Editar", "edit"), ("Activar/Desactivar", "toggle"),
                               ("Eliminar", "delete"), ("Volver", "back")])
        if action == "back" or action is None:
            direct = None; continue
        if action == "toggle":
            agents[direct]["active"] = not activo
            data.update(agents)
            _save_json(AGENTS_FILE, data)
            pi(f"Agente '{direct}': {'ACTIVO' if agents[direct]['active'] else 'INACTIVO'}")
            direct = None; continue
        if action == "delete":
            if _menu_confirm("Eliminar agente", f"Eliminar '{direct}'?"):
                del data[direct]
                _save_json(AGENTS_FILE, data)
                pi(f"Agente '{direct}' eliminado.")
                agents = {k: v for k, v in data.items() if not k.startswith("_")}
            direct = None; continue
        if action == "edit":
            _agents_edit(data, agents, direct)
            data = _load_json(AGENTS_FILE)
            agents = {k: v for k, v in data.items() if not k.startswith("_")}
            direct = None; continue
        direct = None

def _agents_create(data, agents):
    name = _menu_input("Nuevo agente", "Nombre del agente:")
    if not name or name in agents: pe("Nombre vacio o ya existe."); return
    model = _menu_input("Modelo", "Modelo LLM:", default="qwen2.5:0.5b") or "qwen2.5:0.5b"
    skills_raw = _menu_input("Skills", "Skills (separadas por coma):") or ""
    desc = _menu_input("Descripcion", "Descripcion breve:") or f"Agente {name}"
    agents[name] = {"phase": 0, "skills": [s.strip() for s in skills_raw.split(",") if s.strip()],
                    "category": "general", "description": desc, "active": True, "model": model}
    data.update(agents)
    if _save_json(AGENTS_FILE, data): pi(f"Agente '{name}' creado.")

def _agents_edit(data, agents, name):
    ag = agents[name]
    fields = [
        ("model",       f"model       = {ag.get('model','?')}"),
        ("skills",      f"skills      = {', '.join(ag.get('skills',[]))}"),
        ("description", f"description = {ag.get('description','')}"),
        ("category",    f"category    = {ag.get('category','?')}"),
        ("phase",       f"phase       = {ag.get('phase','?')}"),
    ]
    field = _menu_select(f"Editar: {name}", "Campo a editar:", fields)
    if not field: return
    new_val = _menu_input(f"Editar {field}", f"Nuevo valor para '{field}':",
                          default=str(ag.get(field, "")))
    if new_val is None: return
    if field == "skills":   new_val = [s.strip() for s in new_val.split(",") if s.strip()]
    elif field == "phase":
        try: new_val = int(new_val)
        except: pass
    agents[name][field] = new_val
    data.update(agents)
    if _save_json(AGENTS_FILE, data): pi(f"Agente '{name}': {field} actualizado.")

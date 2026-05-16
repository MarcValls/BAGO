
import json

from ..constants import USER_BAGO
from ..storage import _STATE_DIR
from ..ui import _menu_confirm, _menu_input, _menu_select, pi
from .workspaces import _load_workspaces, _proj_in_ws, _ws_active

_PROJECTS_FILE = USER_BAGO / "projects.json"

def _load_projects():
    if _PROJECTS_FILE.exists():
        try: return json.loads(_PROJECTS_FILE.read_text(encoding="utf-8-sig"))
        except Exception: pass
    # Seed desde recent_projects.json si existe
    rp = _STATE_DIR / "recent_projects.json"
    if rp.exists():
        try:
            d = json.loads(rp.read_text(encoding="utf-8-sig"))
            projects = []
            for i, p in enumerate(d.get("projects", [])):
                projects.append({
                    "id": f"proj-{i+1:03d}",
                    "workspace_id": None,
                    "name": p.get("repo_name", f"proyecto_{i}"),
                    "path": p.get("repo_root", ""),
                    "description": p.get("last_idea", ""),
                    "status": "active",
                    "tags": [],
                    "mode": p.get("mode", ""),
                    "created_at": p.get("last_seen", "")[:10],
                    "last_active": p.get("last_seen", "")[:10],
                })
            return {"projects": projects, "active_project_id": None}
        except Exception: pass
    return {"projects": [], "active_project_id": None}

def _save_projects(data):
    _PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROJECTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _cmd_projects(session):
    """Gestion de proyectos. Usa el workspace activo como contexto."""
    wdata = _load_workspaces()
    ws = _ws_active(wdata)
    ws_id   = ws["id"]   if ws else None
    ws_name = ws["name"] if ws else "Sin workspace"
    _cmd_projects_in_ws(ws_id, ws_name)

def _cmd_projects_in_ws(ws_id, ws_name):
    while True:
        pdata = _load_projects()
        if ws_id:
            my_projs = _proj_in_ws(pdata, ws_id)
            others   = [p for p in pdata["projects"] if p.get("workspace_id") != ws_id]
            header   = f"Workspace: [cyan]{ws_name}[/cyan]  |  {len(my_projs)} proyectos"
        else:
            my_projs = pdata["projects"]
            others   = []
            header   = "Todos los proyectos (sin workspace activo)"

        active_id = pdata.get("active_project_id")
        choices = []
        for p in my_projs:
            marker = " [bold green]<< ACTIVO[/bold green]" if p["id"] == active_id else ""
            status = p.get("status", "?")
            desc   = p.get("description", "")[:40]
            choices.append((p["id"], f"{p['name']:<22}  [{status}]  {desc}{marker}"))
        if others and ws_id:
            choices.append(("__others__", f"[dim]Ver proyectos de otros workspaces ({len(others)})[/dim]"))
        choices.append(("__new__",  "[green]+ Nuevo proyecto[/green]"))
        choices.append(("__exit__", "Volver"))

        sel = _menu_select(f"BAGO / Proyectos", header, choices)
        if sel is None or sel == "__exit__": break

        if sel == "__new__":
            _proj_create(ws_id)
        elif sel == "__others__":
            _proj_list_all(pdata)
        else:
            _proj_detail(sel)

def _proj_create(ws_id):
    pdata = _load_projects()
    name  = _menu_input("Nuevo Proyecto", "Nombre del proyecto:")
    if not name: return
    desc  = _menu_input("Descripcion", "Descripcion breve:", default="")
    path  = _menu_input("Ruta", "Ruta del proyecto (puede estar vacia):", default="")
    status= _menu_select("Estado", "Estado inicial:",
                         [("active","active"),("paused","paused"),("planned","planned")])
    import datetime as _dt
    new_id = f"proj-{len(pdata['projects'])+1:03d}"
    pdata["projects"].append({
        "id": new_id, "workspace_id": ws_id, "name": name,
        "description": desc or "", "path": path or "",
        "status": status or "active", "tags": [],
        "created_at": _dt.date.today().isoformat(),
        "last_active": _dt.date.today().isoformat(),
    })
    if not pdata.get("active_project_id"):
        pdata["active_project_id"] = new_id
    _save_projects(pdata)
    pi(f"Proyecto '{name}' creado [{new_id}].")

def _proj_list_all(pdata):
    choices = []
    for p in pdata["projects"]:
        ws_id = p.get("workspace_id") or "—"
        choices.append((p["id"], f"{p['name']:<22}  [ws:{ws_id}]  {p.get('status','?')}"))
    choices.append(("__exit__", "Cerrar"))
    sel = _menu_select("Todos los proyectos", f"{len(pdata['projects'])} proyectos en total:", choices)
    if sel and sel != "__exit__":
        _proj_detail(sel)

def _proj_detail(proj_id):
    pdata = _load_projects()
    p = next((x for x in pdata["projects"] if x["id"] == proj_id), None)
    if not p: return
    is_active = pdata.get("active_project_id") == proj_id

    while True:
        info = (f"ID: {p['id']}  |  Workspace: {p.get('workspace_id') or '—'}\n"
                f"Descripcion: {p.get('description','')}\n"
                f"Ruta: {p.get('path','') or '—'}\n"
                f"Status: {p.get('status','?')}  |  Creado: {p.get('created_at','?')}")
        actions = [
            ("set_active", ">> Ya activo" if is_active else "Establecer como proyecto activo"),
            ("edit_name",  "Editar nombre"),
            ("edit_desc",  "Editar descripcion"),
            ("edit_path",  "Editar ruta"),
            ("edit_status","Cambiar estado"),
            ("reasign_ws", "Reasignar a workspace"),
            ("delete",     "[red]Eliminar proyecto[/red]"),
            ("__back__",   "Volver"),
        ]
        sel = _menu_action(f"Proyecto: {p['name']}", info, actions)
        if sel is None or sel == "__back__": break

        if sel == "set_active":
            pdata["active_project_id"] = proj_id
            _save_projects(pdata)
            is_active = True
            pi(f"Proyecto activo: {p['name']}")

        elif sel == "edit_name":
            v = _menu_input("Nombre", "Nuevo nombre:", default=p["name"])
            if v: p["name"] = v; _save_projects(pdata)

        elif sel == "edit_desc":
            v = _menu_input("Descripcion", "Nueva descripcion:", default=p.get("description",""))
            if v is not None: p["description"] = v; _save_projects(pdata)

        elif sel == "edit_path":
            v = _menu_input("Ruta", "Ruta del proyecto:", default=p.get("path",""))
            if v is not None: p["path"] = v; _save_projects(pdata)

        elif sel == "edit_status":
            v = _menu_select("Estado", "Nuevo estado:",
                             [("active","active"),("paused","paused"),
                              ("planned","planned"),("completed","completed"),("archived","archived")])
            if v:
                import datetime as _dt
                p["status"] = v
                p["last_active"] = _dt.date.today().isoformat()
                _save_projects(pdata)

        elif sel == "reasign_ws":
            wdata = _load_workspaces()
            ws_choices = [(w["id"], w["name"]) for w in wdata.get("workspaces", [])]
            ws_choices.append(("__none__", "Sin workspace"))
            ws_choices.append(("__cancel__", "Cancelar"))
            new_ws = _menu_select("Reasignar", "Selecciona workspace destino:", ws_choices)
            if new_ws and new_ws not in ("__cancel__",):
                p["workspace_id"] = None if new_ws == "__none__" else new_ws
                _save_projects(pdata)
                pi(f"Proyecto reasignado a workspace: {new_ws}")

        elif sel == "delete":
            if _menu_confirm("Eliminar proyecto", f"Eliminar '{p['name']}'? Esta accion no se puede deshacer."):
                pdata["projects"] = [x for x in pdata["projects"] if x["id"] != proj_id]
                if pdata.get("active_project_id") == proj_id:
                    pdata["active_project_id"] = pdata["projects"][0]["id"] if pdata["projects"] else None
                _save_projects(pdata)
                pi(f"Proyecto '{p['name']}' eliminado.")
                break

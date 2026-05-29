from pathlib import Path

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json

from ..constants import USER_BAGO
from ..ui import _menu_action, _menu_confirm, _menu_input, _menu_select, pe, pi

_WORKSPACES_FILE = USER_BAGO / "workspaces.json"

def _load_workspaces():
    if _WORKSPACES_FILE.exists():
        try: return json.loads(_WORKSPACES_FILE.read_text(encoding="utf-8-sig"))
        except Exception: pass
    return {"workspaces": [], "active_workspace_id": None}

def _save_workspaces(data):
    _WORKSPACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WORKSPACES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _ws_active(wdata):
    aid = wdata.get("active_workspace_id")
    for w in wdata.get("workspaces", []):
        if w["id"] == aid: return w
    return None

def _proj_in_ws(pdata, ws_id):
    return [p for p in pdata.get("projects", []) if p.get("workspace_id") == ws_id]


def _sync_active_workspace_cwd(wdata):
    from ..cwd import clear_user_cwd, set_user_cwd

    ws = _ws_active(wdata)
    raw = str(ws.get("path", "")).strip() if ws else ""
    if not raw:
        clear_user_cwd()
        return
    try:
        set_user_cwd(raw)
    except Exception:
        clear_user_cwd()

# ── /workspaces ───────────────────────────────────────────────────────────────
def _cmd_workspaces(session):
    """Gestion de workspaces. Un workspace agrupa muchos proyectos."""
    from .projects import _load_projects

    while True:
        wdata = _load_workspaces()
        ws_list = wdata.get("workspaces", [])
        active_id = wdata.get("active_workspace_id")

        choices = []
        for w in ws_list:
            marker = " [bold green]<< ACTIVO[/bold green]" if w["id"] == active_id else ""
            desc = w.get("description", "")[:45]
            n_projs = len([p for p in _load_projects().get("projects", []) if p.get("workspace_id") == w["id"]])
            choices.append((w["id"], f"{w['name']:<20}  {desc}  [{n_projs} proyectos]{marker}"))
        choices.append(("__new__",  "[green]+ Nuevo workspace[/green]"))

        title_line = f"Workspace activo: [cyan]{_ws_active(wdata)['name'] if _ws_active(wdata) else 'ninguno'}[/cyan]"
        sel = _menu_select("BAGO / Workspaces", title_line, choices)
        if sel is None: break

        if sel == "__new__":
            _ws_create(wdata)
        else:
            _ws_detail(wdata, sel)

def _ws_create(wdata):
    name = _menu_input("Nuevo Workspace", "Nombre del workspace:")
    if not name: return
    desc = _menu_input("Descripcion", "Descripcion breve:", default="")
    path = _menu_input("Ruta", "Ruta raiz del workspace (puede estar vacia):", default="")
    new_id = f"ws-{len(wdata['workspaces'])+1:03d}"
    import datetime as _dt
    wdata["workspaces"].append({
        "id": new_id, "name": name, "description": desc or "",
        "path": path or "", "tags": [], "created_at": _dt.date.today().isoformat()
    })
    if not wdata.get("active_workspace_id"):
        wdata["active_workspace_id"] = new_id
    _save_workspaces(wdata)
    _sync_active_workspace_cwd(wdata)
    pi(f"Workspace '{name}' creado [{new_id}].")

def _ws_detail(wdata, ws_id):
    from .projects import _cmd_projects_in_ws, _load_projects

    w = next((x for x in wdata["workspaces"] if x["id"] == ws_id), None)
    if not w: return
    pdata  = _load_projects()
    projs  = _proj_in_ws(pdata, ws_id)
    is_active = wdata.get("active_workspace_id") == ws_id

    while True:
        proj_names = ", ".join(p["name"] for p in projs[:5]) or "sin proyectos"
        info = (f"ID: {w['id']}  |  Ruta: {w.get('path','') or '—'}\n"
                f"Descripcion: {w.get('description','')}\n"
                f"Proyectos ({len(projs)}): {proj_names}")
        actions = [
            ("set_active", f"{'>> Ya activo' if is_active else 'Establecer como activo'}"),
            ("edit_name",  "Editar nombre"),
            ("edit_desc",  "Editar descripcion"),
            ("edit_path",  "Editar ruta"),
            ("projects",   f"Ver proyectos ({len(projs)})"),
            ("delete",     "[red]Eliminar workspace[/red]"),
            ("__back__",   "Volver"),
        ]
        sel = _menu_action(f"Workspace: {w['name']}", info, actions)
        if sel is None or sel == "__back__": break

        if sel == "set_active":
            wdata["active_workspace_id"] = ws_id
            _save_workspaces(wdata)
            _sync_active_workspace_cwd(wdata)
            is_active = True
            pi(f"Workspace activo: {w['name']}")

        elif sel == "edit_name":
            v = _menu_input("Nombre", "Nuevo nombre:", default=w["name"])
            if v: w["name"] = v; _save_workspaces(wdata)

        elif sel == "edit_desc":
            v = _menu_input("Descripcion", "Nueva descripcion:", default=w.get("description",""))
            if v is not None: w["description"] = v; _save_workspaces(wdata)

        elif sel == "edit_path":
            v = _menu_input("Ruta", "Ruta raiz:", default=w.get("path",""))
            if v is not None:
                w["path"] = v
                _save_workspaces(wdata)
                if is_active:
                    _sync_active_workspace_cwd(wdata)

        elif sel == "projects":
            _cmd_projects_in_ws(ws_id, w["name"])
            pdata = _load_projects()
            projs = _proj_in_ws(pdata, ws_id)

        elif sel == "delete":
            if projs:
                pe(f"El workspace tiene {len(projs)} proyectos. Reasignalos o eliminalos primero.")
            elif _menu_confirm("Eliminar workspace", f"Eliminar '{w['name']}'? Esta accion no se puede deshacer."):
                wdata["workspaces"] = [x for x in wdata["workspaces"] if x["id"] != ws_id]
                if wdata.get("active_workspace_id") == ws_id:
                    wdata["active_workspace_id"] = wdata["workspaces"][0]["id"] if wdata["workspaces"] else None
                _save_workspaces(wdata)
                _sync_active_workspace_cwd(wdata)
                pi(f"Workspace '{w['name']}' eliminado.")
                break


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

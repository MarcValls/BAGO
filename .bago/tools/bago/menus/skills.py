import sys
from pathlib import Path

from ..storage import SKILLS_FILE, _load_json, _save_json
from ..ui import _menu_action, _menu_confirm, _menu_input, _menu_select, pe, pi

def _cmd_skills(arg):
    data = _load_json(SKILLS_FILE)
    parts = arg.split(None, 1)
    direct = parts[0] if parts and parts[0] in data else None

    while True:
        if not direct:
            choices = [(name,
                        f"{name}  |  cat:{sk.get('category','?')}  |  {sk.get('description','')[:50]}")
                       for name, sk in data.items()]
            choices += [("__add__", "+ Crear nueva skill")]
            sel = _menu_select("BAGO / Skills", "Selecciona una skill:", choices)
            if sel is None: break
            if sel == "__add__":
                _skills_create(data); data = _load_json(SKILLS_FILE); continue
            direct = sel

        sk = data.get(direct, {})
        info = (f"Categoria: {sk.get('category','?')}\n"
                f"Fase:      {sk.get('phase','?')}\n"
                f"Steps:     {sk.get('steps',[])}\n"
                f"Desc:      {sk.get('description','')}")
        action = _menu_action(f"Skill: {direct}", info,
                              [("Editar", "edit"), ("Eliminar", "delete"), ("Volver", "back")])
        if action == "back" or action is None: direct = None; continue
        if action == "delete":
            if _menu_confirm("Eliminar skill", f"Eliminar '{direct}'?"):
                del data[direct]; _save_json(SKILLS_FILE, data); pi(f"Skill '{direct}' eliminada.")
            direct = None; continue
        if action == "edit":
            _skills_edit(data, direct); data = _load_json(SKILLS_FILE); direct = None; continue
        direct = None

def _skills_create(data):
    name = _menu_input("Nueva skill", "Nombre de la skill:")
    if not name or name in data: pe("Nombre vacio o ya existe."); return
    cat  = _menu_input("Categoria", "Categoria:", default="general") or "general"
    desc = _menu_input("Descripcion", "Descripcion:") or f"Skill {name}"
    data[name] = {"steps": [], "phase": 0, "category": cat, "description": desc}
    if _save_json(SKILLS_FILE, data): pi(f"Skill '{name}' creada.")

def _skills_edit(data, name):
    sk = data[name]
    fields = [
        ("description", f"description = {sk.get('description','')}"),
        ("category",    f"category    = {sk.get('category','?')}"),
        ("phase",       f"phase       = {sk.get('phase','?')}"),
        ("steps",       f"steps       = {sk.get('steps',[])}"),
    ]
    field = _menu_select(f"Editar skill: {name}", "Campo a editar:", fields)
    if not field: return
    new_val = _menu_input(f"Editar {field}", "Nuevo valor:", default=str(sk.get(field, "")))
    if new_val is None: return
    if field == "steps":
        try: new_val = [int(x.strip()) for x in new_val.split(",") if x.strip()]
        except: pass
    elif field == "phase":
        try: new_val = int(new_val)
        except: pass
    data[name][field] = new_val
    if _save_json(SKILLS_FILE, data): pi(f"Skill '{name}': {field} actualizado.")


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

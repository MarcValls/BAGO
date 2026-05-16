
from ..storage import ORCH_FILE, _load_json
from ..ui import _menu_select, pi

def _cmd_mode(session):
    """Cambio rapido del modo del orquestador."""
    orch = _load_json(ORCH_FILE)
    modes = orch.get("modes", {})

    choices = []
    for name, m in modes.items():
        marker = " [bold green]<<[/bold green]" if name == session.orch_mode else ""
        desc = m.get("description", "")[:60]
        choices.append((name, f"{name:<12}  {desc}{marker}"))
    choices.append(("__exit__", "Volver sin cambiar"))

    sel = _menu_select("BAGO / Modo Orquestador",
                       f"Modo actual: [cyan]{session.orch_mode}[/cyan]\n"
                       "Selecciona el modo de operacion:", choices)
    if sel is None or sel == "__exit__": return

    session.orch_mode = sel
    m = modes.get(sel, {})
    pi(f"Modo: {sel}  |  providers permitidos: {', '.join(m.get('allowed_providers',[]))}")
    pi(f"Modelo default: {m.get('default_model','?')}  |  chain: {' -> '.join(m.get('fallback_chain',[]))}")

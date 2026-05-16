
from ..storage import ROUTING_FILE_P, _load_json, _save_json
from ..ui import _menu_action, _menu_confirm, _menu_input, _menu_select, pe, pi

# ── /routing ──────────────────────────────────────────────────────────────────
def _cmd_routing(arg):
    data = _load_json(ROUTING_FILE_P)

    while True:
        rules = data.get("rules", [])
        fb    = data.get("fallback", {})
        choices = [(r["id"],
                    f"#{i+1:02d}  {r['id']:<22}  {r.get('provider','?')}/{r.get('model','?')}")
                   for i, r in enumerate(rules)]
        choices += [
            ("__add__",      "+ Aniadir regla"),
            ("__fallback__", f"* Fallback: {fb.get('provider','?')} / {fb.get('model','?')}"),
            ("__exit__",     "Salir"),
        ]
        sel = _menu_select("BAGO / Routing Matrix",
                           "Selecciona una regla (flechas + Enter):", choices)
        if sel is None or sel == "__exit__": break

        if sel == "__add__":
            _routing_add(data); continue

        if sel == "__fallback__":
            prov  = _menu_input("Fallback provider", "Provider:", default=fb.get("provider","codex"))
            if prov is None: continue
            model = _menu_input("Fallback model", "Modelo:", default=fb.get("model","gpt-5.4"))
            if model is None: continue
            data["fallback"] = {"provider": prov, "model": model}
            _save_json(ROUTING_FILE_P, data); pi(f"Fallback: {prov} / {model}"); continue

        rule = next((r for r in rules if r["id"] == sel), None)
        if not rule: continue
        idx  = next(i for i, r in enumerate(rules) if r["id"] == sel)
        info = (f"Keywords:  {rule.get('keywords','')}\n"
                f"Provider:  {rule.get('provider','?')}\n"
                f"Modelo:    {rule.get('model','?')}\n"
                f"Razon:     {rule.get('reason','')}")
        action = _menu_action(f"Regla: {sel}", info,
                              [("Editar", "edit"), ("Subir", "up"),
                               ("Bajar", "down"), ("Eliminar", "delete"), ("Volver", "back")])
        if action == "back" or action is None: continue
        if action == "delete":
            if _menu_confirm("Eliminar regla", f"Eliminar '{sel}'?"):
                data["rules"] = [r for r in rules if r["id"] != sel]
                _save_json(ROUTING_FILE_P, data); pi(f"Regla '{sel}' eliminada.")
            continue
        if action == "up" and idx > 0:
            rules[idx], rules[idx-1] = rules[idx-1], rules[idx]
            data["rules"] = rules; _save_json(ROUTING_FILE_P, data)
            pi(f"Regla '{sel}' -> posicion {idx}"); continue
        if action == "down" and idx < len(rules)-1:
            rules[idx], rules[idx+1] = rules[idx+1], rules[idx]
            data["rules"] = rules; _save_json(ROUTING_FILE_P, data)
            pi(f"Regla '{sel}' -> posicion {idx+2}"); continue
        if action == "edit":
            _routing_edit(data, sel); data = _load_json(ROUTING_FILE_P)

def _routing_add(data):
    rid = _menu_input("Nueva regla", "ID de la regla (slug):")
    if not rid: return
    if any(r.get("id") == rid for r in data.get("rules", [])):
        pe(f"Regla '{rid}' ya existe."); return
    keywords = _menu_input("Keywords", "Palabras clave (separadas por espacio):") or ""
    provider = _menu_select("Provider", "Provider:", [
        ("codex","codex - GPT/OpenAI"),
        ("copilot","copilot - GitHub Copilot"),
        ("ollama-local","ollama-local - Local"),
        ("ollama-cloud","ollama-cloud - Nube"),
        ("anthropic","anthropic - Claude"),
    ]) or "codex"
    model  = _menu_input("Modelo", "Nombre del modelo:", default="gpt-5.4") or "gpt-5.4"
    reason = _menu_input("Razon", "Razon/descripcion:") or "Regla personalizada"
    data.setdefault("rules", []).append(
        {"id": rid, "keywords": keywords, "provider": provider, "model": model, "reason": reason})
    if _save_json(ROUTING_FILE_P, data): pi(f"Regla '{rid}' aniadida.")

def _routing_edit(data, rid):
    rule = next((r for r in data.get("rules", []) if r["id"] == rid), None)
    if not rule: return
    fields = [
        ("keywords", f"keywords = {rule.get('keywords','')}"),
        ("provider", f"provider = {rule.get('provider','?')}"),
        ("model",    f"model    = {rule.get('model','?')}"),
        ("reason",   f"reason   = {rule.get('reason','')}"),
    ]
    field = _menu_select(f"Editar regla: {rid}", "Campo a editar:", fields)
    if not field: return
    new_val = _menu_input(f"Editar {field}", "Nuevo valor:", default=str(rule.get(field, "")))
    if new_val is None: return
    rule[field] = new_val
    if _save_json(ROUTING_FILE_P, data): pi(f"Regla '{rid}': {field} actualizado.")

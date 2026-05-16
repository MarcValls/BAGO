
import json

from ..llm import _llm_call
from ..storage import AGENTS_FILE, ORCH_FILE, ROUTING_FILE_P, SKILLS_FILE, _load_json, _save_json
from ..ui import console, _menu_input, _menu_select, pe, pi

# Prompts de sistema para generar cada tipo de pieza
_WIZARD_PROMPTS = {
    "agent": """\
Eres el constructor de agentes BAGO. El usuario describe un agente y tu generas
el JSON de definicion exacto para agents_registry.json.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "agent_<slug>",
  "phase": <0-11>,
  "skills": ["<skill_id>", ...],
  "category": "<tools|tests|docs|ops|music|general>",
  "description": "<descripcion breve>",
  "active": true,
  "model": "<nombre_modelo>"
}
Modelos disponibles: qwen2.5:0.5b, claude-sonnet-4.6, claude-haiku-4.5,
claude-opus-4.7, gpt-5.4, gpt-5.4-mini, gpt-5.5, gpt-5.3-codex.
Elige el modelo mas adecuado para el rol descrito.
Skills existentes: code_review, test_runner, doc_writer.
Si necesitas una skill nueva, incluye su id en la lista igualmente.""",

    "skill": """\
Eres el constructor de skills BAGO. El usuario describe una skill y tu generas
el JSON de definicion exacto para skill_registry.json.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "<skill_slug>",
  "steps": [<lista de indices enteros 0-11>],
  "phase": <0-11>,
  "category": "<tools|tests|docs|ops|music|general>",
  "description": "<descripcion de lo que hace la skill>"
}
Los steps son indices de pasos del ciclo espiral BAGO (0=SENSE, 1=FILTER, 2=PLAN,
3=SELECT, 4=ACT, 5=GENERATE, 6=REVIEW, 7=VALIDATE, 8=OBSERVE, 9=RECORD,
10=LEARN, 11=DECIDE). Incluye los steps relevantes para esta skill.""",

    "role": """\
Eres el constructor de roles/modos del orquestador BAGO. El usuario describe
un modo de operacion y tu generas el JSON para model_orchestrator.json -> modes.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "<nombre_modo>",
  "description": "<descripcion del modo>",
  "allowed_providers": ["<provider1>", ...],
  "default_model": "<modelo>",
  "fallback_chain": ["<modelo1>", "<modelo2>", ...]
}
Providers disponibles: ollama-local, ollama-cloud, copilot, codex, anthropic.
Modelos: qwen2.5:0.5b, claude-sonnet-4.6, claude-opus-4.7, gpt-5.4, gpt-5.5,
         gpt-5.3-codex, gpt-5.4-mini, kimi-k2-1t.""",

    "routing": """\
Eres el constructor de reglas de routing BAGO. El usuario describe una regla
y tu generas el JSON para model_routing.json -> rules[].
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "id": "<slug_unico>",
  "keywords": "<palabras clave separadas por espacio>",
  "provider": "<copilot|codex|ollama-local|ollama-cloud|anthropic>",
  "model": "<nombre_modelo>",
  "reason": "<por que este modelo para estas keywords>"
}
Elige el provider y modelo mas adecuado para las tareas descritas.""",

    "task_pref": """\
Eres el constructor de preferencias de tarea BAGO. El usuario describe un tipo
de tarea y tu generas el JSON para model_orchestrator.json -> task_preference.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "<task_slug>",
  "models": ["<modelo1>", "<modelo2>"],
  "reason": "<por que estos modelos para este tipo de tarea>"
}
Modelos disponibles: qwen2.5:0.5b, claude-sonnet-4.6, claude-opus-4.7, gpt-5.4,
gpt-5.5, gpt-5.3-codex, gpt-5.4-mini, kimi-k2-1t.""",
}

def _wizard_call_lm(session, kind, description):
    """Llama al LM con el prompt de fabrica y devuelve el dict generado o None."""
    sys_prompt = _WIZARD_PROMPTS[kind]
    lm, kw = session.litellm_info
    messages = [
        {"role": "system",  "content": sys_prompt},
        {"role": "user",    "content": description},
    ]
    with console.status(f"  [dim cyan]Generando {kind}...[/dim cyan]", spinner="dots"):
        try:
            raw = _llm_call(lm, kw, messages)
        except Exception as e:
            pe(f"LM error: {e}"); return None

    # Extraer JSON — el LM puede envolver en ``` a veces
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except Exception:
        # Intentar buscar primer { ... }
        try:
            start = text.index("{"); end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            pe(f"LM devolvio JSON invalido:\n{raw[:300]}")
            return None

def _wizard_review_dict(title, d):
    """Muestra los campos generados por LM y permite editar campo a campo."""
    while True:
        # Muestra campos editables (excluye 'name' de la lista — se edita aparte)
        editable = [(k, f"{k} = {v}") for k, v in d.items() if k != "name"]
        editable += [("__confirm__", "✓ Confirmar y guardar"),
                     ("__cancel__", "✗ Cancelar")]

        field = _menu_select(
            title,
            f"Revisa los campos generados por el LM.\nSelecciona uno para editar o confirma:",
            editable)

        if field is None or field == "__cancel__":
            return None
        if field == "__confirm__":
            return d

        current = str(d.get(field, ""))
        new_val = _menu_input(f"Editar: {field}", f"Valor actual:", default=current)
        if new_val is None:
            continue
        # Conversiones de tipo
        if field in ("skills", "models", "fallback_chain", "allowed_providers", "steps"):
            try:
                parsed = json.loads(new_val)
                if isinstance(parsed, list):
                    new_val = parsed
                else:
                    new_val = [x.strip() for x in new_val.split(",") if x.strip()]
            except Exception:
                new_val = [x.strip() for x in new_val.split(",") if x.strip()]
        elif field == "phase":
            try: new_val = int(new_val)
            except: pass
        elif field == "active":
            new_val = new_val.lower() in ("true", "si", "yes", "1")
        d[field] = new_val

def _cmd_wizard(session):
    """Fabrica de piezas BAGO asistida por LM. /new | /wizard | /fabrica"""
    kind_choices = [
        ("agent",    "Agente BAGO  — define rol, modelo, skills, fase"),
        ("skill",    "Skill BAGO   — define capacidad reutilizable con steps espirales"),
        ("role",     "Modo/Rol del orquestador  — offline / economico / custom"),
        ("routing",  "Regla de routing  — keywords → provider/modelo"),
        ("task_pref","Preferencia de tarea  — tipo de tarea → modelos recomendados"),
    ]
    kind = _menu_select("BAGO / Fabrica de Piezas",
                        "Que tipo de pieza quieres construir?", kind_choices)
    if not kind: return

    desc = _menu_input(
        f"Describe tu {kind}",
        f"Describe en lenguaje natural lo que necesitas.\n"
        f"El LM generara la definicion completa:",
        default="")
    if not desc or not desc.strip(): return

    result = _wizard_call_lm(session, kind, desc)
    if not result:
        pe("El LM no pudo generar una definicion valida."); return

    # Pedir nombre si no viene en el resultado
    name_field = {"agent": "name", "skill": "name", "role": "name",
                  "routing": "id", "task_pref": "name"}.get(kind, "name")
    if name_field not in result or not result.get(name_field):
        suggested = desc.lower().replace(" ", "_")[:20]
        name_val = _menu_input("Nombre / ID",
                               f"El LM no propuso un nombre. Introduce el {name_field}:",
                               default=suggested)
        if not name_val: return
        result[name_field] = name_val

    # Revisión interactiva campo a campo
    title = f"Fabrica > {kind}: {result.get(name_field, '?')}"
    confirmed = _wizard_review_dict(title, result)
    if confirmed is None:
        pi("Wizard cancelado."); return

    # Guardar en el archivo correspondiente
    _wizard_save(kind, confirmed)

def _wizard_save(kind, d):
    """Persiste la pieza generada en el JSON de estado correspondiente."""
    if kind == "agent":
        data = _load_json(AGENTS_FILE)
        name = d.pop("name", None) or d.get("name", "agent_nuevo")
        # Asegurarse de que empieza por "agent_"
        if not name.startswith("agent_"):
            name = "agent_" + name
        data[name] = d
        if _save_json(AGENTS_FILE, data):
            pi(f"Agente '{name}' guardado en agents_registry.json")

    elif kind == "skill":
        data = _load_json(SKILLS_FILE)
        name = d.pop("name", None) or "skill_nueva"
        data[name] = d
        if _save_json(SKILLS_FILE, data):
            pi(f"Skill '{name}' guardada en skill_registry.json")

    elif kind == "role":
        data = _load_json(ORCH_FILE)
        name = d.pop("name", None) or "modo_nuevo"
        data.setdefault("modes", {})[name] = d
        if _save_json(ORCH_FILE, data):
            pi(f"Modo '{name}' guardado en model_orchestrator.json")

    elif kind == "routing":
        data = _load_json(ROUTING_FILE_P)
        rid = d.get("id", "regla_nueva")
        # Evitar duplicados
        data["rules"] = [r for r in data.get("rules", []) if r.get("id") != rid]
        data["rules"].append(d)
        if _save_json(ROUTING_FILE_P, data):
            pi(f"Regla '{rid}' guardada en model_routing.json (posicion {len(data['rules'])})")

    elif kind == "task_pref":
        data = _load_json(ORCH_FILE)
        name = d.pop("name", None) or "tarea_nueva"
        data.setdefault("task_preference", {})[name] = d
        if _save_json(ORCH_FILE, data):
            pi(f"Preferencia de tarea '{name}' guardada en model_orchestrator.json")


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
import datetime

from ..constants import SCRIPT_DIR, TOOLBOXES_DIR
from ..llm import _llm_call
from ..storage import AGENTS_FILE, ORCH_FILE, ROUTING_FILE_P, SKILLS_FILE, _load_json, _save_json
from ..ui import console, _menu_input, _menu_select, pe, pi

# ─── LM prompts ────────────────────────────────────────────────────────────────

_WIZARD_PROMPTS = {

    # ── CATEGORÍA: INTELIGENCIA ────────────────────────────────────────────────

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
Fases espirales: 0=SENSE 1=FILTER 2=PLAN 3=SELECT 4=ACT 5=GENERATE
                 6=REVIEW 7=VALIDATE 8=OBSERVE 9=RECORD 10=LEARN 11=DECIDE
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
Los steps son indices del ciclo espiral BAGO:
  0=SENSE 1=FILTER 2=PLAN 3=SELECT 4=ACT 5=GENERATE
  6=REVIEW 7=VALIDATE 8=OBSERVE 9=RECORD 10=LEARN 11=DECIDE
Incluye los steps relevantes para esta skill. Tipicamente 3-6 steps.""",

    # ── CATEGORÍA: SPRINT / NEURAL ─────────────────────────────────────────────

    "neural_node": """\
Eres el constructor de nodos neurales (toolboxes) BAGO.
Un nodo neural define el conjunto de herramientas disponibles para un ROL dentro
de un sprint. El usuario describe el rol y tu generas el JSON completo.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "agent": "<NOMBRE_ROL_EN_MAYUSCULAS>",
  "task": "<sprint|review|audit|onboard|release>",
  "sprint": "<slug-del-sprint>",
  "tools": [
    {"cmd": "<bago_command>", "purpose": "<always_available|sprint_start|sprint_end|on_demand>", "group": "<default|music|code|docs|ops>"},
    ...
  ],
  "composite": "<descripcion del composite si aplica, o vacio>",
  "created_at": "<ISO timestamp>"
}
Comandos BAGO tipicos: session, health, flow, work_matrix, neural, npath, status,
  sprint_kickoff, validate, context, scope, project, env_check, deps, code_review,
  test_runner, doc_writer, sync, ideas, task, audit, dashboard, efficiency, cosecha,
  detector, stale, sincerity.
Purposes:
  always_available = disponible en todo momento durante el sprint
  sprint_start     = solo al inicio del sprint
  sprint_end       = solo al cierre del sprint
  on_demand        = solo cuando el rol lo necesita explicitamente
Roles existentes: MAESTRO_BAGO, ANALISTA_CONTEXTO, ARQUITECTO_SOLUCIONES,
  GENERADOR_CONTENIDO, ORGANIZADOR_ENTREGABLES, CENTINELA_SINCERIDAD,
  ADAPTADOR_PROYECTO, INICIADOR_MAESTRO.
Elige un nombre de rol descriptivo en MAYUSCULAS.""",

    # ── CATEGORÍA: ORQUESTACIÓN ────────────────────────────────────────────────

    "routing": """\
Eres el constructor de reglas de routing BAGO. El usuario describe una regla
y tu generas el JSON para model_routing.json -> rules[].
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "id": "<slug_unico>",
  "keywords": ["<kw1>", "<kw2>", ...],
  "provider": "<copilot|codex|ollama-local|ollama-cloud|anthropic|local>",
  "model": "<nombre_modelo>",
  "reason": "<por que este modelo para estas keywords>"
}
IMPORTANTE: keywords es SIEMPRE un array JSON de strings, no un string.
Cada keyword puede ser una palabra o frase corta.
Providers disponibles: copilot, codex, ollama-local, ollama-cloud, anthropic, local.
Modelos: qwen2.5:0.5b, claude-sonnet-4.6, claude-opus-4.7, gpt-5.4, gpt-5.5,
         gpt-5.3-codex, gpt-5.4-mini, kimi-k2-1t, qwen25-coder.
Elige el provider y modelo mas adecuado para las tareas descritas por las keywords.""",

    "task_pref": """\
Eres el constructor de preferencias de tarea BAGO. El usuario describe un tipo
de tarea y tu generas el JSON para model_orchestrator.json -> task_preference.
Responde SOLO con JSON valido, sin explicacion, sin markdown, sin bloques de codigo.
Esquema requerido:
{
  "name": "<task_slug>",
  "keywords": ["<kw1>", "<kw2>", ...],
  "models": ["<modelo1>", "<modelo2>"],
  "reason": "<por que estos modelos para este tipo de tarea>"
}
IMPORTANTE: keywords y models son SIEMPRE arrays JSON.
Tipos de tarea existentes (no duplicar): code_fast, code_complex, code_frontier,
  review_quick, review_deep, brainstorm, music_edit, music_render, long_context, agent_long.
Modelos disponibles: qwen2.5:0.5b, claude-sonnet-4.6, claude-opus-4.7, gpt-5.4,
  gpt-5.5, gpt-5.3-codex, gpt-5.4-mini, kimi-k2-1t.""",

    "role": """\
Eres el constructor de modos del orquestador BAGO. El usuario describe
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
Modos existentes (no duplicar): offline, eco, standard, full, auto.
Providers disponibles: ollama-local, ollama-cloud, copilot, codex, anthropic, local.
Modelos: qwen2.5:0.5b, claude-sonnet-4.6, claude-opus-4.7, gpt-5.4, gpt-5.5,
         gpt-5.3-codex, gpt-5.4-mini, kimi-k2-1t.
El fallback_chain indica el orden de modelos alternativos si el default falla.""",

    # ── CATEGORÍA: HERRAMIENTAS ────────────────────────────────────────────────

    "tool": """\
Eres el constructor de herramientas Python para el framework BAGO.
El usuario describe una herramienta y tu generas un script Python completo y listo.
Responde SOLO con JSON valido que contiene la metadata y el codigo Python.
Sin explicacion adicional, sin markdown externo.
Esquema requerido:
{
  "name": "<tool_slug_sin_bago_prefix>",
  "category": "<tools|tests|docs|ops|music|general|audit|infra>",
  "description": "<descripcion de una linea de lo que hace>",
  "tags": ["<tag1>", "<tag2>"],
  "code": "<codigo Python completo como string — sin saltos de linea literales, usa \\n>"
}
El codigo Python debe:
1. Empezar con el shebang: #!/usr/bin/env python3
2. Tener un docstring modulo con descripcion y seccion 'Uso:'
3. Importar desde stdlib (pathlib, json, sys, subprocess, etc.)
4. Tener una funcion main() clara
5. Terminar con: if __name__ == '__main__': main()
6. Usar BAGO_ROOT = Path(__file__).resolve().parents[1] si necesita acceso al repo
7. Usar sys.stdout.isatty() para decidir si usar colores
Devuelve el codigo como STRING en el campo 'code', con saltos de linea como \\n.""",
}

# ─── Categorías para el menú ────────────────────────────────────────────────────
_WIZARD_CATEGORIES = [
    ("🧠  INTELIGENCIA", [
        ("agent",      "Agente BAGO        — rol + modelo + skills + fase espiral"),
        ("skill",      "Skill BAGO         — capacidad reutilizable con steps espirales"),
    ]),
    ("⚡  SPRINT / NEURAL", [
        ("neural_node", "Nodo Neural        — toolbox de sprint para un rol"),
    ]),
    ("🔀  ORQUESTACIÓN", [
        ("routing",     "Regla de routing   — keywords → provider/modelo"),
        ("task_pref",   "Preferencia tarea  — tipo de tarea → modelos recomendados"),
        ("role",        "Modo orquestador   — offline / eco / standard / full / auto"),
    ]),
    ("🔧  HERRAMIENTAS", [
        ("tool",        "Tool Python        — script con main() listo para usar"),
    ]),
]

_ALL_KINDS = [(k, label) for _, items in _WIZARD_CATEGORIES for k, label in items]

# ─── LM call ────────────────────────────────────────────────────────────────────

def _wizard_call_lm(session, kind, description):
    """Llama al LM con el prompt de fabrica y devuelve el dict generado o None."""
    sys_prompt = _WIZARD_PROMPTS[kind]
    lm, kw = session.litellm_info
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": description},
    ]
    with console.status(f"  [dim cyan]Generando {kind}...[/dim cyan]", spinner="dots"):
        try:
            raw = _llm_call(lm, kw, messages)
        except Exception as e:
            pe(f"LM error: {e}"); return None

    # Extraer JSON (el LM puede envolver en ``` a veces)
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].strip()
    try:
        return json.loads(text)
    except Exception:
        try:
            start = text.index("{"); end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            pe(f"LM devolvio JSON invalido:\n{raw[:300]}")
            return None

# ─── Revisión interactiva ────────────────────────────────────────────────────────

def _wizard_review_dict(title, d, skip_keys=None):
    """Muestra los campos generados por LM y permite editar campo a campo.
    skip_keys: campos que se muestran pero no se editan inline (ej: 'code').
    """
    skip_keys = set(skip_keys or [])
    while True:
        editable = []
        for k, v in d.items():
            if k == "name":
                continue
            if k in skip_keys:
                preview = str(v)[:60] + ("..." if len(str(v)) > 60 else "")
                editable.append((f"__view_{k}__", f"{k} = {preview}  [ver/editar]"))
            else:
                editable.append((k, f"{k} = {v}"))
        editable += [
            ("__confirm__", "✓ Confirmar y guardar"),
        ]

        field = _menu_select(
            title,
            "Revisa los campos generados por el LM.\nSelecciona uno para editar o confirma:",
            editable)

        if field is None:
            return None
        if field == "__confirm__":
            return d

        # Ver/editar campo largo
        if isinstance(field, str) and field.startswith("__view_"):
            real_field = field[len("__view_"):]
            current = str(d.get(real_field, ""))
            new_val = _menu_input(f"Editar: {real_field}",
                                  f"Contenido actual ({len(current)} chars).\nEdita o deja vacio para mantener:",
                                  default=current[:200])
            if new_val is not None and new_val.strip():
                d[real_field] = new_val
            continue

        current = str(d.get(field, ""))
        new_val = _menu_input(f"Editar: {field}", f"Valor actual:", default=current)
        if new_val is None:
            continue
        # Conversiones de tipo
        if field in ("skills", "models", "fallback_chain", "allowed_providers",
                     "steps", "keywords", "tags", "tools"):
            try:
                parsed = json.loads(new_val)
                new_val = parsed if isinstance(parsed, list) else [x.strip() for x in new_val.split(",") if x.strip()]
            except Exception:
                new_val = [x.strip() for x in new_val.split(",") if x.strip()]
        elif field == "phase":
            try: new_val = int(new_val)
            except: pass
        elif field == "active":
            new_val = new_val.lower() in ("true", "si", "yes", "1")
        d[field] = new_val

# ─── Guardado por tipo ──────────────────────────────────────────────────────────

def _wizard_save(kind, d):
    """Persiste la pieza generada en el archivo de estado correspondiente."""

    if kind == "agent":
        data = _load_json(AGENTS_FILE)
        name = d.pop("name", None) or "agent_nuevo"
        if not name.startswith("agent_"):
            name = "agent_" + name
        data[name] = d
        if _save_json(AGENTS_FILE, data):
            pi(f"Agente '[bold]{name}[/bold]' guardado en agents_registry.json")

    elif kind == "skill":
        data = _load_json(SKILLS_FILE)
        name = d.pop("name", None) or "skill_nueva"
        data[name] = d
        if _save_json(SKILLS_FILE, data):
            pi(f"Skill '[bold]{name}[/bold]' guardada en skill_registry.json")

    elif kind == "neural_node":
        agent_name = d.get("agent", "NODO_NUEVO").upper().replace(" ", "_")
        sprint_slug = d.get("sprint", "sprint-default").lower().replace(" ", "-")
        filename = f"{agent_name.lower()}_{sprint_slug}.json"
        dest = TOOLBOXES_DIR / filename
        TOOLBOXES_DIR.mkdir(parents=True, exist_ok=True)
        if not d.get("created_at"):
            d["created_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        dest.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        pi(f"Nodo neural '[bold]{agent_name}[/bold]' guardado en state/toolboxes/{filename}")

    elif kind == "routing":
        data = _load_json(ROUTING_FILE_P)
        rid = d.get("id", "regla_nueva")
        # Asegurar que keywords es lista
        if isinstance(d.get("keywords"), str):
            d["keywords"] = [k.strip() for k in d["keywords"].split() if k.strip()]
        # Evitar duplicados
        data["rules"] = [r for r in data.get("rules", []) if r.get("id") != rid]
        data["rules"].append(d)
        if _save_json(ROUTING_FILE_P, data):
            pi(f"Regla '[bold]{rid}[/bold]' guardada en model_routing.json (total: {len(data['rules'])})")

    elif kind == "task_pref":
        data = _load_json(ORCH_FILE)
        name = d.pop("name", None) or "tarea_nueva"
        # Asegurar que keywords y models son listas
        if isinstance(d.get("keywords"), str):
            d["keywords"] = [k.strip() for k in d["keywords"].split(",") if k.strip()]
        if isinstance(d.get("models"), str):
            d["models"] = [m.strip() for m in d["models"].split(",") if m.strip()]
        data.setdefault("task_preference", {})[name] = d
        if _save_json(ORCH_FILE, data):
            pi(f"Preferencia '[bold]{name}[/bold]' guardada en model_orchestrator.json")

    elif kind == "role":
        data = _load_json(ORCH_FILE)
        name = d.pop("name", None) or "modo_nuevo"
        data.setdefault("modes", {})[name] = d
        if _save_json(ORCH_FILE, data):
            pi(f"Modo '[bold]{name}[/bold]' guardado en model_orchestrator.json")

    elif kind == "tool":
        name = d.get("name", "tool_nuevo").lower().replace(" ", "_")
        if name.startswith("bago_"):
            filename = f"{name}.py"
        else:
            filename = f"bago_{name}.py"
        dest = SCRIPT_DIR / filename
        code = d.get("code", "")
        # Desescapar \n literales que el LM puede enviar
        if "\\n" in code and "\n" not in code:
            code = code.replace("\\n", "\n")
        if dest.exists():
            pi(f"[yellow]¡Atención![/yellow] {filename} ya existe — guardando como {filename}.new")
            dest = dest.with_suffix(".py.new")
        dest.write_text(code, encoding="utf-8")
        pi(f"Tool '[bold]{filename}[/bold]' creado en tools/")
        pi(f"  Descripción : {d.get('description','')}")
        pi(f"  Categoría   : {d.get('category','')}")
        pi(f"  Tags        : {', '.join(d.get('tags', []))}")

# ─── Comando principal ──────────────────────────────────────────────────────────

def _cmd_wizard(session):
    """Fabrica de piezas BAGO asistida por LM. /new | /wizard | /fabrica"""

    # Menú plano con categoría indicada en la etiqueta
    display_choices = []
    for cat_label, items in _WIZARD_CATEGORIES:
        for kind_key, kind_lbl in items:
            display_choices.append((kind_key, f"[{cat_label}]  {kind_lbl}"))

    kind = _menu_select(
        "BAGO / Fábrica de Artefactos — 7 tipos",
        "Selecciona el tipo de artefacto a construir.\n"
        "El LM genera la definición completa a partir de tu descripción natural:",
        display_choices)
    if not kind:
        return

    # Etiqueta del tipo seleccionado
    kind_label = next((lbl for k, lbl in _ALL_KINDS if k == kind), kind)

    desc = _menu_input(
        f"Describe tu {kind}",
        f"[{kind_label.strip()}]\n"
        f"Describe en lenguaje natural lo que necesitas.\n"
        f"El LM generará la definición completa:",
        default="")
    if not desc or not desc.strip():
        return

    result = _wizard_call_lm(session, kind, desc)
    if not result:
        pe("El LM no pudo generar una definición válida."); return

    # Pedir nombre si no viene en el resultado
    name_field = {
        "agent":      "name",
        "skill":      "name",
        "role":       "name",
        "neural_node":"agent",
        "routing":    "id",
        "task_pref":  "name",
        "tool":       "name",
    }.get(kind, "name")

    if name_field not in result or not result.get(name_field):
        suggested = desc.lower().replace(" ", "_")[:20]
        name_val = _menu_input(
            "Nombre / ID",
            f"El LM no propuso un nombre. Introduce el {name_field}:",
            default=suggested)
        if not name_val:
            return
        result[name_field] = name_val

    # Revisión interactiva campo a campo
    title = f"Fábrica > {kind}: {result.get(name_field, '?')}"
    # Para tools, el campo 'code' es largo — tratarlo como campo especial
    skip_long = {"code"} if kind == "tool" else set()
    confirmed = _wizard_review_dict(title, result, skip_keys=skip_long)
    if confirmed is None:
        pi("Wizard cancelado."); return

    # Guardar
    _wizard_save(kind, confirmed)


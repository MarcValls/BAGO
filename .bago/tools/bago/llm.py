
import concurrent.futures
import re

import litellm

from .constants import BAGO_SYSTEM, COLORS
from .providers import detect_strategy, resolve_litellm
from .ui import console, pe, pi, show_response

litellm.suppress_debug_info = True
litellm.set_verbose = False

# ── Anti-repetición ────────────────────────────────────────────────────────────
def _jaccard(a: str, b: str) -> float:
    """Similitud Jaccard por palabras (0–1). Rapido, sin dependencias."""
    if not a or not b:
        return 0.0
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)

def _dedup_paragraphs(text: str) -> str:
    """Elimina parrafos/bloques duplicados dentro de una misma respuesta."""
    blocks = re.split(r'\n{2,}', text)
    seen, out = [], []
    for blk in blocks:
        key = blk.strip()
        if not key:
            continue
        # Comprobar similitud con los ultimos 8 bloques vistos
        if any(_jaccard(key, s) > 0.82 for s in seen[-8:]):
            continue
        seen.append(key)
        out.append(blk)
    return "\n\n".join(out)

_REPEAT_THRESHOLD = 0.72   # Jaccard entre respuestas sucesivas

def _last_assistant(history: list) -> str:
    """Ultimo mensaje del asistente en el historial."""
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            return msg["content"]
    return ""

# ── Escalado por saturación de contexto ───────────────────────────────────────
_CTX_KEYWORDS = (
    "context", "token", "length exceeded", "too long", "maximum context",
    "context_length", "context window", "max_tokens", "sequence length",
    "input is too long", "prompt is too long", "reduce your prompt",
)

def _is_ctx_overflow(exc) -> bool:
    msg = str(exc).lower()
    return any(kw in msg for kw in _CTX_KEYWORDS)

def _model_size_score(name: str) -> int:
    """Tamano aproximado segun nombre del modelo (mayor = mas contexto/capacidad)."""
    n = name.lower()
    if any(x in n for x in ("0.5b", "1b", "mini")):   return 1
    if any(x in n for x in ("2b", "3b")):               return 2
    if any(x in n for x in ("7b", "8b")):               return 3
    if "coder" in n and not any(x in n for x in ("14b","32b","72b")): return 3
    if any(x in n for x in ("13b", "14b")):             return 4
    if any(x in n for x in ("30b", "32b", "34b")):      return 5
    if any(x in n for x in ("70b", "72b")):             return 6
    return 3  # desconocido → medio

# Orden de providers local→cloud para escalado
_ESCALATE_PROV_ORDER = ("ollama-local", "ollama-cloud", "copilot", "codex", "anthropic")

# Señales de tarea → provider cloud ideal
_TASK_CLOUD_HINTS = {
    "codex":      ("codigo","code","funcion","function","clase","class","script","api",
                   "test","algoritmo","algorithm","refactor","debug","error","bug",
                   "implementa","implement","build","compile"),
    "copilot":    ("explica","analiza","diseña","arquitectura","razona","razonamiento",
                   "estrategia","planifica","documenta","explain","analyze","design",
                   "architecture","reason","strategy","plan","document","compare",
                   "cual es mejor","pros","contras","decision"),
    "anthropic":  ("redacta","escribe","resume","traduce","creative","write","summarize",
                   "translate","draft","articulo","essay","narrativa"),
}

def _deduce_cloud_provider(history: list, user_input: str, active: list) -> str:
    """
    Deduce el mejor provider cloud para la tarea combinando el input actual
    y los ultimos mensajes del usuario en el historial.
    """
    # Texto de contexto: ultimos 4 mensajes de usuario + input actual
    ctx_msgs = [m["content"] for m in history if m.get("role") == "user"][-4:]
    ctx = " ".join(ctx_msgs + [user_input]).lower()

    scores: dict[str, int] = {p: 0 for p in _TASK_CLOUD_HINTS}
    for prov, keywords in _TASK_CLOUD_HINTS.items():
        scores[prov] = sum(1 for kw in keywords if kw in ctx)

    # Elegir el mejor que tenga credenciales activas
    cloud_order = ("codex", "copilot", "anthropic")
    for prov in sorted(cloud_order, key=lambda p: -scores.get(p, 0)):
        if prov in active and prov in _TASK_CLOUD_HINTS:
            return prov
    # Fallback: primer cloud disponible
    for prov in cloud_order:
        if prov in active:
            return prov
    return "copilot"

def _escalate_model(session, user_input: str = "") -> tuple[str, str, str] | None:
    """
    Escalado por saturacion de contexto:
    1. Busca modelo mas grande en el MISMO provider (local)
    2. Si local está agotado → deduce el mejor cloud para la tarea y salta allí
    Retorna (model_name, wire_name, provider) o None.
    """
    cur_score = _model_size_score(session.model_name)
    active = session.creds.active_bago_providers()
    local_provs = ("ollama-local", "ollama-cloud")

    def _candidates_in(prov_name):
        if prov_name not in active:
            return []
        prov_data = session.providers.get(prov_name, {})
        out = []
        for mn, md in prov_data.get("models", {}).items():
            s = _model_size_score(mn)
            if s > cur_score:
                out.append((s, mn, md.get("wire_name", mn), prov_name))
        return sorted(out)

    def _any_model_in(prov_name):
        if prov_name not in active:
            return None
        prov_data = session.providers.get(prov_name, {})
        for mn, md in prov_data.get("models", {}).items():
            return mn, md.get("wire_name", mn), prov_name
        return None

    # ── Fase 1: escalar dentro de providers locales ───────────────────────
    for pn in local_provs:
        cands = _candidates_in(pn)
        if cands:
            _, mn, wn, p = cands[0]
            return mn, wn, p
        if pn != session.provider:
            r = _any_model_in(pn)
            if r:
                return r

    # ── Fase 2: local agotado → mejor cloud para la tarea deducida ───────
    cloud_prov = _deduce_cloud_provider(session.history, user_input, active)
    prov_data  = session.providers.get(cloud_prov, {})
    models     = prov_data.get("models", {})
    if models:
        # Modelo de mayor score en ese provider cloud
        best = max(models.items(), key=lambda kv: _model_size_score(kv[0]))
        mn, md = best
        return mn, md.get("wire_name", mn), cloud_prov
    return None
# ─────────────────────────────────────────────────────────────────────────────

def _llm_call(lm, kw, messages):
    r = litellm.completion(model=lm, messages=messages, **kw)
    return r.choices[0].message.content

def run_chain(session, model_sequence, prompt, silent_route=True):
    """Pipeline secuencial. Solo la respuesta final va al historial compartido."""
    context = list(session.history)
    prev_text = None

    for i, target in enumerate(model_sequence):
        is_last = (i == len(model_sequence) - 1)
        name, wire, prov = session._find_model(target)
        if not name:
            pe(f"Modelo '{target}' no disponible, saltando.")
            continue

        lm, kw = resolve_litellm(prov, wire)
        c = COLORS.get(prov, "white")

        if i == 0:
            msgs = context + [{"role":"user","content": prompt}]
        else:
            msgs = [
                {"role":"system","content": BAGO_SYSTEM},
                {"role":"user","content":
                    f"Revisa y mejora esta respuesta. Corrige errores, completa huecos, mejora claridad.\n\n"
                    f"PREGUNTA ORIGINAL: {prompt}\n\nRESPUESTA PREVIA:\n{prev_text}"}
            ]

        step_label = f"paso {i+1}/{len(model_sequence)}: {name}"
        with console.status(f"[dim {c}]{step_label}...[/dim {c}]", spinner="dots"):
            try:
                text = _llm_call(lm, kw, msgs)
            except Exception as e:
                text = f"[ERROR {name}: {e}]"

        prev_text = text

        if is_last:
            show_response(text, name, prov, label=f"[bold]✓ CHAIN FINAL[/bold] [{c}]{name}[/{c}]")
            session.history.append({"role":"user","content": prompt})
            session.history.append({"role":"assistant","content": text})
            # Dejar el modelo en el ultimo de la cadena
            session.provider, session.model_name, session.wire_name = prov, name, wire
        else:
            console.print(f"  [{c}]✓ {name}[/{c}] [dim]→ refinando con siguiente modelo...[/dim]")

def run_ensemble(session, model_list, prompt):
    """Paralelo: todos responden, el modelo activo sintetiza."""
    context = list(session.history) + [{"role":"user","content": prompt}]
    results = {}

    def call_one(target):
        name, wire, prov = session._find_model(target)
        if not name: return None, None, f"'{target}' no encontrado"
        lm, kw = resolve_litellm(prov, wire)
        try:
            text = _llm_call(lm, kw, context)
            return name, prov, text
        except Exception as e:
            return name, prov, f"[ERROR: {e}]"

    console.print(f"  [dim]Consultando {len(model_list)} modelos...[/dim]")
    with concurrent.futures.ThreadPoolExecutor() as ex:
        futures = [ex.submit(call_one, t) for t in model_list]
        for f in concurrent.futures.as_completed(futures):
            name, prov, text = f.result()
            if name:
                results[name] = {"provider": prov or "codex", "text": text}
                show_response(text, name, prov or "codex")

    if len(results) >= 2:
        pi(f"Sintetizando con {session.model_name}...")
        drafts = "\n\n".join(f"[{mn}]:\n{d['text']}" for mn, d in results.items())
        synth = (f"Combina lo mejor de estas respuestas en una sola, coherente y completa.\n"
                 f"PREGUNTA: {prompt}\n\n{drafts}")
        lm, kw = session.litellm_info
        with console.status(f"[dim]{session.model_name} sintetizando...[/dim]", spinner="dots"):
            try:
                final = _llm_call(lm, kw, [{"role":"system","content":BAGO_SYSTEM},
                                            {"role":"user","content":synth}])
            except Exception as e:
                final = next(iter(results.values()))["text"]
        show_response(final, session.model_name, session.provider,
                      label=f"[bold]✦ SÍNTESIS[/bold] [{COLORS.get(session.provider,'white')}]{session.model_name}[/{COLORS.get(session.provider,'white')}]")
        session.history.append({"role":"user","content": prompt})
        session.history.append({"role":"assistant","content": final})
    elif results:
        mn, d = next(iter(results.items()))
        session.history.append({"role":"user","content": prompt})
        session.history.append({"role":"assistant","content": d["text"]})

# ── Chat (orquestador principal) ───────────────────────────────────────────────
def chat(session, user_input):
    """
    Punto de entrada principal. El orquestador decide automaticamente:
      1. Que modelo usar (auto-route por keywords)
      2. Que estrategia usar (single / chain / ensemble)
    El usuario no necesita hacer nada, todo es transparente.
    """
    if session.autoroute:
        # Paso 1: routing por keyword → mejor modelo para esta tarea
        switched, reason = session.auto_route(user_input)
        if switched:
            c = COLORS.get(session.provider, "white")
            console.print(f"  [dim {c}]{reason}[/dim {c}]")
        elif reason:
            c = COLORS.get(session.provider, "white")
            console.print(f"  [dim {c}]{reason}[/dim {c}]")

        # Paso 2: detectar estrategia optima
        active = session.creds.active_bago_providers()
        strategy, providers_for_strategy = detect_strategy(user_input, active)

        if strategy == "chain" and len(providers_for_strategy) >= 2:
            console.print(f"  [dim]⛓ chain auto: {' → '.join(providers_for_strategy)}[/dim]")
            run_chain(session, providers_for_strategy, user_input)
            return None  # ya mostrado y añadido al historial dentro de run_chain

        if strategy == "ensemble" and len(providers_for_strategy) >= 2:
            console.print(f"  [dim]◈ ensemble auto: {', '.join(providers_for_strategy)}[/dim]")
            run_ensemble(session, providers_for_strategy, user_input)
            return None

    # Estrategia single (o autoroute desactivado)
    session.history.append({"role":"user","content":user_input})
    lm, kw = session.litellm_info
    try:
        with console.status(f"[dim]{session.model_name}...[/dim]", spinner="dots"):
            text = _llm_call(lm, kw, session.history)

        # ── Capa 1: eliminar bloques repetidos dentro de la respuesta ──────
        text = _dedup_paragraphs(text)

        # ── Capa 2: si la respuesta es casi igual a la anterior, reintentar ─
        prev = _last_assistant(session.history[:-1])
        if prev and _jaccard(text, prev) >= _REPEAT_THRESHOLD:
            console.print("  [dim yellow]⚠ respuesta repetitiva detectada — reintentando con mayor profundidad...[/dim yellow]")
            anti_repeat = (
                "ALERTA: Tu respuesta fue casi identica a la anterior. Esto no es aceptable. "
                "Debes profundizar REALMENTE. Para esta nueva respuesta:\n"
                "1. No copies ni parafrasees nada de lo ya dicho.\n"
                "2. Baja un nivel mas: mecanismos internos, por que funciona asi, que pasa si falla.\n"
                "3. Da ejemplos CONCRETOS y ESPECIFICOS (valores reales, rutas reales, codigo real).\n"
                "4. Explica implicaciones practicas que no se mencionaron antes.\n"
                "5. Si hay alternativas o casos limite, describelos ahora.\n"
                f"Pregunta original del usuario: {user_input}"
            )
            msgs_retry = session.history[:-1] + [{"role":"user","content":anti_repeat}]
            with console.status(f"[dim]{session.model_name} (anti-rep)...[/dim]", spinner="dots"):
                text = _llm_call(lm, kw, msgs_retry)
            text = _dedup_paragraphs(text)

        session.history.append({"role":"assistant","content": text})
        session.last_route = {
            "mode": "auto" if session.autoroute else "manual",
            "provider": session.provider,
            "model": session.model_name,
            "reason": session.last_route.get("reason", "single"),
        }
        return text

    except Exception as e:
        session.history.pop()

        # ── Escalado por saturación de contexto ────────────────────────────
        if _is_ctx_overflow(e):
            escalation = _escalate_model(session, user_input)
            if escalation:
                new_model, new_wire, new_prov = escalation
                old_model = session.model_name
                c_new = COLORS.get(new_prov, "white")
                is_cloud = new_prov not in ("ollama-local", "ollama-cloud")
                tag = "☁ cloud" if is_cloud else "⬆ local"
                console.print(
                    f"  [dim yellow]⚡ contexto saturado ({old_model}) "
                    f"→ {tag}: [{c_new}]{new_model}[/{c_new}] ({new_prov})[/dim yellow]"
                )
                session.provider    = new_prov
                session.model_name  = new_model
                session.wire_name   = new_wire
                session.switches   += 1
                session.last_route  = {
                    "mode": "auto", "provider": new_prov, "model": new_model,
                    "reason": f"ctx-overflow escalation desde {old_model}",
                }
                # Reintentar con el nuevo modelo
                session.history.append({"role":"user","content":user_input})
                lm2, kw2 = session.litellm_info
                try:
                    with console.status(f"[dim]{new_model}...[/dim]", spinner="dots"):
                        text2 = _llm_call(lm2, kw2, session.history)
                    text2 = _dedup_paragraphs(text2)
                    session.history.append({"role":"assistant","content": text2})
                    return text2
                except Exception as e2:
                    session.history.pop()
                    raise RuntimeError(str(e2))

        raise RuntimeError(str(e))

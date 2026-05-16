
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
        prev = _last_assistant(session.history[:-1])  # historial SIN el user actual
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
        raise RuntimeError(str(e))

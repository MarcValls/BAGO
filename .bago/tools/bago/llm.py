
import concurrent.futures

import litellm

from .constants import BAGO_SYSTEM, COLORS
from .providers import detect_strategy, resolve_litellm
from .ui import console, pe, pi, show_response

litellm.suppress_debug_info = True
litellm.set_verbose = False

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
        session.history.append({"role":"assistant","content": text})
        return text
    except Exception as e:
        session.history.pop()
        raise RuntimeError(str(e))

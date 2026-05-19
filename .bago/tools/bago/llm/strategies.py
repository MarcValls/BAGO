"""bago.llm.strategies — Estrategias de llamada: chain y ensemble."""

import concurrent.futures

from ..constants import BAGO_SYSTEM, COLORS
from ..providers import resolve_litellm
from ..ui import console, pe, pi, show_response

from .call import _llm_call


def run_chain(session, model_sequence, prompt, silent_route=True, *, history_input: str | None = None):
    """Pipeline secuencial. Solo la respuesta final va al historial compartido.

    Args:
        prompt:        texto que ve el LLM (con secretos de tumba ya sustituidos).
        history_input: texto que se guarda en history (con {{placeholders}}).
                       Si None, se usa prompt (compat hacia atrás).
    """
    history_msg = history_input if history_input is not None else prompt
    context   = list(session.history)
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
            msgs = context + [{"role": "user", "content": prompt}]
        else:
            msgs = [
                {"role": "system", "content": BAGO_SYSTEM},
                {"role": "user", "content": (
                    "Revisa y mejora esta respuesta. Corrige errores, completa huecos, mejora claridad.\n\n"
                    f"PREGUNTA ORIGINAL: {prompt}\n\nRESPUESTA PREVIA:\n{prev_text}"
                )},
            ]

        step_label = f"paso {i+1}/{len(model_sequence)}: {name}"
        with console.status(f"[dim {c}]{step_label}...[/dim {c}]", spinner="dots"):
            try:
                text = _llm_call(lm, kw, msgs, session=session, _provider=prov, _model=name)
            except Exception as e:
                text = f"[ERROR {name}: {e}]"

        prev_text = text

        if is_last:
            show_response(text, name, prov, label=f"[bold]✓ CHAIN FINAL[/bold] [{c}]{name}[/{c}]")
            session.history.append({"role": "user", "content": history_msg})
            session.history.append({"role": "assistant", "content": text})
            session.provider, session.model_name, session.wire_name = prov, name, wire
        else:
            console.print(f"  [{c}]✓ {name}[/{c}] [dim]→ refinando con siguiente modelo...[/dim]")


def run_ensemble(session, model_list, prompt, *, history_input: str | None = None):
    """Paralelo: todos los modelos responden; el modelo activo sintetiza.

    Args:
        prompt:        texto que ve el LLM (con secretos sustituidos).
        history_input: texto que se guarda en history (con {{placeholders}}).
    """
    history_msg = history_input if history_input is not None else prompt
    context = list(session.history) + [{"role": "user", "content": prompt}]
    results: dict = {}

    def call_one(target):
        name, wire, prov = session._find_model(target)
        if not name:
            return None, None, f"'{target}' no encontrado"
        lm, kw = resolve_litellm(prov, wire)
        try:
            text = _llm_call(lm, kw, context, session=session, _provider=prov, _model=name)
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
        synth  = (
            "Combina lo mejor de estas respuestas en una sola, coherente y completa.\n"
            f"PREGUNTA: {prompt}\n\n{drafts}"
        )
        lm, kw = session.litellm_info
        with console.status(f"[dim]{session.model_name} sintetizando...[/dim]", spinner="dots"):
            try:
                final = _llm_call(
                    lm, kw,
                    [{"role": "system", "content": BAGO_SYSTEM},
                     {"role": "user", "content": synth}],
                    session=session,
                )
            except Exception:
                final = next(iter(results.values()))["text"]
        c = COLORS.get(session.provider, "white")
        show_response(
            final, session.model_name, session.provider,
            label=f"[bold]✦ SÍNTESIS[/bold] [{c}]{session.model_name}[/{c}]",
        )
        session.history.append({"role": "user",      "content": history_msg})
        session.history.append({"role": "assistant", "content": final})
    elif results:
        _, d = next(iter(results.items()))
        session.history.append({"role": "user",      "content": history_msg})
        session.history.append({"role": "assistant", "content": d["text"]})

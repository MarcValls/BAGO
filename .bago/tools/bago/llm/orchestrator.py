"""bago.llm.orchestrator — Punto de entrada principal: chat().

Integra:
- auto-routing por keywords
- detección de estrategia (single / chain / ensemble)
- pre-call: escalado preventivo a cloud si el mensaje tiene URLs
- post-call: detección de respuesta basura + escalado a cloud + reintento
- anti-repetición
- escalado por saturación de contexto
"""

from ..constants import COLORS
from ..providers import detect_strategy, resolve_litellm
from ..ui import console, pi

from .call import _llm_call
from .errors import _is_ctx_overflow
from .quality import _dedup_paragraphs, _jaccard, _last_assistant, _needs_cloud_for_url, _REPEAT_THRESHOLD, _response_is_garbage
from .routing import _cloud_escalation_for_quality, _escalate_model
from .strategies import run_chain, run_ensemble


def _preemptive_cloud_escalation(session, user_input: str) -> bool:
    """Escala a cloud ANTES de llamar cuando el mensaje requiere internet.

    Retorna True si se escaló.
    """
    escalation = _cloud_escalation_for_quality(session, user_input)
    if not escalation:
        return False
    new_model, new_wire, new_prov = escalation
    old_label = f"{session.provider}/{session.model_name}"
    c_new = COLORS.get(new_prov, "white")
    console.print(
        f"  [dim cyan]🌐 URL detectada — escalando a cloud [{c_new}]{new_prov}/{new_model}[/{c_new}] "
        f"(era {old_label})[/dim cyan]"
    )
    session.provider   = new_prov
    session.model_name = new_model
    session.wire_name  = new_wire
    session.switches  += 1
    session.last_route = {
        "mode": "auto", "provider": new_prov, "model": new_model,
        "reason": f"preemptive-url-escalation desde {old_label}",
    }
    return True


def _quality_cloud_retry(session, user_input: str, reason: str) -> "str | None":
    """Escala a cloud y reintenta cuando la respuesta es basura.

    Retorna la nueva respuesta o None si no hay cloud disponible.
    """
    escalation = _cloud_escalation_for_quality(session, user_input)
    if not escalation:
        return None
    new_model, new_wire, new_prov = escalation
    old_label = f"{session.provider}/{session.model_name}"
    c_new = COLORS.get(new_prov, "white")
    console.print(
        f"  [dim yellow]⚠ Respuesta incoherente ({reason}) "
        f"→ escalando a [{c_new}]{new_prov}/{new_model}[/{c_new}][/dim yellow]"
    )
    session.provider   = new_prov
    session.model_name = new_model
    session.wire_name  = new_wire
    session.switches  += 1
    session.last_route = {
        "mode": "auto", "provider": new_prov, "model": new_model,
        "reason": f"quality-guard escalation desde {old_label}",
    }
    lm, kw = session.litellm_info
    try:
        with console.status(f"[dim]{new_model}...[/dim]", spinner="dots"):
            text2 = _llm_call(lm, kw, session.history, session=session,
                              _provider=new_prov, _model=new_model)
        return _dedup_paragraphs(text2)
    except Exception:
        return None


def chat(session, user_input, *, history_input: str | None = None):
    """Orquestador principal — decide modelo, estrategia y calidad de respuesta.

    Args:
        user_input:    Texto que ve el LLM (puede tener secretos de tumba sustituidos).
        history_input: Texto que se guarda en history (conserva {{placeholders}} de tumba).
                       Si None, se usa user_input para ambos.

    Flujo:
      1. Auto-routing por keywords
      2. Pre-call: si URL en mensaje y provider local → escalar a cloud
      3. Detectar estrategia (single / chain / ensemble)
      4. Llamar al modelo
      5. Anti-repetición (dedup + jaccard)
      6. Post-call: quality guard → si basura → escalar + reintentar
      7. Escalado por saturación de contexto
    """
    # La entrada que va a history conserva {{placeholders}} para no filtrar secretos
    history_msg = history_input if history_input is not None else user_input
    if session.autoroute:
        # ── Paso 1: routing por keyword ───────────────────────────────────────
        switched, reason = session.auto_route(user_input)
        if switched or reason:
            c = COLORS.get(session.provider, "white")
            console.print(f"  [dim {c}]{reason}[/dim {c}]")

        # ── Paso 2: pre-call URL escalation ──────────────────────────────────
        _preemptive_cloud_escalation(session, user_input)

        # ── Paso 3: detectar estrategia ───────────────────────────────────────
        active = session.creds.active_bago_providers()
        strategy, providers_for_strategy = detect_strategy(user_input, active)

        if strategy == "chain" and len(providers_for_strategy) >= 2:
            console.print(f"  [dim]⛓ chain auto: {' → '.join(providers_for_strategy)}[/dim]")
            run_chain(session, providers_for_strategy, user_input)
            return None

        if strategy == "ensemble" and len(providers_for_strategy) >= 2:
            console.print(f"  [dim]◈ ensemble auto: {', '.join(providers_for_strategy)}[/dim]")
            run_ensemble(session, providers_for_strategy, user_input)
            return None

    # ── Estrategia single (o autoroute desactivado) ───────────────────────────
    # history_msg conserva {{placeholders}} para no filtrar secretos al disco
    session.history.append({"role": "user", "content": history_msg})
    lm, kw = session.litellm_info
    try:
        with console.status(f"[dim]{session.model_name}...[/dim]", spinner="dots"):
            text = _llm_call(lm, kw, session.history, session=session)

        # ── Anti-rep capa 1: eliminar bloques duplicados ─────────────────────
        text = _dedup_paragraphs(text)

        # ── Anti-rep capa 2: reintentar si respuesta ≈ anterior ──────────────
        prev = _last_assistant(session.history[:-1])
        if prev and _jaccard(text, prev) >= _REPEAT_THRESHOLD:
            console.print(
                "  [dim yellow]⚠ respuesta repetitiva detectada — "
                "reintentando con mayor profundidad...[/dim yellow]"
            )
            anti_repeat = (
                "ALERTA: Tu respuesta fue casi idéntica a la anterior. Esto no es aceptable. "
                "Debes profundizar REALMENTE. Para esta nueva respuesta:\n"
                "1. No copies ni parafrasees nada de lo ya dicho.\n"
                "2. Baja un nivel más: mecanismos internos, por qué funciona así, qué pasa si falla.\n"
                "3. Da ejemplos CONCRETOS y ESPECÍFICOS (valores reales, rutas reales, código real).\n"
                "4. Explica implicaciones prácticas que no se mencionaron antes.\n"
                "5. Si hay alternativas o casos límite, descríbelos ahora.\n"
                f"Pregunta original del usuario: {user_input}"
            )
            msgs_retry = session.history[:-1] + [{"role": "user", "content": anti_repeat}]
            with console.status(f"[dim]{session.model_name} (anti-rep)...[/dim]", spinner="dots"):
                text = _llm_call(lm, kw, msgs_retry, session=session)
            text = _dedup_paragraphs(text)

        # ── Quality guard: detectar basura → escalar a cloud ─────────────────
        is_garbage, garbage_reason = _response_is_garbage(user_input, text)
        if is_garbage:
            retry_text = _quality_cloud_retry(session, user_input, garbage_reason)
            if retry_text:
                text = retry_text

        session.history.append({"role": "assistant", "content": text})
        session.last_route = {
            "mode":     "auto" if session.autoroute else "manual",
            "provider": session.provider,
            "model":    session.model_name,
            "reason":   session.last_route.get("reason", "single"),
        }
        return text

    except (KeyboardInterrupt, SystemExit):
        # audit-1: evitar que el user turn quede huérfano en history sin respuesta
        session.history.pop()
        raise

    except Exception as e:
        session.history.pop()

        # ── Escalado por saturación de contexto ──────────────────────────────
        if _is_ctx_overflow(e):
            escalation = _escalate_model(session, user_input)
            if escalation:
                new_model, new_wire, new_prov = escalation
                old_model = session.model_name
                c_new     = COLORS.get(new_prov, "white")
                is_cloud  = new_prov not in ("ollama-local", "ollama-cloud")
                tag       = "☁ cloud" if is_cloud else "⬆ local"
                console.print(
                    f"  [dim yellow]⚡ contexto saturado ({old_model}) "
                    f"→ {tag}: [{c_new}]{new_model}[/{c_new}] ({new_prov})[/dim yellow]"
                )
                session.provider   = new_prov
                session.model_name = new_model
                session.wire_name  = new_wire
                session.switches  += 1
                session.last_route = {
                    "mode": "auto", "provider": new_prov, "model": new_model,
                    "reason": f"ctx-overflow escalation desde {old_model}",
                }
                session.history.append({"role": "user", "content": user_input})
                lm2, kw2 = session.litellm_info
                try:
                    with console.status(f"[dim]{new_model}...[/dim]", spinner="dots"):
                        text2 = _llm_call(lm2, kw2, session.history,
                                          session=session, _provider=new_prov, _model=new_model)
                    text2 = _dedup_paragraphs(text2)
                    session.history.append({"role": "assistant", "content": text2})
                    return text2
                except Exception as e2:
                    session.history.pop()
                    raise RuntimeError(str(e2))

        raise RuntimeError(str(e))

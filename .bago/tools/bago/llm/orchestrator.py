"""bago.llm.orchestrator — Punto de entrada principal: chat().

Integra:
- auto-routing por keywords
- detección de estrategia (single / chain / ensemble)
- pre-call: escalado preventivo a cloud si el mensaje tiene URLs
- post-call: detección de respuesta basura + escalado a cloud + reintento
- anti-repetición
- escalado por saturación de contexto
"""
from pathlib import Path

import os
import re
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ..constants import COLORS
from ..providers import detect_strategy, describe_model_source, resolve_litellm, best_model_for_provider
from ..ui import console, pi

from .call import _llm_call
from .errors import _is_ctx_overflow
from .quality import _dedup_paragraphs, _jaccard, _last_assistant, _needs_cloud_for_url, _REPEAT_THRESHOLD, _response_is_garbage
from .routing import _cloud_escalation_for_quality, _escalate_model, _cloud_escalation_candidates, _escalate_candidates
from .strategies import run_chain, run_ensemble
from ..routing_runtime import active_settings, resolve_contract, validate_contract



def _contract_candidate_targets(session) -> list[str]:
    settings = active_settings()
    preset = settings.get("preset", {})
    order = [f"{session.provider}/{session.model_name}"]
    active = [
        p for p in session.creds.active_bago_providers()
        if p not in getattr(session, "skip_providers", set())
    ]
    for prov in preset.get("provider_order", []):
        if prov in active:
            best = best_model_for_provider(prov, session.providers)
            if best:
                order.append(f"{prov}/{best[0]}")
            else:
                order.append(prov)
    dedup = []
    seen = set()
    for item in order:
        if item not in seen:
            seen.add(item)
            dedup.append(item)
    return dedup


def _contract_prompt(user_input: str, contract_text: str, draft: str, unmet: list[str], iteration: int, max_iter: int) -> str:
    if not draft:
        return (
            f"TAREA ORIGINAL:\n{user_input}\n\n"
            f"CONTRATO OBLIGATORIO:\n{contract_text}\n\n"
            "Devuelve una respuesta final que cumpla estrictamente el contrato. "
            "Si alguna parte del contrato no aplica, dilo dentro de la salida final sin romper el formato pedido."
        )
    unmet_block = "\n".join(f"- {u}" for u in unmet) if unmet else "- mejora claridad y ajuste"
    return (
        f"ITERACION {iteration}/{max_iter} DEL BUCLE DE CONTRATO.\n"
        f"TAREA ORIGINAL:\n{user_input}\n\n"
        f"CONTRATO OBLIGATORIO:\n{contract_text}\n\n"
        f"BORRADOR ACTUAL:\n{draft}\n\n"
        f"DESAJUSTES DETECTADOS:\n{unmet_block}\n\n"
        "Reescribe la respuesta completa para que cumpla el contrato mejor que el borrador. "
        "No expliques el proceso; devuelve solo la salida final."
    )


def _run_contract_loop(session, user_input: str, history_msg: str, contract_text: str) -> str | None:
    if not getattr(session, "contract_loop_enabled", False):
        return None
    targets = _contract_candidate_targets(session)
    if not targets:
        return None

    best_text = None
    best_validation = {"ok": False, "score": 0.0, "unmet": ["sin validacion"]}
    best_route = None
    prev_text = ""
    max_iter = max(1, int(getattr(session, "contract_max_iter", 3)))

    for idx in range(max_iter):
        target = targets[min(idx, len(targets) - 1)]
        name, wire, prov = session._find_model(target)
        if not name:
            continue
        lm, kw = resolve_litellm(prov, wire)
        prompt = _contract_prompt(user_input, contract_text, prev_text, best_validation.get("unmet", []), idx + 1, max_iter)
        msgs = session.history + [{"role": "user", "content": prompt}]
        with console.status(f"[dim]{name} contract-loop {idx+1}/{max_iter}...[/dim]", spinner="dots"):
            text = _llm_call(lm, kw, msgs, session=session, _provider=prov, _model=name)
        validation = validate_contract(contract_text, text)
        session.last_contract_report = validation
        source = describe_model_source(prov, name, session.providers, wire_name=wire)
        session.last_route = {
            "mode": "auto" if session.autoroute else "manual",
            "provider": prov,
            "model": name,
            "reason": f"contract-loop {idx+1}/{max_iter} score={validation.get('score')}",
            "service": source.get("service", ""),
            "route": source.get("route", ""),
            "backend": source.get("backend", ""),
        }
        prev_text = text
        if validation.get("score", 0.0) >= best_validation.get("score", 0.0):
            best_text = text
            best_validation = validation
            session.provider, session.model_name, session.wire_name = prov, name, wire
            source = session._update_model_origin(prov, name, wire)
            best_route = {
                "mode": "auto" if session.autoroute else "manual",
                "provider": prov,
                "model": name,
                "reason": f"contract-loop {idx+1}/{max_iter} score={validation.get('score')}",
                "service": source.get("service", ""),
                "route": source.get("route", ""),
                "backend": source.get("backend", ""),
            }
            session.last_route = {
                **best_route,
            }
        if validation.get("ok"):
            session.history.append({"role": "user", "content": history_msg})
            session.history.append({"role": "assistant", "content": text})
            return text

    if best_text is not None:
        if best_route:
            session.last_route = best_route
        session.history.append({"role": "user", "content": history_msg})
        session.history.append({"role": "assistant", "content": best_text})
        return best_text
    return None


def _preemptive_cloud_escalation(session, user_input: str) -> bool:
    """Escala a cloud ANTES de llamar cuando el mensaje requiere internet.

    Retorna True si se escaló.
    """
    if not _needs_cloud_for_url(user_input, session):
        return False
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
    source = session._update_model_origin(new_prov, new_model, new_wire)
    session.switches  += 1
    session.last_route = {
        "mode": "auto", "provider": new_prov, "model": new_model,
        "reason": f"preemptive-url-escalation desde {old_label}",
        "service": source.get("service", ""),
        "route": source.get("route", ""),
        "backend": source.get("backend", ""),
    }
    return True


def _looks_like_helpful_clarification(text: str) -> bool:
    """Detecta si la respuesta es una aclaración genuina, no evasiva."""
    for pattern in (
        r"(?i)\b(te refieres a|hablas de|est[aá]s buscando|quieres que)\b",
        r"(?i)\b(puedes|podr[ií]as)\s+(decirme|confirmar|especificar|aclarar|mostrar)\b",
        r"(?i)\b(necesito|me falta|me hace falta)\b.{5,}",
    ):
        if re.search(pattern, text or ""):
            return True
    return False


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
    source = session._update_model_origin(new_prov, new_model, new_wire)
    session.switches  += 1
    session.last_route = {
        "mode": "auto", "provider": new_prov, "model": new_model,
        "reason": f"quality-guard escalation desde {old_label}",
        "service": source.get("service", ""),
        "route": source.get("route", ""),
        "backend": source.get("backend", ""),
    }
    lm, kw = session.litellm_info
    try:
        with console.status(f"[dim]{new_model}...[/dim]", spinner="dots"):
            text2 = _llm_call(lm, kw, session.history, session=session,
                              _provider=new_prov, _model=new_model)
        return _dedup_paragraphs(text2)
    except Exception:
        return None


def _spiral_single(session, history_msg: str, user_input: str) -> str:
    """Espiral: modo single-model sin fallback."""
    session.history.append({"role": "user", "content": history_msg})
    lm, kw = session.litellm_info
    with console.status(f"[dim]{session.model_name}...[/dim]", spinner="dots"):
        text = _llm_call(lm, kw, session.history, session=session)
    text = _dedup_paragraphs(text)
    session.history.append({"role": "assistant", "content": text})
    source = session._update_model_origin(session.provider, session.model_name, session.wire_name)
    session.last_route = {
        "mode": "single",
        "provider": session.provider,
        "model": session.model_name,
        "reason": "single-model mode",
        "service": source.get("service", ""),
        "route": source.get("route", ""),
        "backend": source.get("backend", ""),
    }
    return text


def _spiral_brainstorm(session, history_msg: str, user_input: str) -> str:
    """Espiral: modo brainstorm — fuerza análisis concreto."""
    brainstorm_prompt = (
        "[MODO BRAINSTORM ACTIVO] Resultado CONCRETO obligatorio:\n"
        "1. ANALISIS: Identifica minimo 3 aspectos concretos.\n"
        "2. GENERACION: Propón minimo 2 soluciones implementables con codigo real.\n"
        "3. EVIDENCIA: Cada afirmacion con ejemplo especifico.\n"
        "4. PROHIBIDO: vaguedades, depends, podria ser.\n"
        "5. FORMATO: listas, codigo real, rutas absolutas, valores concretos.\n"
        f"TAREA: {history_msg}\n"
    )
    session.history.append({"role": "user", "content": brainstorm_prompt})
    return _spiral_call_with_guards(session, user_input)


def _spiral_normal(session, history_msg: str, user_input: str) -> str:
    """Espiral: llamada normal con anti-rep + quality guard."""
    session.history.append({"role": "user", "content": history_msg})
    return _spiral_call_with_guards(session, user_input)


def _spiral_call_with_guards(session, user_input: str) -> str:
    """Núcleo compartido: LLM call + anti-rep + quality guard + ctx overflow."""
    lm, kw = session.litellm_info
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
    if is_garbage and not _looks_like_helpful_clarification(text):
        retry_text = _quality_cloud_retry(session, user_input, garbage_reason)
        if retry_text:
            text = retry_text

    session.history.append({"role": "assistant", "content": text})
    session.last_route = {
        "mode":     "auto" if session.autoroute else "manual",
        "provider": session.provider,
        "model":    session.model_name,
        "reason":   session.last_route.get("reason", "single"),
        "service":   session.model_origin.get("service", ""),
        "route":     session.model_origin.get("route", ""),
        "backend":   session.model_origin.get("backend", ""),
    }
    return text


def _spiral_ctx_overflow_retry(session, history_msg: str, user_input: str) -> str:
    """Espiral: reintento tras desbordamiento de contexto."""
    escalation = _escalate_model(session, user_input)
    if not escalation:
        raise RuntimeError("contexto saturado y sin modelo de escalado disponible")
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
    source = session._update_model_origin(new_prov, new_model, new_wire)
    session.switches  += 1
    session.last_route = {
        "mode": "auto", "provider": new_prov, "model": new_model,
        "reason": f"ctx-overflow escalation desde {old_model}",
        "service": source.get("service", ""),
        "route": source.get("route", ""),
        "backend": source.get("backend", ""),
    }
    session.history.append({"role": "user", "content": history_msg})
    lm2, kw2 = session.litellm_info
    with console.status(f"[dim]{new_model}...[/dim]", spinner="dots"):
        text2 = _llm_call(lm2, kw2, session.history,
                          session=session, _provider=new_prov, _model=new_model)
    text2 = _dedup_paragraphs(text2)
    session.history.append({"role": "assistant", "content": text2})
    return text2


def chat(session, user_input, *, history_input: str | None = None):
    """Orquestador principal — un solo punto de salida en espiral.

    Args:
        user_input:    Texto que ve el LLM (puede tener secretos de tumba sustituidos).
        history_input: Texto que se guarda en history (conserva {{placeholders}} de tumba).
                       Si None, se usa user_input para ambos.

    Flujo espiral:
      1. Auto-routing por keywords
      2. Pre-call: si URL en mensaje y provider local → escalar a cloud
      3. Detectar estrategia (single / chain / ensemble)
      4. Llamar al modelo
      5. Anti-repetición (dedup + jaccard)
      6. Post-call: quality guard → si basura → escalar + reintentar
      7. Escalado por saturación de contexto
      ── Todas las ramas confluyen en un único return al final.
    """
    history_msg = history_input if history_input is not None else user_input
    contract_text = resolve_contract(history_msg, getattr(session, "output_contract", ""))

    result = None      # ── única variable de salida ──

    try:
        # ── Espiral 1–3: routing + estrategia ──────────────────────────────
        if session.autoroute:
            switched, reason = session.auto_route(user_input)
            if switched or reason:
                c = COLORS.get(session.provider, "white")
                console.print(f"  [dim {c}]{reason}[/dim {c}]")
            _preemptive_cloud_escalation(session, user_input)

            active = [
                p for p in session.creds.active_bago_providers()
                if p not in getattr(session, "skip_providers", set())
            ]
            strategy, providers_for_strategy = detect_strategy(user_input, active)

            if contract_text and getattr(session, "contract_loop_enabled", False):
                result = _run_contract_loop(session, user_input, history_msg, contract_text)
            elif strategy == "chain" and len(providers_for_strategy) >= 2:
                console.print(f"  [dim]⛓ chain auto: {' → '.join(providers_for_strategy)}[/dim]")
                run_chain(session, providers_for_strategy, user_input, history_input=history_msg)
            elif strategy == "ensemble" and len(providers_for_strategy) >= 2:
                console.print(f"  [dim]◈ ensemble auto: {', '.join(providers_for_strategy)}[/dim]")
                run_ensemble(session, providers_for_strategy, user_input, history_input=history_msg)

        # ── Espiral 4–6: llamada al modelo con guards ────────────────────
        if result is None:
            if getattr(session, "single_model", False):
                result = _spiral_single(session, history_msg, user_input)
            elif getattr(session, "brainstorm", False):
                result = _spiral_brainstorm(session, history_msg, user_input)
            else:
                result = _spiral_normal(session, history_msg, user_input)

    except (KeyboardInterrupt, SystemExit):
        if session.history and session.history[-1].get("role") == "user":
            session.history.pop()
        raise

    except Exception as exc:
        # Deshacer turno huérfano
        if session.history and session.history[-1].get("role") == "user":
            session.history.pop()
        # ── Espiral 7: escalado por saturación de contexto ───────────────
        if _is_ctx_overflow(exc):
            try:
                result = _spiral_ctx_overflow_retry(session, history_msg, user_input)
            except Exception:
                raise RuntimeError(str(exc))
        else:
            raise RuntimeError(str(exc))

    # ── ÚNICO PUNTO DE SALIDA ──────────────────────────────────────────────
    return result


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

"""bago.llm.routing — Scoring de modelos, cadenas de escalado y deducción de cloud."""

import os

# ── Scoring de tamaño de modelo ───────────────────────────────────────────────

def _model_size_score(name: str) -> int:
    """Tamaño aproximado según nombre del modelo (mayor = más capacidad)."""
    n = name.lower()
    if any(x in n for x in ("0.5b", "1b", "mini")):                  return 1
    if any(x in n for x in ("2b", "3b")):                             return 2
    if any(x in n for x in ("7b", "8b")):                             return 3
    if "coder" in n and not any(x in n for x in ("14b","32b","72b")): return 3
    if any(x in n for x in ("13b", "14b")):                           return 4
    if any(x in n for x in ("30b", "32b", "34b")):                    return 5
    if any(x in n for x in ("70b", "72b")):                           return 6
    return 3  # desconocido → medio


# ── Fallback Ollama local ──────────────────────────────────────────────────────

def _ollama_fallback_model(missing_model: str) -> "tuple[str | None, list[str]]":
    """Busca modelos Ollama locales disponibles y elige el mejor sustituto."""
    from ..providers import ollama_probe
    probe     = ollama_probe()
    available = probe.get("models", [])
    if not available:
        return None, []
    is_coder = "coder" in missing_model.lower()
    scored = sorted(
        available,
        key=lambda m: (
            (1 if is_coder and "coder" in m.lower() else 0),
            _model_size_score(m),
        ),
        reverse=True,
    )
    return scored[0], available


# ── Equivalencias local → cloud ────────────────────────────────────────────────

# score de tamaño → (copilot_model, codex_model)
_CLOUD_EQUIV = {
    0: ("gpt-4o-mini", "gpt-4o-mini"),
    1: ("gpt-4o-mini", "gpt-4o-mini"),
    2: ("gpt-4o-mini", "gpt-4o-mini"),
    3: ("gpt-4o",      "gpt-4o"),
    4: ("gpt-4o",      "gpt-4o"),
    5: ("gpt-4o",      "gpt-4o"),
    6: ("gpt-4o",      "gpt-4o"),
}


def _build_escalation_chain(missing_model: str) -> "tuple[list, list]":
    """Construye la cadena de fallback para cuando un modelo Ollama no existe.

    Orden: otros Ollama locales → copilot → codex.
    Devuelve (chain, available) donde chain es lista de (lm_wire, kw_dict, label).
    """
    from ..providers import _codex_access_token

    chain: list[tuple[str, dict, str]] = []
    score = _model_size_score(missing_model)

    # 1. Ollama local: otros modelos instalados
    fallback_local, available = _ollama_fallback_model(missing_model)
    if fallback_local:
        wire = f"ollama/{fallback_local}"
        chain.append((wire, {"api_base": "http://127.0.0.1:11434"}, f"ollama-local / {fallback_local}"))

    # 2. copilot: GitHub Models
    gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    if gh_token:
        copilot_model = _CLOUD_EQUIV.get(score, _CLOUD_EQUIV[3])[0]
        chain.append((
            f"openai/{copilot_model}",
            {"api_base": "https://models.inference.ai.azure.com", "api_key": gh_token},
            f"copilot / {copilot_model}",
        ))

    # 3. codex: OpenAI API key o Codex CLI OAuth
    openai_key  = os.environ.get("OPENAI_API_KEY", "")
    codex_token = openai_key or _codex_access_token()
    if codex_token:
        codex_model = _CLOUD_EQUIV.get(score, _CLOUD_EQUIV[3])[1]
        chain.append((
            codex_model,
            {"api_key": codex_token},
            f"codex / {codex_model}",
        ))

    return chain, available


# ── Deducción de provider cloud óptimo para la tarea ─────────────────────────

_ESCALATE_PROV_ORDER = ("ollama-local", "ollama-cloud", "copilot", "codex", "anthropic")

_TASK_CLOUD_HINTS: dict[str, tuple] = {
    "codex": (
        "codigo","code","funcion","function","clase","class","script","api",
        "test","algoritmo","algorithm","refactor","debug","error","bug",
        "implementa","implement","build","compile",
    ),
    "copilot": (
        "explica","analiza","diseña","arquitectura","razona","razonamiento",
        "estrategia","planifica","documenta","explain","analyze","design",
        "architecture","reason","strategy","plan","document","compare",
        "cual es mejor","pros","contras","decision",
    ),
    "anthropic": (
        "redacta","escribe","resume","traduce","creative","write","summarize",
        "translate","draft","articulo","essay","narrativa",
    ),
}


def _deduce_cloud_provider(history: list, user_input: str, active: list) -> str:
    """Deduce el mejor provider cloud para la tarea combinando el input actual
    y los últimos mensajes del usuario en el historial."""
    ctx_msgs = [m["content"] for m in history if m.get("role") == "user"][-4:]
    ctx = " ".join(ctx_msgs + [user_input]).lower()

    scores: dict[str, int] = {p: 0 for p in _TASK_CLOUD_HINTS}
    for prov, keywords in _TASK_CLOUD_HINTS.items():
        scores[prov] = sum(1 for kw in keywords if kw in ctx)

    cloud_order = ("codex", "copilot", "anthropic")
    for prov in sorted(cloud_order, key=lambda p: -scores.get(p, 0)):
        if prov in active:
            return prov
    for prov in cloud_order:
        if prov in active:
            return prov
    return "copilot"


def _escalate_model(session, user_input: str = "") -> "tuple[str, str, str] | None":
    """Escalado por saturación de contexto o calidad.

    1. Busca modelo más grande en el MISMO provider (local primero).
    2. Si local está agotado → deduce el mejor cloud para la tarea y salta allí.
    Retorna (model_name, wire_name, provider) o None.
    """
    cur_score = _model_size_score(session.model_name)
    active    = [p for p in session.creds.active_bago_providers()
                 if p not in getattr(session, "skip_providers", set())]
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

    # Fase 1: escalar dentro de providers locales
    for pn in local_provs:
        cands = _candidates_in(pn)
        if cands:
            _, mn, wn, p = cands[0]
            return mn, wn, p
        if pn != session.provider:
            r = _any_model_in(pn)
            if r:
                return r

    # Fase 2: local agotado → mejor cloud para la tarea deducida
    cloud_prov = _deduce_cloud_provider(session.history, user_input, active)
    prov_data  = session.providers.get(cloud_prov, {})
    models     = prov_data.get("models", {})
    if models:
        best = max(models.items(), key=lambda kv: _model_size_score(kv[0]))
        mn, md = best
        return mn, md.get("wire_name", mn), cloud_prov
    return None


def _cloud_escalation_for_quality(session, user_input: str) -> "tuple[str, str, str] | None":
    """Encuentra el mejor provider cloud para escalar por fallo de calidad o URL.

    Prioriza cualquier cloud activo sobre Ollama.
    Retorna (model_name, wire_name, provider) o None si no hay cloud.
    """
    active = [p for p in session.creds.active_bago_providers()
              if p not in getattr(session, "skip_providers", set())]
    cloud_prov = _deduce_cloud_provider(session.history, user_input, active)
    prov_data  = session.providers.get(cloud_prov, {})
    models     = prov_data.get("models", {})
    if models:
        best = max(models.items(), key=lambda kv: _model_size_score(kv[0]))
        mn, md = best
        return mn, md.get("wire_name", mn), cloud_prov
    return None


def _best_model_for_provider_task(session, provider: str, user_input: str) -> "tuple[str, str, str] | None":
    """Elige modelo dentro de un provider, prefiriendo coder para tareas de código."""
    pdata = session.providers.get(provider, {})
    models = pdata.get("models", {})
    if not models:
        return None
    try:
        from ..providers import _looks_like_local_code_task
        wants_code = _looks_like_local_code_task(user_input)
    except Exception:
        wants_code = False

    items = list(models.items())
    if wants_code:
        code_items = [
            (mn, md) for mn, md in items
            if "coder" in mn.lower()
            or "codex" in mn.lower()
            or "code" in str(md.get("best_for", "")).lower()
            or "coding" in str(md.get("best_for", "")).lower()
        ]
        if code_items:
            items = code_items

    mn, md = max(items, key=lambda kv: _model_size_score(kv[0]))
    return mn, md.get("wire_name", mn), provider


def _provider_error_fallbacks(session, user_input: str, failed_provider: str) -> list[tuple[str, str, str]]:
    """Candidatos de fallback tras auth/quota/rate-limit/conexión.

    Login, cuota y permisos son estados separados: un provider autenticado puede
    quedar degradado por billing/rate-limit y se excluye sólo para esta sesión.
    """
    active = [
        p for p in session.creds.active_bago_providers()
        if p != failed_provider and p not in getattr(session, "skip_providers", set())
    ]
    try:
        from ..providers import _looks_like_local_code_task
        local_code = _looks_like_local_code_task(user_input)
    except Exception:
        local_code = False

    if local_code:
        priority = (
            "ollama-local", "ollama-cloud", "copilot", "github-models",
            "codex", "anthropic", "gemini", "openrouter",
        )
    else:
        priority = (
            "copilot", "ollama-cloud", "ollama-local", "github-models",
            "codex", "anthropic", "gemini", "openrouter",
        )

    ordered = [p for p in priority if p in active]
    ordered.extend(p for p in active if p not in ordered)

    out: list[tuple[str, str, str]] = []
    for prov in ordered:
        candidate = _best_model_for_provider_task(session, prov, user_input)
        if candidate:
            out.append(candidate)
    return out

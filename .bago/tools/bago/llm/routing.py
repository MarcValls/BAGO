"""bago.llm.routing — Scoring de modelos, cadenas de escalado y deducción de cloud."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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




def active_providers() -> list[str]:
    """Return list of active provider names from credential manager."""
    try:
        from ..credentials import CredentialManager
        mgr = CredentialManager()
        return mgr.active_bago_providers()
    except Exception:
        return []


def _ollama_cloud_base() -> str | None:
    """Return ollama-cloud API base URL if configured."""
    return os.environ.get("OLLAMA_CLOUD_BASE", "") or None


def _ollama_cloud_key() -> str:
    """Return ollama-cloud API key if configured."""
    return os.environ.get("OLLAMA_CLOUD_KEY", "")

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
        from ..ollama_runtime import default_ollama_base_url
        chain.append((wire, {"api_base": default_ollama_base_url()}, f"ollama-local / {fallback_local}"))

    # 1b. ollama-cloud: si esta activo en providers, anadirlo
    if "ollama-cloud" in active_providers():
        cloud_model = fallback_local or missing_model
        cloud_base = _ollama_cloud_base()
        if cloud_base:
            chain.append((
                f"openai/{cloud_model}",
                {"api_base": cloud_base, "api_key": _ollama_cloud_key()},
                f"ollama-cloud / {cloud_model}",
            ))

    # 2. copilot: GitHub Models
    gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    if not gh_token:
        try:
            import subprocess as _sp
            gh_token = _sp.check_output(["gh", "auth", "token"], text=True, stderr=_sp.DEVNULL).strip()
        except Exception:
            gh_token = ""
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
    "replicate": (
        "run","execute","deploy","inference","open-source","oss","modelo",
        "llama","mistral","stable","flux","whisper",
    ),
}



def _cloud_priority_order(history: list, user_input: str, active: list) -> list[str]:
    """Devuelve lista ordenada de providers cloud, mejor task-fit primero.
    Incluye TODOS los providers activos, no solo los hardcodeados."""
    ctx_msgs = [m["content"] for m in history if m.get("role") == "user"][-4:]
    ctx = " ".join(ctx_msgs + [user_input]).lower()
    scores: dict[str, int] = {p: 0 for p in _TASK_CLOUD_HINTS}
    for prov, keywords in _TASK_CLOUD_HINTS.items():
        scores[prov] = sum(1 for kw in keywords if kw in ctx)
    # Base order: known good defaults, then task-scored
    base_order = ("codex", "copilot", "anthropic", "gemini", "replicate",
                  "deepseek", "groq", "mistral", "together", "xai",
                  "perplexity", "cohere", "huggingface", "openrouter")
    # Sort by task-fit score first, then by base order
    scored_known = sorted(base_order, key=lambda p: -scores.get(p, 0))
    result = [p for p in scored_known if p in active]
    # Append any active providers not in base_order (new/future providers)
    for p in active:
        if p not in result and p not in ("ollama-local", "ollama-cloud", "opencode"):
            result.append(p)
    return result


def _deduce_cloud_provider(history: list, user_input: str, active: list) -> str:
    """Deduce el mejor provider cloud para la tarea. Usa _cloud_priority_order."""
    order = _cloud_priority_order(history, user_input, active)
    if order:
        return order[0]
    for prov in active:
        if prov not in ("ollama-local", "ollama-cloud", "opencode"):
            return prov
    return "copilot"


def _escalate_model(session, user_input: str = "") -> "tuple[str, str, str] | None":
    """Compat: devuelve el primer candidato de _escalate_candidates."""
    cands = _escalate_candidates(session, user_input)
    return cands[0] if cands else None


def _escalate_candidates(session, user_input: str = "") -> list[tuple[str, str, str]]:
    """Escalado por saturacion de contexto o calidad.

    Devuelve lista ordenada de candidatos (model_name, wire_name, provider).
    Itera TODOS los providers activos, no solo el primero.
    """
    cur_score = _model_size_score(session.model_name)
    active    = [p for p in session.creds.active_bago_providers()
                 if p not in getattr(session, "skip_providers", set())]
    local_provs = ("ollama-local", "ollama-cloud")
    candidates: list[tuple[str, str, str]] = []

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
            candidates.append((mn, wn, p))
        elif pn != session.provider:
            r = _any_model_in(pn)
            if r:
                candidates.append(r)

    # Fase 2: TODOS los clouds activos, ordenados por task-fit
    cloud_order = _cloud_priority_order(session.history, user_input, active)
    for prov in cloud_order:
        prov_data = session.providers.get(prov, {})
        models = prov_data.get("models", {})
        if models:
            best = max(models.items(), key=lambda kv: _model_size_score(kv[0]))
            mn, md = best
            candidates.append((mn, md.get("wire_name", mn), prov))

    return candidates


def _cloud_escalation_for_quality(session, user_input: str) -> "tuple[str, str, str] | None":
    """Compat: devuelve el primer candidato de cloud_escalation_candidates."""
    cands = _cloud_escalation_candidates(session, user_input)
    return cands[0] if cands else None


def _cloud_escalation_candidates(session, user_input: str) -> list[tuple[str, str, str]]:
    """Encuentra TODOS los providers cloud para escalar por fallo de calidad o URL.

    Prioriza cualquier cloud activo sobre Ollama.
    Retorna lista ordenada de (model_name, wire_name, provider).
    """
    active = [p for p in session.creds.active_bago_providers()
              if p not in getattr(session, "skip_providers", set())]
    cloud_order = _cloud_priority_order(session.history, user_input, active)
    # Incluir tambien locales como ultimo recurso
    local_fallback = [p for p in ("ollama-local", "ollama-cloud") if p in active and p not in cloud_order]
    all_provs = cloud_order + local_fallback
    candidates: list[tuple[str, str, str]] = []
    for prov in all_provs:
        prov_data = session.providers.get(prov, {})
        models = prov_data.get("models", {})
        if models:
            best = max(models.items(), key=lambda kv: _model_size_score(kv[0]))
            mn, md = best
            candidates.append((mn, md.get("wire_name", mn), prov))
    return candidates


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


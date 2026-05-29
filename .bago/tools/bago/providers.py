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
import os

from .codex_auth import resolve_openai_credential, resolve_openai_credentials
from .constants import PROVIDERS_FILE, ROUTING_FILE
from .model_availability import (
    available_model_items as _available_model_items,
    available_model_routes as _available_model_routes,
    rough_model_size_score as _rough_model_size_score,
)
from .ollama_runtime import discover_ollama_url, ollama_probe, ollama_pull
from .provider_health import scan_provider_health
from .provider_scan_history import update_scan_history
from .provider_state import disabled_provider_ids
from .ollama_models import ensure_ollama_models_env

ensure_ollama_models_env()


def load_providers():
    try:
        providers = json.loads(PROVIDERS_FILE.read_text(encoding="utf-8-sig"))["providers"]
    except Exception:
        return {}
    disabled = disabled_provider_ids()
    return {
        name: data
        for name, data in providers.items()
        if name.lower().replace("_", "-") not in disabled
    }


def load_routing():
    try:
        return json.loads(ROUTING_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"rules": [], "fallback": {"provider": "codex", "model": "gpt-5.4-mini"}}


_PROVIDER_ALIASES = {
    "local": "ollama-local",
    "ollama": "ollama-local",
    "ollama_local": "ollama-local",
    "ollama-cloud": "ollama-cloud",
    "ollama_cloud": "ollama-cloud",
    "openai": "codex",
    "gpt": "codex",
    "github": "copilot",
    "github-models": "github-models",
}

_LOCAL_CODE_KEYWORDS = (
    "codigo", "código", "code", "script", "funcion", "función", "function",
    "clase", "class", "refactor", "debug", "bug", "error", "traceback",
    "test", "tests", "pytest", "edita", "editar", "modifica", "modificar",
    "implementa", "implementar", "implement", "shell", "repo", "archivo",
    "pipeline",
)

_CLOUD_REQUIRED_KEYWORDS = (
    "repo completo", "contexto masivo", "bago completo", "long context",
    "auditoria", "auditoría", "security", "seguridad", "vulnerabilidad",
    "pr", "pull request", "code review", "review",
)


def _normalize_provider_name(provider) -> str:
    raw = (provider or "").strip()
    return _PROVIDER_ALIASES.get(raw, raw)


def _looks_like_local_code_task(text: str) -> bool:
    tl = text.lower()
    if any(k in tl for k in _CLOUD_REQUIRED_KEYWORDS):
        return False
    return any(k in tl for k in _LOCAL_CODE_KEYWORDS)


# Selección estable: primero la preferencia explícita, luego capacidad y al final nombre.
_CODEX_PREFERRED_MODELS = (
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.3-codex",
    "gpt-5.5",
    "gpt-5.2",
    "gpt-5.3",
    "gpt-5.2-codex",
    "gpt-5-mini",
    "gpt-5.1",
)


def _model_sort_key(
    name: str,
    meta: dict | None = None,
    *,
    preferred: tuple[str, ...] = (),
    prefer_code: bool = True,
):
    meta = meta if isinstance(meta, dict) else {}
    wire = str(meta.get("wire_name", name))
    best_for = str(meta.get("best_for", "")).lower()
    lower_name = name.lower()
    lower_wire = wire.lower()
    preferred_index = next(
        (
            idx
            for idx, candidate in enumerate(preferred)
            if candidate == name
            or candidate == lower_name
            or candidate == wire
            or candidate == lower_wire
        ),
        None,
    )
    if preferred_index is not None:
        return (0, preferred_index, -_rough_model_size_score(name), lower_name, lower_wire)
    code_bonus = 1 if prefer_code and ("coder" in lower_name or "code" in lower_wire or "code" in best_for) else 0
    return (1, -code_bonus, -_rough_model_size_score(name), lower_name, lower_wire)


def _select_best_model(models: dict, *, preferred: tuple[str, ...] = (), prefer_code: bool = True):
    if not models:
        return None
    return min(
        models.items(),
        key=lambda item: _model_sort_key(
            item[0],
            item[1],
            preferred=preferred,
            prefer_code=prefer_code,
        ),
    )


def _best_ollama_coder(providers: dict) -> "tuple[str, str, str] | None":
    for prov in ("ollama-local", "ollama-cloud"):
        models = dict(_available_model_items(prov, providers.get(prov, {})))
        if not models:
            continue
        coder = {
            mn: md
            for mn, md in models.items()
            if "coder" in mn.lower() or "code" in str(md.get("best_for", "")).lower()
        }
        selected = _select_best_model(coder) if coder else _select_best_model(models)
        if not selected:
            continue
        mn, md = selected
        return mn, md.get("wire_name", mn), prov
    return None


def route_by_task(task, routing, providers, current_provider=None):
    tl = task.lower()
    best_rule = None
    best_hits = 0
    best_kw = None
    for rule in routing.get("rules", []):
        hits = sum(1 for kw in rule.get("keywords", []) if kw.lower() in tl)
        if hits > best_hits:
            best_hits = hits
            best_rule = rule
            best_kw = next((kw for kw in rule.get("keywords", []) if kw.lower() in tl), None)

    if best_rule:
        if _looks_like_local_code_task(task):
            local = _best_ollama_coder(providers)
            if local:
                return local[0], local[1], local[2], best_kw
        prov = _normalize_provider_name(best_rule["provider"])
        if prov not in providers:
            local = _best_ollama_coder(providers)
            if local:
                return local[0], local[1], local[2], best_kw
        model = best_rule["model"]
        available = dict(_available_model_items(prov, providers.get(prov, {})))
        if model not in available and prov == "ollama-local":
            local = _best_ollama_coder(providers)
            if local:
                return local[0], local[1], local[2], best_kw
        wire = available.get(model, providers.get(prov, {}).get("models", {}).get(model, {})).get("wire_name", model)
        return model, wire, prov, best_kw

    current_provider = _normalize_provider_name(current_provider)
    if current_provider in ("ollama-local", "ollama-cloud"):
        best = best_model_for_provider(current_provider, providers)
        if best:
            return best[0], best[1], current_provider, None
    if _looks_like_local_code_task(task):
        local = _best_ollama_coder(providers)
        if local:
            return local[0], local[1], local[2], None

    fb = routing.get("fallback", {"provider": "ollama-local", "model": "qwen25-mini"})
    fb_provider = _normalize_provider_name(fb.get("provider", "ollama-local"))
    fb_model = fb.get("model", "qwen25-mini")
    fb_models = dict(_available_model_items(fb_provider, providers.get(fb_provider, {})))
    if fb_model not in fb_models and fb_provider == "ollama-local":
        local = _best_ollama_coder(providers)
        if local:
            return local[0], local[1], local[2], None
    fb_wire = fb_models.get(fb_model, providers.get(fb_provider, {}).get("models", {}).get(fb_model, {})).get("wire_name", fb_model)
    return fb_model, fb_wire, fb_provider, None


def detect_strategy(text, active_providers):
    if len(active_providers) < 2:
        return "single", []

    tl = text.lower()
    if _looks_like_local_code_task(text):
        preferred = ("ollama-local", "ollama-cloud", "copilot", "codex", "anthropic")
        ordered = [p for p in preferred if p in active_providers]
        ordered.extend(p for p in active_providers if p not in ordered)
        active_providers = ordered

    creates = any(w in tl for w in [
        "escrib", "crea", "genera", "implementa", "construye",
        "diseña", "haz ", "build", "write", "create", "code", "codigo",
    ])
    reviews = any(w in tl for w in [
        "explica", "comenta", "documenta", "revisa", "mejora",
        "optimiza", "explain", "review", "improve", "refactor",
        "y luego", "despues", "tras", "then",
    ])
    code_ctx = any(w in tl for w in [
        "codigo", "code", "funcion", "function", "clase", "class",
        "script", "api", "test", "algoritmo", "algorithm",
    ])
    opinions = any(w in tl for w in [
        "mejor forma", "mejor manera", "best way", "recomiend",
        "que opinas", "opinion", "pros y contras", "ventajas",
        "desventajas", "compara", "versus", " vs ", "alternativa",
        "cual es mejor", "debate", "perspectiva", "enfoque",
    ])

    if creates and (reviews or (code_ctx and reviews)):
        return "chain", active_providers[:2]
    if opinions:
        return "ensemble", active_providers[:min(3, len(active_providers))]
    if len(text) > 300 and creates:
        return "chain", active_providers[:2]
    return "single", []


def get_default_model(provider_name, providers):
    prov = providers.get(provider_name, {})
    models = dict(_available_model_items(provider_name, prov))
    if not models:
        return "", "", provider_name
    if provider_name == "ollama-local":
        preferred = (
            "llama3.2:1b",
            "qwen2.5:1.5b",
            "phi3:mini",
            "smollm2:1.7b",
            "qwen2.5:0.5b",
            "llama3.2:3b",
            "llama3.2:latest",
            "qwen2.5-coder:7b",
            "deepseek-coder:6.7b",
            "granite3.2:8b",
        )
    else:
        preferred = _CODEX_PREFERRED_MODELS if provider_name in ("codex", "openai") else ()
    selected = _select_best_model(models, preferred=preferred)
    if not selected:
        return "", "", provider_name
    name, meta = selected
    return name, meta.get("wire_name", name), provider_name


def best_model_for_provider(prov_name, providers):
    name, wire, prov = get_default_model(prov_name, providers)
    return (name, wire, prov) if name else None


def describe_model_source(
    provider_name: str,
    model_name: str,
    providers: dict,
    wire_name: str | None = None,
    *,
    route: str | None = None,
    service: str | None = None,
) -> dict:
    """Return the richest known origin metadata for a provider/model pair."""
    prov_data = providers.get(provider_name, {})
    target_wire = wire_name or model_name
    def _default_service() -> str:
        if provider_name in ("codex", "openai"):
            if route == "openai-api" or service == "openai-api":
                return "openai-api"
            return "codex-cli"
        if provider_name == "ollama-local":
            return "ollama-native"
        if provider_name == "ollama-cloud":
            return "ollama-cloud-api"
        return f"{provider_name}-api"

    for rec in _available_model_routes(provider_name, prov_data):
        if route and rec.get("route") != route:
            continue
        if service and rec.get("service") != service:
            continue
        if rec.get("model") == model_name or rec.get("wire_name") == target_wire:
            return dict(rec)
    for mn, md in _available_model_items(provider_name, prov_data):
        if mn == model_name or md.get("wire_name", mn) == target_wire:
            resolved_service = md.get("service") or _default_service()
            resolved_route = route or md.get("route") or service or resolved_service or provider_name
            return {
                "provider": provider_name,
                "model": mn,
                "wire_name": md.get("wire_name", mn),
                "service": service or resolved_service,
                "route": resolved_route,
                "backend": md.get("backend", "litellm"),
                "available": md.get("available", True),
                "best_for": md.get("best_for", ""),
                "cost": md.get("cost", ""),
            }
    resolved_service = service or _default_service()
    return {
        "provider": provider_name,
        "model": model_name,
        "wire_name": target_wire,
        "service": resolved_service,
        "route": route or service or provider_name,
        "backend": "litellm",
        "available": False,
    }


_COPILOT_MODEL_MAP = {
    "claude-sonnet-4.6": "gpt-4o",
    "claude-sonnet-4.5": "gpt-4o",
    "claude-opus-4.7": "gpt-4o",
    "claude-opus-4.5": "gpt-4o",
    "claude-3-5-sonnet": "gpt-4o",
    "claude-3-opus": "gpt-4o",
    "claude-3-haiku": "gpt-4o-mini",
}

_CODEX_MODEL_MAP = {
    "gpt-5.5": "gpt-4o",
    "gpt-5.4": "gpt-4o",
    "gpt-5.3-codex": "gpt-4o",
    "gpt-5.3": "gpt-4o",
    "gpt-5.2-codex": "gpt-4o",
    "gpt-5.2": "gpt-4o-mini",
    "gpt-5.4-mini": "gpt-4o-mini",
    "gpt-5-mini": "gpt-4o-mini",
    "gpt-5.1": "gpt-4o-mini",
}


def _is_valid_api_key(key: str) -> bool:
    key = key.strip()
    if len(key) < 8:
        return False
    obvious = {"ollama", "none", "null", "undefined", "false", "test", "demo", "placeholder"}
    return key.lower() not in obvious


def resolve_codex_route_candidates(wire_name: str, *, allow_api_fallback: bool = True) -> list[dict]:
    """Return ordered execution routes for codex/openai models."""
    creds = resolve_openai_credentials()
    oauth_token = creds.get("oauth_token")
    api_key = creds.get("api_key", "")
    if not oauth_token:
        return []

    candidates: list[dict] = []
    try:
        from .codex_runtime import codex_cli_available
    except Exception:
        def codex_cli_available() -> bool:  # type: ignore[redef]
            return False

    if codex_cli_available():
        candidates.append({
            "provider": "codex",
            "model": wire_name,
            "wire_name": wire_name,
            "service": "codex-cli",
            "route": "codex-cli",
            "backend": "codex-cli",
            "available": True,
            "auth_mode": "oauth",
            "lm": wire_name,
            "kw": {},
        })

    if allow_api_fallback and api_key and _is_valid_api_key(api_key):
        candidates.append({
            "provider": "codex",
            "model": wire_name,
            "wire_name": wire_name,
            "service": "openai-api",
            "route": "openai-api",
            "backend": "litellm",
            "available": True,
            "auth_mode": "api_key",
            "fallback": True,
            "lm": wire_name,
            "kw": {"api_key": api_key},
        })

    return candidates


def resolve_litellm(provider, wire_name):
    provider = _normalize_provider_name(provider)
    if provider == "ollama-local":
        from .ollama_runtime import default_ollama_base_url
        return f"ollama/{wire_name}", {"api_base": os.environ.get("OLLAMA_HOST") or default_ollama_base_url()}
    if provider == "ollama-cloud":
        providers = load_providers()
        pdata = providers.get("ollama-cloud", {})
        api_base = (
            os.environ.get("OLLAMA_CLOUD_BASE_URL")
            or pdata.get("base_url")
            or "https://api.ollama.com"
        )
        api_key = os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get("OLLAMA_API_KEY", "")
        kw = {"api_base": api_base}
        if api_key:
            kw["api_key"] = api_key
        return f"ollama/{wire_name}", kw
    if provider == "copilot":
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if not token:
            try:
                from .credentials import CredentialManager
                token = CredentialManager()._creds.get("github", "")
            except Exception:
                pass
        if token and _is_valid_api_key(token):
            mapped = _COPILOT_MODEL_MAP.get(wire_name, wire_name)
            return f"openai/{mapped}", {
                "api_base": "https://models.inference.ai.azure.com",
                "api_key": token,
            }
        return wire_name, {}
    if provider == "github-models":
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if not token:
            try:
                from .credentials import CredentialManager
                token = CredentialManager()._creds.get("github", "")
            except Exception:
                pass
        if token and _is_valid_api_key(token):
            # GitHub Models usa el endpoint models.github.ai/inference
            return f"openai/{wire_name}", {
                "api_base": "https://models.github.ai/inference",
                "api_key": token,
            }
        return wire_name, {}
    if provider == "replicate":
        api_key = os.environ.get("REPLICATE_API_TOKEN", "")
        if not api_key:
            try:
                from .credentials import CredentialManager
                api_key = CredentialManager()._creds.get("replicate", "")
            except Exception:
                pass
        if api_key and _is_valid_api_key(api_key):
            return f"replicate/{wire_name}", {"api_key": api_key}
        return wire_name, {}
    if provider in ("codex", "openai"):
        credential, _mode = resolve_openai_credential()
        if credential:
            return wire_name, {"api_key": credential}
        gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if gh_token:
            safe = "gpt-4o-mini" if "mini" in wire_name else "gpt-4o"
            return f"openai/{safe}", {
                "api_base": "https://models.inference.ai.azure.com",
                "api_key": gh_token,
            }
        return wire_name, {}

    providers_data = load_providers()
    pdata = providers_data.get(provider, {})
    api_base = pdata.get("base_url") or pdata.get("base_url_v1")
    env_key = pdata.get("auth", "")
    api_key = ""
    if env_key.startswith("api_key_env:"):
        env_name = env_key[len("api_key_env:"):]
        api_key = os.environ.get(env_name, "")
        if not api_key:
            try:
                from .credentials import CredentialManager
                cred_val = CredentialManager()._creds.get(provider, "")
                if isinstance(cred_val, str) and _is_valid_api_key(cred_val):
                    api_key = cred_val
            except Exception:
                pass
    if api_key and _is_valid_api_key(api_key):
        kw = {}
        if api_base:
            kw["api_base"] = api_base
        kw["api_key"] = api_key
        return wire_name, kw
    return wire_name, {}


def auto_detect_provider(creds, providers):
    active = creds.active_bago_providers()
    for preferred in ("ollama-local", "copilot", "github-models", "codex", "anthropic", "ollama-cloud"):
        if preferred in active and preferred in providers:
            return preferred
    return next((name for name in providers if name in active), "none")


KNOWN_PROVIDERS_CATALOG: dict[str, dict] = {
    "ollama-local": {
        "label": "Ollama (local)",
        "description": "Modelos LLM privados en tu máquina — sin coste, sin internet",
        "setup": "Descarga desde https://ollama.com y ejecuta `ollama pull <modelo>`",
        "requires": "Ollama instalado + al menos un modelo descargado",
        "type": "local",
    },
    "ollama-cloud": {
        "label": "Ollama (remoto)",
        "description": "Ollama Cloud o un servidor Ollama remoto",
        "setup": "Configura OLLAMA_CLOUD_API_KEY/OLLAMA_API_KEY o OLLAMA_CLOUD_BASE_URL",
        "requires": "API key de Ollama Cloud o URL remota compatible",
        "type": "local",
    },
    "copilot": {
        "label": "GitHub Copilot",
        "description": "Code completion y chat IA en el IDE — requiere suscripcion Copilot activa",
        "setup": "Activa GitHub Copilot en github.com/settings/copilot + `gh auth login`",
        "requires": "Suscripcion GitHub Copilot (Free/Pro/Business) + GITHUB_TOKEN",
        "type": "cloud",
    },
    "github-models": {
        "label": "GitHub Models",
        "description": "GPT-4.1, Llama 3, Mistral, DeepSeek y mas — gratis con rate limit",
        "setup": "Solo necesitas `gh auth login`",
        "requires": "GITHUB_TOKEN o GH_TOKEN",
        "type": "cloud",
        "endpoint": "https://models.github.ai/inference",
        "catalog": "https://models.github.ai/catalog/models",
        "openai_compat": True,
    },
    "codex": {
        "label": "OpenAI / Codex CLI",
        "description": "GPT-4o / GPT-5.x via codex login",
        "setup": "npm i -g @openai/codex && codex login",
        "requires": "codex CLI autenticado",
        "type": "cloud",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "description": "Claude 3.5 Sonnet, Claude Opus — razonamiento avanzado",
        "setup": "Obtén API key en https://console.anthropic.com",
        "requires": "ANTHROPIC_API_KEY",
        "type": "cloud",
    },
    "gemini": {
        "label": "Google Gemini",
        "description": "Gemini 2.0 Flash, Gemini 1.5 Pro — multimodal, contexto largo",
        "setup": "Obtén API key gratuita en https://aistudio.google.com/app/apikey",
        "requires": "GEMINI_API_KEY",
        "type": "cloud",
    },
    "openrouter": {
        "label": "OpenRouter",
        "description": "Acceso unificado a 200+ modelos",
        "setup": "Obtén API key gratuita en https://openrouter.ai",
        "requires": "OPENROUTER_API_KEY",
        "type": "cloud",
    },
}

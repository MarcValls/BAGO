"""Canonical provider descriptors shared by API handlers and UI payloads.

Runtime registration remains authoritative for availability.  This catalogue
only describes stable identity, configuration and model-discovery contracts.

Cloud-provider endpoint policy: providers whose canonical descriptor carries a
fixed cloud URL are bound to that origin.  Callers cannot point them at an
arbitrary URL, even with a valid stored secret, because that would let a
compromised UI or persisted config redirect credentials.  Custom or local
endpoints must use the dedicated local/custom provider surface
(e.g. ``ollama-local``, ``opencode`` or ``custom-openai-compatible``).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "ollama-local": {
        "description": "Ollama local (CPU/GPU)",
        "icon": "local",
        "runtime": "local",
        "protocol": "ollama",
        "auth_kind": "none",
        "base_url": "http://localhost:11434",
        "model_discovery": {"type": "ollama_tags", "path": "/api/tags"},
    },
    "ollama-cloud": {
        "description": "Ollama Cloud",
        "icon": "cloud",
        "runtime": "cloud",
        "protocol": "openai-compatible",
        "auth_kind": "api-key",
        "base_url": "https://ollama.com",
        "model_discovery": {"type": "ollama_tags", "path": "/api/tags"},
    },
    "anthropic": {
        "description": "Anthropic Claude (API key)",
        "icon": "cloud",
        "runtime": "cloud",
        "protocol": "anthropic",
        "auth_kind": "api-key",
        "base_url": "https://api.anthropic.com",
        "model_discovery": {"type": "manual"},
    },
    "openai": {
        "description": "OpenAI GPT (API key)",
        "icon": "cloud",
        "runtime": "cloud",
        "protocol": "openai",
        "auth_kind": "api-key",
        "base_url": "https://api.openai.com/v1",
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "copilot": {
        "description": "GitHub Copilot CLI",
        "icon": "cloud",
        "runtime": "delegated-cli",
        "protocol": "openai-compatible",
        "auth_kind": "delegated",
        "base_url": "https://api.githubcopilot.com",
        "aliases": ["github-copilot-cli", "github-copilot-oauth"],
        "model_discovery": {"type": "manual"},
    },
    "codex": {
        "description": "OpenAI Codex CLI",
        "icon": "cloud",
        "runtime": "delegated-cli",
        "protocol": "openai",
        "auth_kind": "delegated",
        "base_url": "https://api.openai.com/v1",
        "model_discovery": {"type": "manual"},
    },
    "openrouter": {
        "description": "OpenRouter (API key)",
        "icon": "cloud",
        "runtime": "cloud",
        "protocol": "openai-compatible",
        "auth_kind": "api-key",
        "base_url": "https://openrouter.ai/api/v1",
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "opencode": {
        "description": "OpenCode (local server)",
        "icon": "local",
        "runtime": "local",
        "protocol": "openai-compatible",
        "auth_kind": "optional",
        "base_url": "",
        "model_discovery": {"type": "manual"},
    },
    "cpp-local": {
        "description": "llama.cpp local server",
        "icon": "local",
        "runtime": "local",
        "protocol": "openai-compatible",
        "auth_kind": "none",
        "base_url": "http://localhost:8080/v1",
        "aliases": ["llama-cpp-local"],
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "google-gemini": {
        "description": "Google Gemini",
        "icon": "cloud",
        "runtime": "cloud",
        "protocol": "gemini",
        "auth_kind": "api-key",
        "base_url": "https://generativelanguage.googleapis.com",
        "model_discovery": {"type": "manual"},
    },
    "vertex-ai": {"model_discovery": {"type": "manual"}},
    "azure-openai": {"model_discovery": {"type": "manual"}},
    "aws-bedrock": {"model_discovery": {"type": "manual"}},
    "huggingface": {
        "base_url": "https://router.huggingface.co/v1",
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model_discovery": {"type": "manual"},
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "vllm-local": {
        "base_url": "http://localhost:8000/v1",
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
    "custom-openai-compatible": {
        "model_discovery": {"type": "openai_models", "path": "/models"},
    },
}


def canonical_provider_id(provider_id: str) -> str:
    clean = str(provider_id or "").strip().lower()
    if clean in PROVIDER_CATALOG:
        return clean
    for canonical, descriptor in PROVIDER_CATALOG.items():
        if clean in descriptor.get("aliases", []):
            return canonical
    return clean


def provider_descriptor(provider_id: str) -> dict[str, Any]:
    canonical = canonical_provider_id(provider_id)
    descriptor = dict(PROVIDER_CATALOG.get(canonical, {}))
    descriptor["canonical_id"] = canonical
    descriptor.setdefault("description", provider_id)
    descriptor.setdefault("icon", "cloud")
    descriptor.setdefault("runtime", "cloud")
    descriptor.setdefault("protocol", "openai-compatible")
    descriptor.setdefault("auth_kind", "api-key")
    descriptor.setdefault("base_url", "")
    descriptor.setdefault("aliases", [])
    descriptor.setdefault("model_discovery", {"type": "manual"})
    return descriptor


def normalize_provider_base_url(provider_id: str, value: Any) -> str:
    """Return the URL shape expected by each runtime adapter."""
    url = str(value or "").strip().rstrip("/")
    if canonical_provider_id(provider_id) in {"ollama-local", "ollama-cloud"}:
        if url.lower().endswith("/api"):
            url = url[:-4].rstrip("/")
    return url


def provider_base_url(provider_id: str, config: dict[str, Any]) -> str:
    providers = config.get("providers", {}) if isinstance(config, dict) else {}
    configured = providers.get(provider_id, {}) if isinstance(providers, dict) else {}
    url = configured.get("base_url", "") if isinstance(configured, dict) else ""
    fallback = provider_descriptor(provider_id).get("base_url", "")
    return normalize_provider_base_url(provider_id, url or fallback)


def provider_canonical_base_url(provider_id: str) -> str:
    """Return the fixed canonical cloud URL from the provider descriptor."""
    return str(provider_descriptor(provider_id).get("base_url", "") or "").strip()


#: Providers whose descriptor carries a fixed, server-owned cloud endpoint.
#: Any supplied ``base_url`` must canonicalise to this exact origin+path.
_FIXED_CLOUD_URL_PROVIDERS: frozenset[str] = frozenset({
    "ollama-cloud",
    "anthropic",
    "openai",
    "copilot",
    "codex",
    "openrouter",
    "google-gemini",
    "huggingface",
    "mistral",
    "groq",
    "deepseek",
    "xai",
})


def is_fixed_cloud_provider(provider_id: str) -> bool:
    """Return True when the provider descriptor fixes a single cloud URL."""
    return canonical_provider_id(provider_id) in _FIXED_CLOUD_URL_PROVIDERS


def _effective_port(parsed) -> int:
    """Return the explicit or default port for a parsed URL."""
    if parsed.port is not None:
        return int(parsed.port)
    if parsed.scheme.lower() == "https":
        return 443
    if parsed.scheme.lower() == "http":
        return 80
    return 0


def canonical_url_matches(url: str, canonical_url: str) -> bool:
    """Compare two URLs for scheme, host (case-insensitive), effective port and path.

    Trailing slashes are ignored.  Empty URLs never match a non-empty canonical.
    """
    try:
        a = urlparse(str(url or "").strip().rstrip("/"))
        b = urlparse(str(canonical_url or "").strip().rstrip("/"))
        if not b.scheme or not b.hostname:
            return False
        if a.username or a.password or a.query or a.fragment or a.params:
            return False
        if a.scheme.lower() != b.scheme.lower():
            return False
        if (a.hostname or "").lower() != (b.hostname or "").lower():
            return False
        if _effective_port(a) != _effective_port(b):
            return False
        return a.path.rstrip("/") == b.path.rstrip("/")
    except ValueError:
        # Malformed IPv6/ports are untrusted inputs, not handler exceptions.
        return False


def validate_provider_endpoint(provider_id: str, base_url: str) -> tuple[bool, str]:
    """Validate ``base_url`` for named cloud providers against their fixed URL.

    Returns ``(True, "")`` when the provider is not a fixed-cloud provider or
    when the URL matches the canonical descriptor.  Local and custom providers
    are intentionally unrestricted.
    """
    canonical = provider_canonical_base_url(provider_id)
    if not canonical or not is_fixed_cloud_provider(provider_id):
        return True, ""
    normalized = normalize_provider_base_url(provider_id, base_url)
    if canonical_url_matches(normalized, canonical):
        return True, ""
    return False, "provider_endpoint_canonical_mismatch"


def provider_discovery(provider_id: str) -> dict[str, str]:
    value = provider_descriptor(provider_id).get("model_discovery", {"type": "manual"})
    return dict(value) if isinstance(value, dict) else {"type": "manual"}

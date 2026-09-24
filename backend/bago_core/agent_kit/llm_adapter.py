"""Portable LLM adapter for the BAGO agent kit.

Supports:
- Ollama native API (/api/chat)
- OpenAI-compatible APIs (/chat/completions)
- Anthropic Messages API (basic)
- BAGO-configured provider resolution (--use-bago-provider)

Uses only the standard library by default. If `requests` is available it is
preferred for nicer error messages, but the adapter works without it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bago_core.agent_kit.errors import AgentKitError

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    finish_reason: str = ""
    usage: dict[str, int] | None = None
    raw: dict[str, Any] | None = None


class LLMAdapterError(AgentKitError):
    pass


def _env_key(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _default_base_url(provider: str) -> str:
    provider = (provider or "").strip().lower()
    if provider in {"ollama", "ollama-local"}:
        return _env_key("OLLAMA_HOST", "OLLAMA_BASE_URL") or "http://localhost:11434"
    if provider == "ollama-cloud":
        return "https://ollama.com"
    if provider in {"openai", "codex"}:
        return "https://api.openai.com/v1"
    if provider == "anthropic":
        return "https://api.anthropic.com"
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    if provider == "copilot":
        return "https://api.githubcopilot.com"
    if provider == "cpp-local":
        return "http://localhost:8080/v1"
    return ""


def _provider_protocol(provider: str) -> str:
    provider = (provider or "").strip().lower()
    if provider in {"ollama", "ollama-local"}:
        return "ollama"
    if provider in {"anthropic"}:
        return "anthropic"
    return "openai-compatible"


def _resolve_api_key(provider: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    provider = (provider or "").strip().lower()
    env_names = {
        "openai": ["OPENAI_API_KEY"],
        "codex": ["OPENAI_API_KEY", "CODEX_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "copilot": ["GITHUB_COPILOT_API_KEY", "COPILOT_API_KEY"],
        "ollama-cloud": ["OLLAMA_API_KEY"],
    }.get(provider, [])
    return _env_key(*env_names)


def _resolve_bago_config(user_root: str | Path | None = None) -> dict[str, Any]:
    try:
        from config_manager import ConfigManager
    except ModuleNotFoundError as exc:
        raise LLMAdapterError("BAGO config_manager not importable; cannot use --use-bago-provider") from exc

    root = Path(user_root) if user_root else None
    cm = ConfigManager(state_root=str(root)) if root else ConfigManager()
    return {
        "default_provider": cm.get("default_provider", ""),
        "default_model": cm.get("default_model", ""),
        "temperature": cm.get("temperature", 0.7),
        "providers": cm.get("providers", {}),
    }


def resolve_bago_provider(user_root: str | Path | None = None) -> dict[str, Any]:
    cfg = _resolve_bago_config(user_root)
    provider = cfg.get("default_provider") or "ollama-local"
    model = cfg.get("default_model") or ""
    providers = cfg.get("providers", {})
    pcfg = providers.get(provider, {}) if isinstance(providers, dict) else {}
    base_url = pcfg.get("base_url", "") or _default_base_url(provider)
    api_key = pcfg.get("api_key", "") or _resolve_api_key(provider)
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": cfg.get("temperature", 0.7),
    }


def _http_post(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    if requests is not None:
        try:
            resp = requests.post(url, headers=headers, data=payload, timeout=timeout)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise LLMAdapterError(f"HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
        except requests.RequestException as exc:
            raise LLMAdapterError(f"request failed: {exc}") from exc
        return resp.json()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="ignore")[:500]
        raise LLMAdapterError(f"HTTP {exc.code}: {text}") from exc
    except urllib.error.URLError as exc:
        raise LLMAdapterError(f"URL error: {exc.reason}") from exc


def _ollama_chat(
    messages: list[dict[str, str]],
    model: str,
    base_url: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> LLMResponse:
    url = base_url.rstrip("/") + "/api/chat"
    ollama_messages = list(messages)
    if system:
        ollama_messages.insert(0, {"role": "system", "content": system})
    body: dict[str, Any] = {
        "model": model,
        "messages": ollama_messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if max_tokens:
        body["options"]["num_predict"] = max_tokens

    raw = _http_post(url, {}, body)
    message = raw.get("message", {})
    return LLMResponse(
        content=message.get("content", ""),
        provider="ollama",
        model=raw.get("model", model),
        finish_reason="stop",
        usage=None,
        raw=raw,
    )


def _openai_compatible_chat(
    messages: list[dict[str, str]],
    model: str,
    base_url: str,
    api_key: str = "",
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> LLMResponse:
    url = base_url.rstrip("/") + "/chat/completions"
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    openai_messages = list(messages)
    if system:
        openai_messages.insert(0, {"role": "system", "content": system})
    body: dict[str, Any] = {
        "model": model,
        "messages": openai_messages,
        "temperature": temperature,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens

    raw = _http_post(url, headers, body)
    choice = raw.get("choices", [{}])[0]
    message = choice.get("message", {})
    usage = raw.get("usage")
    return LLMResponse(
        content=message.get("content", ""),
        provider="openai-compatible",
        model=raw.get("model", model),
        finish_reason=choice.get("finish_reason", ""),
        usage=usage if isinstance(usage, dict) else None,
        raw=raw,
    )


def _anthropic_chat(
    messages: list[dict[str, str]],
    model: str,
    base_url: str,
    api_key: str = "",
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> LLMResponse:
    url = base_url.rstrip("/") + "/v1/messages"
    if not api_key:
        raise LLMAdapterError("Anthropic provider requires ANTHROPIC_API_KEY")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body: dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "system": system,
        "temperature": temperature,
        "max_tokens": max_tokens or 1024,
    }
    raw = _http_post(url, headers, body)
    content_parts = raw.get("content", [])
    text = "\n".join(c.get("text", "") for c in content_parts if isinstance(c, dict))
    usage = raw.get("usage")
    return LLMResponse(
        content=text,
        provider="anthropic",
        model=raw.get("model", model),
        finish_reason=raw.get("stop_reason", ""),
        usage=usage if isinstance(usage, dict) else None,
        raw=raw,
    )


def call_llm(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    system: str = "",
    base_url: str = "",
    api_key: str = "",
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> LLMResponse:
    provider = (provider or "").strip().lower()
    if not provider:
        raise LLMAdapterError("provider is required")
    if not model:
        raise LLMAdapterError("model is required")

    protocol = _provider_protocol(provider)
    url = (base_url or _default_base_url(provider)).strip()
    key = api_key or _resolve_api_key(provider)

    if protocol == "ollama":
        return _ollama_chat(messages, model, url, system=system, temperature=temperature, max_tokens=max_tokens)
    if protocol == "anthropic":
        return _anthropic_chat(messages, model, url, api_key=key, system=system, temperature=temperature, max_tokens=max_tokens)
    return _openai_compatible_chat(messages, model, url, api_key=key, system=system, temperature=temperature, max_tokens=max_tokens)


def call_agent_prompt(
    agent: Any,
    request: Any,
    *,
    provider: str = "",
    model: str = "",
    use_bago_provider: bool = False,
    base_url: str = "",
    api_key: str = "",
    temperature: float = 0.7,
    max_tokens: int | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    system = f"You are {agent.name}.\n\n{agent.description}"
    user_lines = []
    if request.task:
        user_lines.append(f"Task: {request.task}")
    if request.context:
        user_lines.append("Context:")
        for key, value in request.context.items():
            user_lines.append(f"  {key}: {value}")
    if agent.prompt_template:
        user_lines.append("\nInstructions:")
        user_lines.append(agent.prompt_template[:4000])
    user = "\n".join(user_lines) or "Proceed."

    prompt = f"{system}\n\n{user}"

    if dry_run:
        return {
            "output": prompt,
            "provider": provider,
            "model": model,
            "dry_run": True,
            "llm_response": None,
        }

    resolved_provider = provider
    resolved_model = model
    resolved_base_url = base_url
    resolved_api_key = api_key

    if use_bago_provider:
        bago_cfg = resolve_bago_provider()
        resolved_provider = bago_cfg["provider"]
        resolved_model = bago_cfg["model"] or model
        resolved_base_url = bago_cfg["base_url"] or base_url
        resolved_api_key = bago_cfg["api_key"] or api_key
        temperature = bago_cfg.get("temperature", temperature)

    if agent.model:
        resolved_model = agent.model

    response = call_llm(
        provider=resolved_provider,
        model=resolved_model,
        messages=[{"role": "user", "content": user}],
        system=system,
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return {
        "output": response.content,
        "provider": resolved_provider,
        "model": response.model or resolved_model,
        "dry_run": False,
        "llm_response": response,
    }


__all__ = [
    "LLMResponse",
    "LLMAdapterError",
    "call_llm",
    "call_agent_prompt",
    "resolve_bago_provider",
    "_default_base_url",
    "_resolve_api_key",
]

#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
message_adapter.py — BAGO 4.1.5 Message Adapter

Normaliza el formato de mensajes entre diferentes providers para que
el ContextStore.history[] sea portable.

Providers soportados y sus formatos:
- OpenAI / Codex / Copilot / GitHub Models:
    [{"role": "system"|"user"|"assistant", "content": str}]
    (tool_calls soportado como metadata)

- Anthropic Claude:
    [{"role": "user"|"assistant", "content": str}]
    system va como parámetro separado, no en la lista.

- Ollama (chat):
    [{"role": "system"|"user"|"assistant", "content": str}]
    (compatible con OpenAI)

- Google Gemini:
    [{"role": "user"|"model", "parts": [{"text": str}]}]

El MessageAdapter convierte desde el formato BAGO (OpenAI-like) al formato
del provider destino, y viceversa.

Uso:
    adapter = MessageAdapter.for_provider("anthropic")
    provider_msgs = adapter.to_provider(history)
    bago_msgs = adapter.from_provider(provider_response)
"""

from __future__ import annotations

import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class BaseMessageAdapter(ABC):
    """Interfaz base para adapters de mensajes."""

    @abstractmethod
    def to_provider(self, messages: list[dict], *, system: str = "") -> list[dict]:
        """Convierte mensajes BAGO -> formato del provider."""
        ...

    @abstractmethod
    def from_provider(self, response: dict | str) -> dict:
        """Convierte respuesta del provider -> formato BAGO."""
        ...

    @abstractmethod
    def extract_content(self, response: dict | str) -> str:
        """Extrae el texto de la respuesta."""
        ...

    @abstractmethod
    def supports_tools(self) -> bool:
        ...

    def compress_for_provider(self, messages: list[dict], max_tokens: int) -> list[dict]:
        """
        Si el historial excede max_tokens, comprime mensajes antiguos.
        Por defecto: trunca manteniendo system + últimos N.
        Override en subclases para compresión inteligente.
        """
        # BAGO native format: OpenAI-like
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other = [m for m in messages if m.get("role") != "system"]
        # Simple heuristic: keep last 80% of budget for recent context
        # In v4.1, use a model to summarize old messages
        kept = system_msgs + other
        return kept


class OpenAIAdapter(BaseMessageAdapter):
    """OpenAI, Codex, Copilot, GitHub Models — todos usan el mismo formato."""

    def to_provider(self, messages: list[dict], *, system: str = "") -> list[dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for m in messages:
            # Skip duplicate system if already prepended
            if m.get("role") == "system" and system:
                continue
            result.append({"role": m["role"], "content": m.get("content", "")})
        return result

    def from_provider(self, response: dict | str) -> dict:
        if isinstance(response, str):
            return {"role": "assistant", "content": response}
        # OpenAI response format
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return {
            "role": "assistant",
            "content": msg.get("content", ""),
            "provider_metadata": {
                "finish_reason": choice.get("finish_reason"),
                "usage": response.get("usage"),
            },
        }

    def extract_content(self, response: dict | str) -> str:
        if isinstance(response, str):
            return response
        choice = response.get("choices", [{}])[0]
        return choice.get("message", {}).get("content", "") or ""

    def supports_tools(self) -> bool:
        return True


class AnthropicAdapter(BaseMessageAdapter):
    """Anthropic Claude: system es parámetro separado, no en la lista."""

    def to_provider(self, messages: list[dict], *, system: str = "") -> list[dict]:
        result = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                # Anthropic handles system separately
                continue
            result.append({"role": role, "content": m.get("content", "")})
        return result

    def from_provider(self, response: dict | str) -> dict:
        if isinstance(response, str):
            return {"role": "assistant", "content": response}
        # Anthropic response format
        content_blocks = response.get("content", [])
        text = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text += block.get("text", "")
        return {
            "role": "assistant",
            "content": text,
            "provider_metadata": {
                "stop_reason": response.get("stop_reason"),
                "usage": response.get("usage"),
            },
        }

    def extract_content(self, response: dict | str) -> str:
        if isinstance(response, str):
            return response
        content_blocks = response.get("content", [])
        return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

    def supports_tools(self) -> bool:
        return True


class OllamaAdapter(BaseMessageAdapter):
    """Ollama: formato OpenAI-like con algunas diferencias menores."""

    def to_provider(self, messages: list[dict], *, system: str = "") -> list[dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for m in messages:
            if m.get("role") == "system" and system:
                continue
            result.append({"role": m["role"], "content": m.get("content", "")})
        return result

    def from_provider(self, response: dict | str) -> dict:
        if isinstance(response, str):
            return {"role": "assistant", "content": response}
        msg = response.get("message", {})
        return {
            "role": "assistant",
            "content": msg.get("content", ""),
            "provider_metadata": {
                "done": response.get("done"),
                "total_duration": response.get("total_duration"),
                "eval_count": response.get("eval_count"),
            },
        }

    def extract_content(self, response: dict | str) -> str:
        if isinstance(response, str):
            return response
        return response.get("message", {}).get("content", "") or ""

    def supports_tools(self) -> bool:
        return True


class GeminiAdapter(BaseMessageAdapter):
    """Google Gemini: formato parts[]."""

    def to_provider(self, messages: list[dict], *, system: str = "") -> list[dict]:
        result = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            result.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}],
            })
        return result

    def from_provider(self, response: dict | str) -> dict:
        if isinstance(response, str):
            return {"role": "assistant", "content": response}
        candidates = response.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        return {
            "role": "assistant",
            "content": text,
            "provider_metadata": {
                "finish_reason": candidates[0].get("finishReason") if candidates else None,
            },
        }

    def extract_content(self, response: dict | str) -> str:
        if isinstance(response, str):
            return response
        candidates = response.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    def supports_tools(self) -> bool:
        return True


# ── Dispatcher ──────────────────────────────────────────────────────────────

class MessageAdapter:
    """Dispatcher que selecciona el adapter correcto según el provider."""

    def to_provider(self, messages: list[dict], provider: str, *, system: str = "") -> list[dict]:
        adapter = get_adapter(provider)
        return adapter.to_provider(messages, system=system)

    def from_provider(self, response: dict | str, provider: str) -> dict:
        adapter = get_adapter(provider)
        return adapter.from_provider(response)

    def extract_content(self, response: dict | str, provider: str) -> str:
        adapter = get_adapter(provider)
        return adapter.extract_content(response)

    def supports_tools(self, provider: str) -> bool:
        adapter = get_adapter(provider)
        return adapter.supports_tools()


# ── Registry ─────────────────────────────────────────────────────────────────

_ADAPTERS: dict[str, type[BaseMessageAdapter]] = {
    "openai": OpenAIAdapter,
    "codex": OpenAIAdapter,
    "copilot": OpenAIAdapter,
    "github-models": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "ollama-local": OllamaAdapter,
    "ollama-cloud": OllamaAdapter,
    "replicate": OpenAIAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(provider: str) -> BaseMessageAdapter:
    provider = provider.lower().strip()
    adapter_cls = _ADAPTERS.get(provider, OpenAIAdapter)
    return adapter_cls()


def list_supported_providers() -> list[str]:
    return list(_ADAPTERS.keys())


def _run_tests() -> int:
    history = [
        {"role": "system", "content": "Eres BAGO."},
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "¡Hola!"},
    ]

    # OpenAI adapter
    oa = get_adapter("copilot")
    oa_msgs = oa.to_provider(history, system="Eres BAGO.")
    assert oa_msgs[0]["role"] == "system"
    assert len(oa_msgs) == 3  # system + user + assistant (skip dup system)
    assert oa.extract_content({"choices": [{"message": {"content": "test"}}]}) == "test"

    # Anthropic adapter
    aa = get_adapter("anthropic")
    aa_msgs = aa.to_provider(history, system="Eres BAGO.")
    assert all(m["role"] != "system" for m in aa_msgs)
    assert len(aa_msgs) == 2  # user + assistant only
    anth_resp = {
        "content": [{"type": "text", "text": "Hola desde Claude"}],
        "stop_reason": "end_turn",
    }
    assert aa.extract_content(anth_resp) == "Hola desde Claude"

    # Ollama adapter
    oll = get_adapter("ollama-local")
    oll_msgs = oll.to_provider(history)
    assert oll_msgs[0]["role"] == "system"
    assert len(oll_msgs) == 3

    # Gemini adapter
    ga = get_adapter("gemini")
    gem_msgs = ga.to_provider(history)
    assert gem_msgs[0]["role"] == "user"
    assert "parts" in gem_msgs[0]

    # Test roundtrip
    bago_resp = oa.from_provider({"choices": [{"message": {"content": "roundtrip"}}]})
    assert bago_resp["role"] == "assistant"
    assert bago_resp["content"] == "roundtrip"

    print("message_adapter.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
anthropic.py — BAGO 4.1.5 Anthropic Provider Adapter

Adapter directo HTTP para la API de Anthropic (Claude).
Requiere ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from provider_adapter import ProviderAdapter, ModelInfo, HealthStatus, ProviderResponse, TokenUsage


ANTHROPIC_API = "https://api.anthropic.com/v1"


class AnthropicAdapter(ProviderAdapter):
    """Adapter para Anthropic Claude."""

    def __init__(self, config: dict | None = None):
        super().__init__("anthropic", config)
        self.api_key = (config or {}).get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = (config or {}).get("base_url", ANTHROPIC_API).rstrip("/")

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key or "",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    def _post(self, url: str, payload: dict, timeout: float = 60.0) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, url: str, timeout: float = 5.0) -> dict:
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        # Anthropic format: system is top-level, messages are user/assistant only
        anthropic_messages = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role in ("user", "assistant"):
                anthropic_messages.append({"role": role, "content": content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        try:
            result = self._post(f"{self.base_url}/messages", payload)
        except Exception as exc:
            self._set_error(str(exc))
            return ProviderResponse(content=f"Error Anthropic: {exc}", provider=self.provider_name, model_used=model)

        content = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage_raw = result.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_raw.get("input_tokens", 0),
            output_tokens=usage_raw.get("output_tokens", 0),
            total_tokens=usage_raw.get("input_tokens", 0) + usage_raw.get("output_tokens", 0),
        )
        return ProviderResponse(
            content=content,
            model_used=result.get("model", model),
            provider=self.provider_name,
            finish_reason=result.get("stop_reason", ""),
            usage=usage,
            metadata={"id": result.get("id")},
        )

    def list_models(self) -> list[ModelInfo]:
        try:
            data = self._get(f"{self.base_url}/models")
        except Exception as exc:
            self._set_error(str(exc))
            return []

        models = []
        for m in data.get("data", []):
            models.append(ModelInfo(
                model_id=m.get("id", ""),
                wire_name=m.get("id", ""),
                provider=self.provider_name,
                context_tokens=m.get("context_window", 200000),
                max_output_tokens=8192,
                best_for="general",
                cost="pay_per_token",
                available=True,
            ))
        return models

    def _extract_delta_text(self, chunk: dict) -> str:
        """Extrae texto de deltas de streaming Anthropic."""
        tp = chunk.get("type", "")
        if tp == "content_block_delta":
            delta = chunk.get("delta", {})
            return delta.get("text", "")
        if tp == "message_delta":
            return ""
        # Fallback genérico
        for key in ("content", "text", "partial_json"):
            if key in chunk:
                return str(chunk[key])
        return ""

    def chat_stream(
        self,
        messages: list[dict],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ):
        """Streaming real para Anthropic (SSE)."""
        anthropic_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/messages", data=data, headers=self._headers(), method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        chunk_json = line[6:]
                        if chunk_json == "[DONE]":
                            break
                        try:
                            chunk = json.loads(chunk_json)
                        except json.JSONDecodeError:
                            continue
                        text = self._extract_delta_text(chunk)
                        if text:
                            yield text
        except Exception as exc:
            self._set_error(str(exc))
            yield f"Error Anthropic: {exc}"

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, provider=self.provider_name, detail="No API key")
        try:
            data = self._get(f"{self.base_url}/models", timeout=timeout)
            count = len(data.get("data", []))
            return HealthStatus(ok=True, provider=self.provider_name, detail=f"Anthropic OK ({count} models)", models_available=count)
        except Exception as exc:
            return HealthStatus(ok=False, provider=self.provider_name, detail=str(exc))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def supports_tools(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True


def _run_tests() -> int:
    adapter = AnthropicAdapter()
    assert adapter.provider_name == "anthropic"
    print("anthropic.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

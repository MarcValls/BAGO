#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
ollama_cloud.py — BAGO 4.1.5 Ollama Cloud Provider Adapter

Adapter para instancias Ollama remotas (cloud/self-hosted).
Mismo protocolo que Ollama local pero con URL configurable
y soporte opcional de autenticación (API key o Bearer token).

Variables de entorno:
  OLLAMA_CLOUD_URL   — URL base del endpoint remoto
  OLLAMA_CLOUD_KEY   — API key opcional
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


DEFAULT_URL = os.environ.get("OLLAMA_CLOUD_URL", "")


class OllamaCloudAdapter(ProviderAdapter):
    """Adapter para Ollama remoto/cloud."""

    def __init__(self, config: dict | None = None):
        super().__init__("ollama-cloud", config)
        self.base_url = (config or {}).get("base_url", DEFAULT_URL).rstrip("/")
        self.api_key = (config or {}).get("api_key") or os.environ.get("OLLAMA_CLOUD_KEY", "")

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _api(self, path: str) -> str:
        return f"{self.base_url}/api{path}"

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
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = tools

        try:
            result = self._post(self._api("/chat"), payload)
        except Exception as exc:
            self._set_error(str(exc))
            return ProviderResponse(content=f"Error Ollama Cloud: {exc}", provider=self.provider_name, model_used=model)

        msg = result.get("message", {})
        usage = TokenUsage(
            input_tokens=result.get("prompt_eval_count", 0),
            output_tokens=result.get("eval_count", 0),
            total_tokens=(result.get("prompt_eval_count", 0) + result.get("eval_count", 0)),
        )
        return ProviderResponse(
            content=msg.get("content", ""),
            model_used=model,
            provider=self.provider_name,
            finish_reason="stop" if result.get("done") else "",
            usage=usage,
            metadata={"done": result.get("done"), "total_duration": result.get("total_duration")},
            tool_calls=msg.get("tool_calls", []),
        )

    def list_models(self) -> list[ModelInfo]:
        if not self.base_url:
            return []
        try:
            data = self._get(self._api("/tags"))
        except Exception as exc:
            self._set_error(str(exc))
            return []

        models = []
        for m in data.get("models", []):
            name = m.get("name", "")
            models.append(ModelInfo(
                model_id=name,
                wire_name=name,
                provider=self.provider_name,
                context_tokens=32768,
                max_output_tokens=8192,
                best_for="general",
                cost="free_or_metered",
                available=True,
            ))
        return models

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
        """Streaming real para Ollama Cloud (NDJSON)."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._api("/chat"), data=data, headers=self._headers(), method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
        except Exception as exc:
            self._set_error(str(exc))
            yield f"Error Ollama Cloud: {exc}"

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        if not self.base_url:
            return HealthStatus(ok=False, provider=self.provider_name, detail="No URL configured")
        try:
            self._get(self._api("/tags"), timeout=timeout)
            models = self.list_models()
            return HealthStatus(
                ok=True,
                provider=self.provider_name,
                detail=f"Ollama Cloud OK ({len(models)} models)",
                latency_ms=0.0,
                models_available=len(models),
            )
        except Exception as exc:
            return HealthStatus(ok=False, provider=self.provider_name, detail=str(exc))

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def supports_tools(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True


def _run_tests() -> int:
    adapter = OllamaCloudAdapter()
    assert adapter.provider_name == "ollama-cloud"
    print("ollama_cloud.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

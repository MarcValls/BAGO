#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
ollama_local.py — BAGO 4.1.5 Ollama Local Provider Adapter

Adapter para modelos Ollama ejecutándose en localhost:11434.
No requiere credenciales.
"""

from __future__ import annotations

import json
import os
import re
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
from ollama_discovery import discover_ollama_model_names


DEFAULT_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


class OllamaLocalAdapter(ProviderAdapter):
    """Adapter para Ollama local."""

    def __init__(self, config: dict | None = None):
        super().__init__("ollama-local", config)
        self.base_url = (config or {}).get("base_url", DEFAULT_URL).rstrip("/")
        try:
            self.timeout_seconds = float((config or {}).get("timeout_seconds", 60.0) or 60.0)
        except (TypeError, ValueError):
            self.timeout_seconds = 60.0

    def _api(self, path: str) -> str:
        return f"{self.base_url}/api{path}"

    def _post(self, url: str, payload: dict, timeout: float = 60.0) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, url: str, timeout: float = 5.0) -> dict:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _tool_call_name_map(self, messages: list[dict]) -> dict[str, str]:
        names: dict[str, str] = {}
        for message in messages:
            for raw in message.get("tool_calls", []) or []:
                if not isinstance(raw, dict):
                    continue
                function = raw.get("function", {}) if isinstance(raw.get("function", {}), dict) else {}
                name = str(function.get("name") or raw.get("name") or "").strip()
                if not name:
                    continue
                for key in (raw.get("id"), raw.get("tool_call_id"), function.get("index"), name):
                    if key is not None and str(key).strip():
                        names[str(key)] = name
        return names

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Strip BOM and normalize line endings to LF — llama-server crashes on CRLF or embedded BOM."""
        return text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")

    def _format_messages_for_ollama(self, messages: list[dict], system: str = "") -> list[dict]:
        tool_names = self._tool_call_name_map(messages)
        payload_messages: list[dict] = []
        if system:
            payload_messages.append({"role": "system", "content": self._normalize_text(system)})
        for message in messages:
            role = str(message.get("role", "user"))
            if role == "system" and system:
                continue
            if role == "tool":
                call_id = str(message.get("tool_call_id") or message.get("id") or "").strip()
                tool_name = str(message.get("tool_name") or tool_names.get(call_id) or call_id).strip()
                tool_message = {"role": "tool", "content": str(message.get("content", ""))}
                if tool_name:
                    tool_message["tool_name"] = tool_name
                payload_messages.append(tool_message)
                continue
            payload = {"role": role, "content": str(message.get("content", ""))}
            if role == "assistant" and message.get("tool_calls"):
                payload["tool_calls"] = message.get("tool_calls")
            payload_messages.append(payload)
        return payload_messages

    def _fallback_tool_calls_from_content(self, content: str) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        text = content or ""
        for idx, match in enumerate(re.finditer(r"<tool_call>\s*(.*?)\s*</tool_call>", text, flags=re.DOTALL | re.IGNORECASE)):
            raw_json = match.group(1).strip()
            if not raw_json:
                continue
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
            function = data.get("function", {}) if isinstance(data.get("function"), dict) else {}
            name = str(function.get("name") or data.get("name") or data.get("tool") or "").strip()
            if not name:
                continue
            arguments = function.get("arguments", data.get("arguments", data.get("args", {})))
            if not isinstance(arguments, dict):
                arguments = {"value": arguments}
            calls.append({
                "id": str(data.get("id") or f"ollama-fallback-{idx}"),
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": arguments,
                },
            })
        return calls

    def _strip_fallback_tool_call_markup(self, content: str) -> str:
        return re.sub(r"<tool_call>\s*.*?\s*</tool_call>", "", content or "", flags=re.DOTALL | re.IGNORECASE).strip()

    def _offline_detail(self, exc: Exception) -> str:
        models = discover_ollama_model_names(None)
        if models:
            preview = ", ".join(models[:5])
            suffix = f" (detectados en disco: {preview})"
            if len(models) > 5:
                suffix += f" +{len(models) - 5} más"
            return f"Ollama local no responde{suffix}: {exc}"
        return f"Ollama local no responde: {exc}"

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
        payload_messages = self._format_messages_for_ollama(messages, system=system)
        payload = {
            "model": model,
            "messages": payload_messages,
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = tools

        try:
            result = self._post(self._api("/chat"), payload, timeout=self.timeout_seconds)
        except Exception as exc:
            self._set_error(str(exc))
            detail = self._offline_detail(exc)
            return ProviderResponse(content=detail, provider=self.provider_name, model_used=model, metadata={"error": detail})

        msg = result.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", []) or self._fallback_tool_calls_from_content(content)
        if tool_calls:
            content = self._strip_fallback_tool_call_markup(content)
        usage = TokenUsage(
            input_tokens=result.get("prompt_eval_count", 0),
            output_tokens=result.get("eval_count", 0),
            total_tokens=(result.get("prompt_eval_count", 0) + result.get("eval_count", 0)),
        )
        return ProviderResponse(
            content=content,
            model_used=model,
            provider=self.provider_name,
            finish_reason="stop" if result.get("done") else "",
            usage=usage,
            metadata={"done": result.get("done"), "total_duration": result.get("total_duration")},
            tool_calls=tool_calls,
        )

    def list_models(self) -> list[ModelInfo]:
        names = discover_ollama_model_names(self.base_url)
        models = []
        for name in names:
            models.append(ModelInfo(
                model_id=name,
                wire_name=name,
                provider=self.provider_name,
                context_tokens=32768,  # Default; Ollama doesn’t expose this via API
                max_output_tokens=8192,
                best_for="general",
                cost="free",
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
        """Streaming real para Ollama: NDJSON línea por línea."""
        payload_messages = self._format_messages_for_ollama(messages, system=system)
        payload = {
            "model": model,
            "messages": payload_messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._api("/chat"), data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
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
            yield self._offline_detail(exc)

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        try:
            self._get(self._api("/tags"), timeout=timeout)
            models = self.list_models()
            return HealthStatus(
                ok=True,
                provider=self.provider_name,
                detail=f"Ollama OK ({len(models)} models)",
                latency_ms=0.0,
                models_available=len(models),
            )
        except Exception as exc:
            models = self.list_models()
            detail = str(exc)
            if models:
                detail = f"Ollama offline ({len(models)} modelos detectados en disco): {exc}"
            return HealthStatus(ok=False, provider=self.provider_name, detail=detail, models_available=len(models))

    def is_configured(self) -> bool:
        return True  # No auth needed

    def supports_tools(self) -> bool:
        return True  # Ollama supports tools

    def supports_streaming(self) -> bool:
        return True


def _run_tests() -> int:
    import tempfile
    # Test adapter instantiation
    adapter = OllamaLocalAdapter()
    assert adapter.provider_name == "ollama-local"
    assert adapter.is_configured()
    print("ollama_local.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

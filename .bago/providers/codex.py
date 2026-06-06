#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
codex.py — BAGO 4.1.5 Codex / OpenAI Provider Adapter

Adapter directo HTTP para la API de OpenAI (incluye Codex models).
Requiere OPENAI_API_KEY.
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
from cli_bridge import build_prompt, find_cli, run_cli


OPENAI_API = "https://api.openai.com/v1"


class CodexAdapter(ProviderAdapter):
    """Adapter para OpenAI / Codex."""

    def __init__(self, config: dict | None = None):
        super().__init__("codex", config)
        self.api_key = (config or {}).get("api_key") or os.environ.get("OPENAI_API_KEY")
        self.base_url = (config or {}).get("base_url", OPENAI_API).rstrip("/")
        self.base_path = Path((config or {}).get("base_path") or os.getcwd()).resolve()
        self.cli_path = find_cli("codex", (config or {}).get("cli_path", ""))
        self.cli_timeout = float((config or {}).get("cli_timeout", 180))
        self.cli_authenticated = bool((config or {}).get("cli_authenticated")) or (
            bool(self.cli_path) and (Path.home() / ".codex" / "auth.json").exists()
        )

    def _use_cli(self) -> bool:
        return not self.api_key and self.cli_authenticated

    def _chat_cli(self, messages: list[dict], model: str, system: str) -> ProviderResponse:
        prompt = build_prompt(messages, system)
        command = [
            self.cli_path,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "-C",
            str(self.base_path),
        ]
        if model:
            command += ["--model", model]
        command.append("-")
        content = run_cli(command, self.base_path, self.cli_timeout, input_text=prompt)
        return ProviderResponse(
            content=content,
            model_used=model,
            provider=self.provider_name,
            finish_reason="stop",
            metadata={"transport": "cli"},
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
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
        if self._use_cli():
            try:
                return self._chat_cli(messages, model, system)
            except Exception as exc:
                self._set_error(str(exc))
                return ProviderResponse(
                    content=f"Error Codex CLI: {exc}",
                    provider=self.provider_name,
                    model_used=model,
                    finish_reason="error",
                    metadata={"transport": "cli", "error": True},
                )

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if system and not any(m.get("role") == "system" for m in messages):
            payload["messages"] = [{"role": "system", "content": system}] + messages
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        try:
            result = self._post(f"{self.base_url}/chat/completions", payload)
        except Exception as exc:
            self._set_error(str(exc))
            return ProviderResponse(
                content=f"Error OpenAI: {exc}",
                provider=self.provider_name,
                model_used=model,
                finish_reason="error",
                metadata={"transport": "api", "error": True},
            )

        choice = result.get("choices", [{}])[0]
        msg = choice.get("message", {})
        usage_raw = result.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_raw.get("prompt_tokens", 0),
            output_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )
        return ProviderResponse(
            content=msg.get("content", ""),
            model_used=result.get("model", model),
            provider=self.provider_name,
            finish_reason=choice.get("finish_reason", ""),
            usage=usage,
            metadata={"id": result.get("id")},
            tool_calls=msg.get("tool_calls", []),
        )

    def list_models(self) -> list[ModelInfo]:
        if self._use_cli():
            return [
                ModelInfo("gpt-5.4-mini", "gpt-5.4-mini", self.provider_name, 128000, 16384, "fast_coding", "subscription"),
                ModelInfo("gpt-5.3-codex", "gpt-5.3-codex", self.provider_name, 128000, 16384, "coding", "subscription"),
                ModelInfo("gpt-5.2", "gpt-5.2", self.provider_name, 128000, 16384, "general", "subscription"),
            ]
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
                context_tokens=128000,
                max_output_tokens=16384,
                best_for="general",
                cost="pay_per_token",
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
        """Streaming real para OpenAI/Codex (SSE)."""
        if self._use_cli():
            response = self._chat_cli(messages, model, system)
            if response.content:
                yield response.content
            return

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if system and not any(m.get("role") == "system" for m in messages):
            payload["messages"] = [{"role": "system", "content": system}] + messages
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=data, headers=self._headers(), method="POST"
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
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
        except Exception as exc:
            self._set_error(str(exc))
            yield f"Error Codex: {exc}"

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        if self._use_cli():
            try:
                detail = run_cli([self.cli_path, "login", "status"], self.base_path, timeout)
                return HealthStatus(ok=True, provider=self.provider_name, detail=f"Codex CLI: {detail}", models_available=3)
            except Exception as exc:
                return HealthStatus(ok=False, provider=self.provider_name, detail=f"Codex CLI: {exc}")
        if not self.api_key:
            return HealthStatus(ok=False, provider=self.provider_name, detail="No API key ni CLI autenticado")
        try:
            data = self._get(f"{self.base_url}/models", timeout=timeout)
            count = len(data.get("data", []))
            return HealthStatus(ok=True, provider=self.provider_name, detail=f"OpenAI OK ({count} models)", models_available=count)
        except Exception as exc:
            return HealthStatus(ok=False, provider=self.provider_name, detail=str(exc))

    def is_configured(self) -> bool:
        return bool(self.api_key or self._use_cli())

    def supports_tools(self) -> bool:
        return bool(self.api_key)

    def supports_streaming(self) -> bool:
        return bool(self.api_key)


def _run_tests() -> int:
    adapter = CodexAdapter()
    assert adapter.provider_name == "codex"
    print("codex.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

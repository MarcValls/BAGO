#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
copilot.py — BAGO 4.1.5 GitHub Copilot Provider Adapter

Adapter para GitHub Copilot Chat.
Usa el endpoint de Copilot Chat v1/v2 directamente vía HTTP.
Requiere token de GitHub con scope 'copilot'.
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


COPILOT_API = "https://api.githubcopilot.com"


class CopilotAdapter(ProviderAdapter):
    """Adapter para GitHub Copilot Chat."""

    def __init__(self, config: dict | None = None):
        super().__init__("copilot", config)
        self.token = (config or {}).get("token") or os.environ.get("GITHUB_COPILOT_TOKEN") or self._gh_token()
        self.base_url = (config or {}).get("base_url", COPILOT_API).rstrip("/")
        self.model_id = (config or {}).get("model", "gpt-4o-copilot")
        self.base_path = Path((config or {}).get("base_path") or os.getcwd()).resolve()
        self.cli_path = find_cli("copilot", (config or {}).get("cli_path", ""))
        self.cli_timeout = float((config or {}).get("cli_timeout", 180))
        copilot_home = Path.home() / ".copilot"
        self.cli_authenticated = bool((config or {}).get("cli_authenticated")) or (
            bool(self.cli_path)
            and any((copilot_home / name).exists() for name in ("config.json", "session-store.db"))
        )

    def _use_cli(self) -> bool:
        return not self.token and self.cli_authenticated

    def _chat_cli(self, messages: list[dict], model: str, system: str) -> ProviderResponse:
        prompt = build_prompt(messages, system)
        command = [
            self.cli_path,
            "-p",
            prompt,
            "--silent",
            "--no-color",
            "--no-ask-user",
            "--no-auto-update",
            "--disable-builtin-mcps",
            "--no-custom-instructions",
            "-C",
            str(self.base_path),
        ]
        if model:
            command += ["--model", model]
        content = run_cli(command, self.base_path, self.cli_timeout)
        return ProviderResponse(
            content=content,
            model_used=model,
            provider=self.provider_name,
            finish_reason="stop",
            metadata={"transport": "cli"},
        )

    def _gh_token(self) -> str | None:
        # Attempt to read from gh CLI credential cache
        cache = Path.home() / ".config" / "github-copilot" / "hosts.json"
        if not cache.exists():
            cache = Path.home() / "AppData" / "Local" / "github-copilot" / "hosts.json"
        if cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                for host, creds in data.items():
                    if "oauth_token" in creds:
                        return creds["oauth_token"]
            except Exception:
                pass
        return None

    def _auth_header(self) -> dict:
        if not self.token:
            return {}
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Copilot-Integration-Id": "vscode-chat",
            "Editor-Version": "Neovim/0.10.0",
        }

    def _post(self, url: str, payload: dict, timeout: float = 60.0) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._auth_header(), method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, url: str, timeout: float = 5.0) -> dict:
        req = urllib.request.Request(url, headers=self._auth_header(), method="GET")
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
                    content=f"Error Copilot CLI: {exc}",
                    provider=self.provider_name,
                    model_used=model,
                    finish_reason="error",
                    metadata={"transport": "cli", "error": True},
                )

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if system:
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
                content=f"Error Copilot: {exc}",
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
        )

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("gpt-5.4-mini", "gpt-5.4-mini", self.provider_name, 128000, 16384, "fast_coding", "subscription"),
            ModelInfo("gpt-5.3-codex", "gpt-5.3-codex", self.provider_name, 128000, 16384, "coding", "subscription"),
            ModelInfo("gpt-5.2", "gpt-5.2", self.provider_name, 128000, 16384, "general", "subscription"),
            ModelInfo("gpt-4o-copilot", "gpt-4o", self.provider_name, 128000, 16384, "coding", "subscription"),
        ]

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
        """Streaming real para Copilot (SSE, OpenAI-compatible)."""
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
        if system:
            payload["messages"] = [{"role": "system", "content": system}] + messages
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=data, headers=self._auth_header(), method="POST"
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
            yield f"Error Copilot: {exc}"

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        if self._use_cli():
            try:
                detail = run_cli([self.cli_path, "--version"], self.base_path, timeout).splitlines()[0]
                return HealthStatus(ok=True, provider=self.provider_name, detail=f"Copilot CLI: {detail}", models_available=4)
            except Exception as exc:
                return HealthStatus(ok=False, provider=self.provider_name, detail=f"Copilot CLI: {exc}")
        if not self.token:
            return HealthStatus(ok=False, provider=self.provider_name, detail="No token ni CLI autenticado")
        try:
            self._get(f"{self.base_url}/models", timeout=timeout)
            return HealthStatus(ok=True, provider=self.provider_name, detail="Copilot API reachable")
        except Exception as exc:
            return HealthStatus(ok=False, provider=self.provider_name, detail=str(exc))

    def is_configured(self) -> bool:
        return bool(self.token or self._use_cli())

    def supports_tools(self) -> bool:
        return bool(self.token)

    def supports_streaming(self) -> bool:
        return bool(self.token)


def _run_tests() -> int:
    adapter = CopilotAdapter()
    assert adapter.provider_name == "copilot"
    models = adapter.list_models()
    assert len(models) >= 2
    print("copilot.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

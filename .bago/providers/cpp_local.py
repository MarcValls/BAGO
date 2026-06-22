#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
cpp_local.py — BAGO C++ Local Runtime Adapter

Adapter para un runtime local externo escrito en C++.
Fase 1: define el contrato HTTP/JSON mínimo para salud, modelos y chat.
Python conserva la sesión; C++ actúa como motor local intercambiable.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request
from json import JSONDecodeError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


DEFAULT_URL = os.environ.get("CPP_LOCAL_BASE_URL", "http://127.0.0.1:8765")


class CppLocalRuntimeError(RuntimeError):
    pass


class CppLocalAdapter(ProviderAdapter):
    """Adapter HTTP/JSON para un runtime local C++."""

    def __init__(self, config: dict | None = None):
        super().__init__("cpp-local", config)
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.transport = str(cfg.get("transport", "http")).lower()
        self.base_url = str(cfg.get("base_url", DEFAULT_URL)).rstrip("/")
        self.timeout = float(cfg.get("timeout_seconds", 30.0))
        self.streaming = bool(cfg.get("supports_streaming", False))
        self.tool_calling = bool(cfg.get("supports_tools", False))
        self.embedding_capable = bool(cfg.get("supports_embeddings", False))
        self.executable_path = str(cfg.get("executable_path", ""))

    def _api(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _post(self, url: str, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            raw = resp.read().decode("utf-8")
        try:
            return json.loads(raw)
        except JSONDecodeError as exc:
            raise RuntimeError(f"Respuesta no JSON desde cpp-local en {url}") from exc

    def _get(self, url: str, timeout: float | None = None) -> dict[str, Any]:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            raw = resp.read().decode("utf-8")
        try:
            return json.loads(raw)
        except JSONDecodeError as exc:
            raise RuntimeError(f"Respuesta no JSON desde cpp-local en {url}") from exc

    def _response_from_payload(self, result: dict[str, Any], model: str) -> ProviderResponse:
        usage_payload = result.get("usage", {})
        if not isinstance(usage_payload, dict):
            usage_payload = {}

        message = result.get("message", {})
        if not isinstance(message, dict):
            message = {}

        return ProviderResponse(
            content=str(result.get("content") or message.get("content") or ""),
            model_used=str(result.get("model_used") or result.get("model") or model),
            provider=self.provider_name,
            finish_reason=str(result.get("finish_reason") or result.get("done_reason") or "stop"),
            usage=TokenUsage(
                input_tokens=int(usage_payload.get("input_tokens", 0)),
                output_tokens=int(usage_payload.get("output_tokens", 0)),
                total_tokens=int(usage_payload.get("total_tokens", 0)),
                calls=int(usage_payload.get("calls", 1)),
            ),
            metadata=dict(result.get("metadata") or {}),
            tool_calls=list(result.get("tool_calls") or message.get("tool_calls") or []),
        )

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
        if not self.is_configured():
            raise CppLocalRuntimeError("Runtime cpp-local no configurado")
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "system": system,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        try:
            result = self._post(self._api("/chat"), payload)
        except Exception as exc:
            self._set_error(str(exc))
            raise CppLocalRuntimeError(str(exc)) from exc

        return self._response_from_payload(result, model)

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
        if not self.is_configured():
            raise CppLocalRuntimeError("Runtime cpp-local no configurado")
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "system": system,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._api("/chat_stream"),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if item.get("done"):
                        break
                    delta = str(item.get("delta") or "")
                    if delta:
                        yield delta
        except Exception as exc:
            self._set_error(str(exc))
            raise CppLocalRuntimeError(str(exc)) from exc

    def embed(self, texts: list[str], *, model: str = "") -> list[list[float]]:
        if not self.is_configured():
            raise CppLocalRuntimeError("Runtime cpp-local no configurado")
        if not self.embedding_capable:
            raise CppLocalRuntimeError("Embeddings no habilitados para cpp-local")
        payload = {"texts": texts}
        if model:
            payload["model"] = model
        try:
            result = self._post(self._api("/embed"), payload)
        except Exception as exc:
            self._set_error(str(exc))
            raise CppLocalRuntimeError(str(exc)) from exc
        embeddings = list(result.get("embeddings") or [])
        return [[float(value) for value in vector] for vector in embeddings]

    def list_models(self) -> list[ModelInfo]:
        if not self.is_configured():
            return []
        try:
            data = self._get(self._api("/models"))
        except Exception as exc:
            self._set_error(str(exc))
            return []

        models_payload = data.get("models", [])
        models: list[ModelInfo] = []
        for item in models_payload:
            if isinstance(item, str):
                models.append(ModelInfo(
                    model_id=item,
                    wire_name=item,
                    provider=self.provider_name,
                    context_tokens=32768,
                    max_output_tokens=4096,
                    best_for="local_cpp_runtime",
                    cost="local",
                    available=True,
                ))
                continue
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or item.get("model_id") or item.get("name") or "")
            if not model_id:
                continue
            models.append(ModelInfo(
                model_id=model_id,
                wire_name=str(item.get("wire_name") or model_id),
                provider=self.provider_name,
                context_tokens=int(item.get("context_tokens", 32768)),
                max_output_tokens=int(item.get("max_output_tokens", 4096)),
                best_for=str(item.get("best_for", "local_cpp_runtime")),
                cost=str(item.get("cost", "local")),
                available=bool(item.get("available", True)),
            ))
        return models

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        if not self.is_configured():
            return HealthStatus(ok=False, provider=self.provider_name, detail="Runtime cpp-local no configurado")
        try:
            started = time.time()
            data = self._get(self._api("/health"), timeout=timeout)
            latency_ms = round((time.time() - started) * 1000, 1)
            return HealthStatus(
                ok=bool(data.get("ok", True)),
                provider=self.provider_name,
                detail=str(data.get("detail", "cpp-local runtime reachable")),
                latency_ms=float(data.get("latency_ms", latency_ms)),
                models_available=int(data.get("models_available", 0)),
            )
        except Exception as exc:
            return HealthStatus(ok=False, provider=self.provider_name, detail=str(exc))

    def is_configured(self) -> bool:
        if self.transport == "http":
            return self.enabled and bool(self.base_url)
        if self.transport == "stdio":
            return self.enabled and bool(self.executable_path)
        return False

    def supports_tools(self) -> bool:
        return self.tool_calling

    def supports_streaming(self) -> bool:
        return self.streaming

    def supports_embeddings(self) -> bool:
        return self.embedding_capable


def _run_tests() -> int:
    class MockCppRuntimeHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._write_json({
                    "ok": True,
                    "detail": "Mock cpp-local runtime OK",
                    "models_available": 1,
                })
                return
            if self.path == "/models":
                self._write_json({
                    "models": [
                        {
                            "id": "bago-cpp:stub",
                            "context_tokens": 16384,
                            "max_output_tokens": 2048,
                            "best_for": "integration_test",
                            "cost": "local",
                        }
                    ]
                })
                return
            self._write_json({"error": "not found"}, status=404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

            if self.path == "/embed":
                self._write_json({
                    "embeddings": [
                        [0.1, 0.2, 0.3],
                        [0.4, 0.5, 0.6],
                    ][:len(list(payload.get("texts") or []))]
                })
                return
            if self.path == "/chat_stream":
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                self.wfile.write(b'{"delta":"cpp-"}\n')
                self.wfile.write(b'{"delta":"stream"}\n')
                self.wfile.write(b'{"done":true,"usage":{"total_tokens":4}}\n')
                return
            if self.path == "/chat":
                tool_calls = []
                content = f"cpp-local::{payload.get('model', '')}"
                if payload.get("tools"):
                    tool_calls = [{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "list_directory",
                            "arguments": "{\"path\": \".\"}",
                        },
                    }]
                    content = ""
                self._write_json({
                    "content": content,
                    "model_used": payload.get("model", "bago-cpp:stub"),
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 6,
                        "total_tokens": 18,
                    },
                    "metadata": {"transport": "mock-http"},
                    "tool_calls": tool_calls,
                })
                return
            self._write_json({"error": "not found"}, status=404)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockCppRuntimeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        adapter = CppLocalAdapter({
            "enabled": True,
            "base_url": f"http://127.0.0.1:{server.server_port}",
            "transport": "http",
            "supports_streaming": True,
            "supports_tools": True,
            "supports_embeddings": True,
        })
        assert adapter.provider_name == "cpp-local"
        assert adapter.is_configured()
        health = adapter.health_check()
        assert health.ok
        models = adapter.list_models()
        assert len(models) == 1
        assert models[0].model_id == "bago-cpp:stub"
        response = adapter.chat([{"role": "user", "content": "hola"}], "bago-cpp:stub")
        assert response.content == "cpp-local::bago-cpp:stub"
        assert response.usage.total_tokens == 18
        tool_resp = adapter.chat(
            [{"role": "user", "content": "usa tool"}],
            "bago-cpp:stub",
            tools=[{"type": "function", "function": {"name": "list_directory"}}],
        )
        assert tool_resp.finish_reason == "tool_calls"
        assert tool_resp.tool_calls[0]["function"]["name"] == "list_directory"
        chunks = list(adapter.chat_stream([{"role": "user", "content": "stream"}], "bago-cpp:stub"))
        assert chunks == ["cpp-", "stream"]
        embeddings = adapter.embed(["uno", "dos"], model="embed-stub")
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 3
        disabled = CppLocalAdapter({"enabled": False, "base_url": f"http://127.0.0.1:{server.server_port}"})
        assert not disabled.is_configured()
        assert disabled.list_models() == []
        assert disabled.health_check().detail == "Runtime cpp-local no configurado"
        print("cpp_local.py --test: ALL PASS")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

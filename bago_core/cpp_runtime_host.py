#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
cpp_runtime_host.py — Reference host for the cpp-local protocol.

Sirve como daemon de desarrollo/pruebas para `cpp-local` en entornos donde el
runtime C++ aún no está compilado. Implementa el mismo contrato HTTP/JSON que
el runtime nativo debe respetar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import urllib.request
from hashlib import sha256
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


def _json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def _embedding(text: str, dims: int = 12) -> list[float]:
    digest = sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    for idx in range(dims):
        values.append(round(digest[idx] / 255.0, 6))
    return values


def _usage_for_text(text: str) -> dict[str, int]:
    input_tokens = max(len(text) // 4, 1)
    output_tokens = max(len(text) // 6, 1)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "calls": 1,
    }


def _last_message(messages: list[dict[str, Any]], role: str) -> str:
    for msg in reversed(messages):
        if msg.get("role") == role:
            return str(msg.get("content", ""))
    return ""


def _build_chat_payload(model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
    last_user = _last_message(messages, "user")
    last_tool = _last_message(messages, "tool")
    tool_enabled = bool(tools)

    if last_tool:
        content = f"Resultado integrado desde runtime cpp-local: {last_tool}"
        return {
            "content": content,
            "model_used": model,
            "finish_reason": "stop",
            "usage": _usage_for_text(content),
            "metadata": {"backend": "python-reference", "mode": "tool-result"},
            "tool_calls": [],
        }

    lowered = last_user.lower()
    if tool_enabled and ("herramienta" in lowered or "directorio" in lowered or "tool" in lowered):
        return {
            "content": "",
            "model_used": model,
            "finish_reason": "tool_calls",
            "usage": _usage_for_text(last_user or model),
            "metadata": {"backend": "python-reference", "mode": "tool-request"},
            "tool_calls": [
                {
                    "id": "cpp-local-call-1",
                    "type": "function",
                    "function": {
                        "name": "list_directory",
                        "arguments": json.dumps({"path": "."}, ensure_ascii=False),
                    },
                }
            ],
        }

    content = f"cpp-local runtime dice: {last_user or 'sin mensaje'}"
    return {
        "content": content,
        "model_used": model,
        "finish_reason": "stop",
        "usage": _usage_for_text(content),
        "metadata": {"backend": "python-reference", "mode": "chat"},
        "tool_calls": [],
    }


class CppRuntimeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json({
                "ok": True,
                "detail": "cpp-local reference host reachable",
                "models_available": 1,
                "latency_ms": 1.0,
                "capabilities": {
                    "streaming": True,
                    "tools": True,
                    "embeddings": True,
                },
            })
            return
        if self.path == "/models":
            self._write_json({
                "models": [
                    {
                        "id": self.server.runtime_model,
                        "wire_name": self.server.runtime_model,
                        "context_tokens": 32768,
                        "max_output_tokens": 4096,
                        "best_for": "hybrid_protocol_validation",
                        "cost": "local",
                        "available": True,
                    }
                ]
            })
            return
        self._write_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        if self.path == "/chat":
            payload = _json_body(self)
            messages = list(payload.get("messages") or [])
            model = str(payload.get("model") or self.server.runtime_model)
            result = _build_chat_payload(model, messages, list(payload.get("tools") or []))
            self._write_json(result)
            return

        if self.path == "/chat_stream":
            payload = _json_body(self)
            messages = list(payload.get("messages") or [])
            model = str(payload.get("model") or self.server.runtime_model)
            result = _build_chat_payload(model, messages, None)
            content = str(result.get("content", ""))
            chunks = [content[i:i + 12] for i in range(0, len(content), 12)] or [""]

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.end_headers()
            for chunk in chunks:
                line = json.dumps({"delta": chunk}, ensure_ascii=False).encode("utf-8") + b"\n"
                self.wfile.write(line)
                self.wfile.flush()
            final_line = json.dumps({
                "done": True,
                "usage": result["usage"],
                "model_used": result["model_used"],
            }, ensure_ascii=False).encode("utf-8") + b"\n"
            self.wfile.write(final_line)
            self.wfile.flush()
            return

        if self.path == "/embed":
            payload = _json_body(self)
            texts = [str(item) for item in list(payload.get("texts") or [])]
            self._write_json({
                "model_used": str(payload.get("model") or self.server.runtime_model),
                "embeddings": [_embedding(text) for text in texts],
            })
            return

        self._write_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        return


class CppRuntimeServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], runtime_model: str):
        super().__init__(server_address, CppRuntimeHandler)
        self.runtime_model = runtime_model


def serve(host: str, port: int, model: str) -> int:
    server = CppRuntimeServer((host, port), runtime_model=model)
    try:
        print(f"cpp-local reference host on http://{host}:{port} model={model}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


def _run_tests() -> int:
    server = CppRuntimeServer(("127.0.0.1", 0), runtime_model="bago-cpp:default")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8"))
        assert health["ok"] is True

        with urllib.request.urlopen(f"{base_url}/models", timeout=5) as resp:
            models = json.loads(resp.read().decode("utf-8"))
        assert models["models"][0]["id"] == "bago-cpp:default"

        chat_req = urllib.request.Request(
            f"{base_url}/chat",
            data=json.dumps({
                "model": "bago-cpp:default",
                "messages": [{"role": "user", "content": "hola runtime"}],
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(chat_req, timeout=5) as resp:
            chat = json.loads(resp.read().decode("utf-8"))
        assert "cpp-local runtime dice" in chat["content"]

        stream_req = urllib.request.Request(
            f"{base_url}/chat_stream",
            data=json.dumps({
                "model": "bago-cpp:default",
                "messages": [{"role": "user", "content": "hola streaming"}],
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(stream_req, timeout=5) as resp:
            lines = [json.loads(line.decode("utf-8")) for line in resp.readlines() if line.strip()]
        assert any("delta" in line for line in lines)
        assert lines[-1]["done"] is True

        embed_req = urllib.request.Request(
            f"{base_url}/embed",
            data=json.dumps({"texts": ["uno", "dos"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(embed_req, timeout=5) as resp:
            embeds = json.loads(resp.read().decode("utf-8"))
        assert len(embeds["embeddings"]) == 2
        assert len(embeds["embeddings"][0]) == 12
        print("cpp_runtime_host.py --test: ALL PASS")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reference host for the cpp-local runtime protocol")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default="bago-cpp:default")
    parser.add_argument("--test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.test:
        return _run_tests()
    return serve(args.host, args.port, args.model)


if __name__ == "__main__":
    raise SystemExit(main())

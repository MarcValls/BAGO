#!/usr/bin/env python3
"""Portable local LLM infrastructure scanner.

Usage:
    python .bago/tools/bago_infra_scan.py [--root DIR] [--quick] [--json] [--all]
    python .bago/tools/bago_infra_scan.py --test
"""
from __future__ import annotations

import argparse
import contextlib
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_scan_root

OLLAMA_DEFAULT_PORT = 11434
LMSTUDIO_DEFAULT_PORT = 1234
DEFAULT_SCAN_PORTS = [11434, 1234, 8080, 8888, 5000, 5001, 7860, 3000, 6006, 8000]
SYSTEM_PORTS = frozenset({135, 445, 902, 912, 5040, 5357, 5985, 47001, 7680, 5432, 3306, 6379, 27017})
SERVICE_SIGNATURES: list[dict[str, Any]] = [
    {"name": "ollama", "match": "ollama", "probe": "/api/tags", "type": "local-llm"},
    {"name": "ollama-web", "match": "Ollama", "probe": "/", "type": "web-ui"},
    {"name": "copilot", "match": "copilot", "probe": "/health", "type": "api"},
    {"name": "codex", "match": "codex", "probe": "/v1/models", "type": "api"},
    {"name": "openai-api", "match": "openai", "probe": "/v1/models", "type": "api"},
    {"name": "anthropic", "match": "anthropic", "probe": "/v1/models", "type": "api"},
    {"name": "bago-hub", "match": "bago", "probe": "/", "type": "gradio"},
    {"name": "gradio", "match": "gradio", "probe": "/", "type": "gradio"},
    {"name": "jupyter", "match": "jupyter", "probe": "/api", "type": "notebook"},
    {"name": "vllm", "match": "vllm", "probe": "/v1/models", "type": "local-llm"},
    {"name": "llamacpp", "match": "llama", "probe": "/health", "type": "local-llm"},
    {"name": "lmstudio", "match": "lm studio", "probe": "/v1/models", "type": "local-llm"},
]
TEST_WORKSPACE = Path(__file__).parent / "_selftest_bago_infra_scan"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_file(root: Path) -> Path:
    path = root / ".bago" / "state" / "infra_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _probe_http(host: str, port: int, path: str, timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        request = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
        request.add_header("User-Agent", "BAGO-InfraScan/4.1")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(8192).decode("utf-8", errors="replace")
            return {"status": response.status, "body": body, "headers": dict(response.headers)}
    except Exception:
        return None


def _extract_models(body: str) -> list[str]:
    try:
        data = json.loads(body)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    for key in ("models", "data", "model_list"):
        value = data.get(key)
        if not isinstance(value, list):
            continue
        models: list[str] = []
        for item in value:
            if isinstance(item, str):
                models.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("id") or item.get("model")
                if name:
                    models.append(str(name))
        return models[:50]
    return []


def _identify_service(host: str, port: int) -> dict[str, Any]:
    info: dict[str, Any] = {"host": host, "port": port, "status": "available", "name": f"port-{port}", "type": "unknown"}
    root = _probe_http(host, port, "/")
    if root:
        body = (root.get("body") or "")
        body_lower = body.lower()
        is_html = "<html" in body_lower
        headers = {str(k).lower(): str(v).lower() for k, v in (root.get("headers") or {}).items()}
        server_header = headers.get("server", "")

        if "ollama is running" in body_lower and not is_html:
            info["name"] = "ollama"
            info["type"] = "local-llm"
            version = _probe_http(host, port, "/api/version")
            if version and version.get("body"):
                try:
                    info["version"] = json.loads(version["body"]).get("version", "")
                except Exception:
                    pass
            tags = _probe_http(host, port, "/api/tags")
            if tags and tags.get("body"):
                info["models"] = _extract_models(tags["body"])
            return info

        if "ollama" in body_lower and is_html:
            info["name"] = "ollama-web"
            info["type"] = "web-ui"
            info["api_port"] = OLLAMA_DEFAULT_PORT
            return info

        for signature in SERVICE_SIGNATURES:
            match = signature["match"].lower()
            if match in body_lower or match in server_header:
                info["name"] = signature["name"]
                info["type"] = signature["type"]
                probe = _probe_http(host, port, signature["probe"])
                if probe and probe.get("body"):
                    models = _extract_models(probe["body"])
                    if models:
                        info["models"] = models
                return info

        if root.get("status") == 200:
            if is_html:
                info["name"] = "web-ui"
                info["type"] = "web"
            else:
                try:
                    json.loads(body)
                    info["name"] = "json-api"
                    info["type"] = "api"
                except Exception:
                    info["name"] = "http-service"
                    info["type"] = "unknown"
            return info

    if _port_open(host, port):
        info["name"] = "tcp-service"
        info["type"] = "unknown"
        return info

    info["status"] = "missing"
    return info


def _netstat_ports() -> list[int]:
    ports: set[int] = set()
    try:
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5)
    except Exception:
        return []
    for line in result.stdout.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        address = parts[1]
        if ":" not in address:
            continue
        port_text = address.rsplit(":", 1)[-1]
        try:
            ports.add(int(port_text))
        except ValueError:
            continue
    return sorted(ports)


def scan(quick: bool = False, host: str = "127.0.0.1", include_system: bool = False) -> list[dict[str, Any]]:
    ports = list(DEFAULT_SCAN_PORTS) if quick else (_netstat_ports() or list(DEFAULT_SCAN_PORTS))
    services: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for port in sorted(set(ports)):
        if not include_system and port in SYSTEM_PORTS:
            continue
        if not _port_open(host, port, timeout=0.3):
            continue
        info = _identify_service(host, port)
        if info.get("status") == "missing":
            continue
        key = (str(info.get("name", "port")), int(info.get("port", port)))
        if key in seen:
            continue
        seen.add(key)
        services.append(info)
    return sorted(services, key=lambda item: int(item.get("port", 0)))


def build_payload(root: Path, services: list[dict[str, Any]], quick: bool, host: str) -> dict[str, Any]:
    return {
        "scan_root": str(root),
        "host": host,
        "quick": quick,
        "timestamp": _now_iso(),
        "count": len(services),
        "services": services,
    }


def save_payload(root: Path, payload: dict[str, Any]) -> Path:
    path = _state_file(root)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def format_report(payload: dict[str, Any]) -> str:
    lines = [f"Infra scan root: {payload['scan_root']}", f"Host: {payload['host']}", f"Services found: {payload['count']}"]
    for service in payload.get("services", []):
        models = service.get("models") or []
        model_text = f" models={len(models)}" if models else ""
        lines.append(
            f"  [OK] {service.get('name', 'unknown')} {service.get('host', '127.0.0.1')}:{service.get('port', '?')} {service.get('type', 'unknown')}{model_text}"
        )
    if not payload.get("services"):
        lines.append("  No local LLM services detected.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable local LLM infrastructure scanner")
    parser.add_argument("--root", default="", help="Project root for output state")
    parser.add_argument("--quick", action="store_true", help="Scan default ports only")
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON output")
    parser.add_argument("--all", action="store_true", help="Include common system ports")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.test:
        return run_self_tests()

    root = get_scan_root(args.root)
    services = scan(quick=args.quick, include_system=args.all)
    payload = build_payload(root, services, quick=args.quick, host="127.0.0.1")
    state_path = save_payload(root, payload)
    payload["state_file"] = str(state_path)
    if args.as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(format_report(payload))
        print(f"State file: {state_path}")
    return 0


class _TestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            body = b"Ollama is running"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
        elif self.path == "/api/version":
            body = b'{"version": "0.4.0"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path == "/api/tags":
            body = b'{"models": [{"name": "llama3"}, {"name": "mistral"}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            body = b'{}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def _start_test_server() -> tuple[http.server.HTTPServer, threading.Thread, int]:
    server = http.server.HTTPServer(("127.0.0.1", 0), _TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    return server, thread, int(server.server_address[1])


def _reset_workspace() -> Path:
    if TEST_WORKSPACE.exists():
        shutil.rmtree(TEST_WORKSPACE)
    TEST_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return TEST_WORKSPACE


def run_self_tests() -> int:
    workspace = _reset_workspace()
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        results.append((name, condition, detail))

    server, thread, port = _start_test_server()
    try:
        check("port_open_bool", isinstance(_port_open("127.0.0.1", port), bool), "_port_open returns bool")
        check("probe_http_error", _probe_http("127.0.0.1", 1, "/") is None, "_probe_http handles connection errors")
        models = _extract_models('{"models": [{"name": "alpha"}, {"id": "beta"}]}')
        check("extract_models", models == ["alpha", "beta"], "_extract_models parses JSON payloads")
        identified = _identify_service("127.0.0.1", port)
        check("identify_service", identified.get("name") == "ollama" and identified.get("models") == ["llama3", "mistral"], "service identification works")
        with mock.patch.object(sys.modules[__name__], "_netstat_ports", return_value=[port]):
            services = scan(quick=False)
        check("scan_returns_list", isinstance(services, list) and len(services) == 1, "scan returns a service list")
        payload = build_payload(workspace, services, quick=False, host="127.0.0.1")
        state_path = save_payload(workspace, payload)
        check("save_payload", state_path.exists() and "services" in state_path.read_text(encoding="utf-8"), "scan state saved under root")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        shutil.rmtree(workspace, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

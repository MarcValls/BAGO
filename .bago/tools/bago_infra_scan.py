#!/usr/bin/env python3
"""bago_infra_scan.py — Escaneo automatico de servicios de modelos BAGO.

Detecta TODOS los servicios locales en 127.0.0.1:*, no solo hardcoded.
Usa netstat/socket scan + HTTP probing para identificar cada servicio.

Uso:
  bago infra-scan          → escaneo completo
  bago infra-scan --json  → salida JSON
  bago infra-scan --quick → solo servicios conocidos (sin scan amplio)
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from bago.ollama_runtime import (
    DEFAULT_BAGO_API_PORT,
    DEFAULT_BAGO_HUB_PORT,
    DEFAULT_BAGO_LLM_SERVER_PORT,
    DEFAULT_API_HTTP_PORT,
    DEFAULT_HONO_PORT,
    DEFAULT_NOTEBOOK_PORT,
    DEFAULT_SERVER_PORT,
    DEFAULT_TOOLING_PORT,
    DEFAULT_WEB_PORT,
    default_ollama_port,
)


THIS_FILE = Path(__file__).resolve()
TOOLS_DIR = THIS_FILE.parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = BAGO_ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = STATE_DIR / "infra_status.json"

# ── Firmas de servicios conocidos ─────────────────────────────────────────────
SERVICE_SIGNATURES: list[dict[str, Any]] = [
    {"name": "ollama",       "match": "ollama",  "probe": "/api/tags",   "type": "local-llm"},
    {"name": "ollama-web",   "match": "Ollama",  "probe": "/",          "type": "web-ui"},
    {"name": "copilot",      "match": "copilot", "probe": "/health",    "type": "api"},
    {"name": "codex",        "match": "codex",   "probe": "/v1/models", "type": "api"},
    {"name": "openai-api",   "match": "openai",  "probe": "/v1/models", "type": "api"},
    {"name": "anthropic",    "match": "anthropic","probe": "/v1/models","type": "api"},
    {"name": "bago-hub",     "match": "bago",    "probe": "/",          "type": "gradio"},
    {"name": "gradio",       "match": "gradio",  "probe": "/",          "type": "gradio"},
    {"name": "jupyter",      "match": "jupyter", "probe": "/api",       "type": "notebook"},
    {"name": "vllm",         "match": "vllm",    "probe": "/v1/models", "type": "local-llm"},
    {"name": "llamacpp",     "match": "llama",   "probe": "/health",    "type": "local-llm"},
    {"name": "lmstudio",     "match": "lm studio","probe": "/v1/models","type": "local-llm"},
]

# Puertos tipicos para escaneo rapido
# Puertos del sistema que NO son servicios de IA (Windows/Linux/macOS)
SYSTEM_PORTS = frozenset({
    135, 445, 902, 912,       # Windows RPC/SMB
    5040, 5357, 5985, 47001, # Windows services
    7680,                     # Windows Update
    5432, 3306, 6379, 27017, # DBs
    49664, 49665, 49666, 49667, 49668, 49669, # Windows dynamic RPC (no son IA, pero se pueden mostrar si --all)
})

QUICK_PORTS = [
    default_ollama_port(),
    DEFAULT_BAGO_API_PORT,
    DEFAULT_BAGO_LLM_SERVER_PORT,
    8081, 8082,
    DEFAULT_BAGO_HUB_PORT,
    DEFAULT_SERVER_PORT,
    DEFAULT_NOTEBOOK_PORT,
    DEFAULT_TOOLING_PORT,
    DEFAULT_WEB_PORT,
    DEFAULT_API_HTTP_PORT,
]


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _probe_http(host: str, port: int, path: str, timeout: float = 2.0) -> dict | None:
    try:
        import urllib.request
        url = f"http://{host}:{port}{path}"
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "BAGO-InfraScan/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            headers = dict(resp.headers)
            return {"status": resp.status, "body": body, "headers": headers}
    except Exception:
        return None


def _identify_service(host: str, port: int) -> dict:
    """Identifica un servicio por HTTP probing y firmas."""
    info: dict[str, Any] = {"host": host, "port": port, "status": "available"}

    # Probe raiz para obtener HTML/headers
    root = _probe_http(host, port, "/")
    if root:
        body = root.get("body") or ""
        body_lower = body.lower()
        is_html = "<html" in body_lower
        headers_lower = {k.lower(): v.lower() for k, v in (root.get("headers") or {}).items()}
        server_hdr = headers_lower.get("server", "")

        # Detectar Ollama API vs Web UI
        if "ollama is running" in body_lower and not is_html:
            info["name"] = "ollama"
            info["type"] = "local-llm"
            ver = _probe_http(host, port, "/api/version")
            if ver and ver.get("body"):
                try:
                    vdata = json.loads(ver["body"])
                    info["version"] = vdata.get("version", "")
                except Exception:
                    pass
            tags = _probe_http(host, port, "/api/tags")
            if tags and tags.get("body"):
                info["models"] = _extract_models(tags["body"])
            return info

        if "ollama" in body_lower and is_html:
            info["name"] = "ollama-web"
            info["type"] = "web-ui"
            info["api_port"] = str(default_ollama_port())  # referencia al API
            return info

        # Buscar firma conocida
        for sig in SERVICE_SIGNATURES:
            match_str = sig["match"].lower()
            if match_str in body_lower or match_str in server_hdr:
                info["name"] = sig["name"]
                info["type"] = sig["type"]
                specific = _probe_http(host, port, sig["probe"])
                if specific and specific.get("body"):
                    info["models"] = _extract_models(specific["body"])
                return info

    # Si no match firma, clasificar por tipo de respuesta
    if root and root.get("status") == 200:
        body = root.get("body", "")
        if "<html" in body.lower():
            info["name"] = f"web-ui"
            info["type"] = "web"
        else:
            try:
                json.loads(body)
                info["name"] = "json-api"
                info["type"] = "api"
            except Exception:
                info["name"] = "http-service"
                info["type"] = "unknown"
    elif _port_open(host, port):
        info["name"] = "tcp-service"
        info["type"] = "unknown"
    else:
        info["status"] = "missing"

    return info


def _extract_models(body: str) -> list[str]:
    try:
        data = json.loads(body)
    except Exception:
        return []
    if isinstance(data, dict):
        for key in ("models", "data", "model_list"):
            val = data.get(key)
            if isinstance(val, list):
                out = []
                for m in val:
                    if isinstance(m, str):
                        out.append(m)
                    elif isinstance(m, dict):
                        out.append(m.get("name") or m.get("id") or m.get("model", "?"))
                return out[:50]
    return []


def _netstat_ports() -> list[int]:
    """Usa netstat para obtener puertos LISTENING en 127.0.0.1 rapidamente."""
    ports = set()
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "LISTENING" not in line:
                continue
            m = re.search(r"127\.0\.0\.1:(\d+)", line)
            if m:
                ports.add(int(m.group(1)))
            # Tambien 0.0.0.0 (escucha en todas las interfaces)
            m2 = re.search(r"0\.0\.0\.0:(\d+)", line)
            if m2:
                ports.add(int(m2.group(1)))
    except Exception:
        pass
    return sorted(ports)


def scan(quick: bool = False) -> dict:
    """Ejecuta escaneo de infraestructura."""
    results: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "services": {},
        "available": [],
        "missing": [],
        "unidentified_ports": [],
    }

    if quick:
        ports_to_check = QUICK_PORTS
    else:
        ports_to_check = _netstat_ports()
        if not ports_to_check:
            ports_to_check = QUICK_PORTS

    host = "127.0.0.1"
    identified = set()

    for port in ports_to_check:
        if port in SYSTEM_PORTS and not '--all' in sys.argv:
            continue
        if not _port_open(host, port, timeout=0.3):
            continue

        info = _identify_service(host, port)
        if info.get("status") == "missing":
            continue

        name = info.get("name", f"port-{port}")
        # Evitar duplicar nombres
        if name in identified:
            name = f"{name}-{port}"
        identified.add(name)

        # Mejorar nombre si es web UI de Ollama
        if info.get("type") == "web" and port != default_ollama_port():
            root_check = _probe_http(host, port, "/")
            if root_check and "ollama" in (root_check.get("body","") or "").lower():
                info["name"] = "ollama-web"
                info["type"] = "web-ui"
        info["port"] = port
        results["services"][name] = info
        results["available"].append(name)

        if info.get("type") == "unknown":
            results["unidentified_ports"].append(port)

    # Servicios conocidos que NO se encontraron
    known_expected = {"ollama", "copilot", "codex", "openai-api", "anthropic", "vllm", "lmstudio"}
    for svc_name in known_expected:
        if svc_name not in identified:
            results["missing"].append(svc_name)

    STATUS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def format_report(results: dict) -> str:
    lines = ["\n  BAGO Infra Scan", "  " + "=" * 44]
    for name, info in results.get("services", {}).items():
        icon = "+"
        port = info.get("port", "?")
        svc_type = info.get("type", "")
        models = info.get("models", [])
        model_str = f" ({len(models)} modelos)" if models else ""
        lines.append(f"  [{icon}] {name:<16} {info.get('host','127.0.0.1')}:{port}  {svc_type}{model_str}")

    unknown = results.get("unidentified_ports", [])
    if unknown:
        lines.append(f"\n  Puertos sin identificar: {unknown}")

    missing = results.get("missing", [])
    if missing:
        lines.append(f"  No detectados: {', '.join(missing)}")

    avail = len(results.get("available", []))
    miss = len(results.get("missing", []))
    lines.append(f"\n  Disponibles: {avail}  |  No detectados: {miss}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    quick = "--quick" in sys.argv
    as_json = "--json" in sys.argv
    results = scan(quick=quick)
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_report(results))
    return 0




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    raise SystemExit(main())
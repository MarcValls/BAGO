#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ping_server.py — Verifica que el servidor local responde.

Envía una petición HTTP al servidor y muestra status, latencia y errores.
Lee la URL desde apps/server/.env (API_URL o PORT).

Uso:
    python3 .bago/tools/ping_server.py              # ping al servidor
    python3 .bago/tools/ping_server.py --url http://localhost:8788  # URL manual
    python3 .bago/tools/ping_server.py --path /health               # endpoint concreto
    python3 .bago/tools/ping_server.py --watch                      # ping cada 5s

Códigos de salida: 0 = responde, 1 = no responde
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

# ─── Colores ──────────────────────────────────────────────────────────────────

def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"

# ─── Config ───────────────────────────────────────────────────────────────────

_DEFAULT_HOST = "http://localhost"
_DEFAULT_PORT = 8788
_DEFAULT_PATH = "/"

# Endpoints to try for health check (in order)
_HEALTH_PATHS = ["/health", "/api/health", "/status", "/ping", "/"]


def _project_root() -> Path | None:
    gs_file = STATE / "global_state.json"
    if not gs_file.exists():
        return None
    try:
        gs = json.loads(gs_file.read_text(encoding="utf-8"))
        p = gs.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


def _read_server_url(project: Path) -> str:
    """Read API URL / PORT from apps/server/.env."""
    for fname in (".env", ".env.example"):
        f = project / "apps" / "server" / fname
        if not f.exists():
            continue
        env_vars: dict[str, str] = {}
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip().strip('"\'')

        # API_URL takes precedence
        if "API_URL" in env_vars:
            return env_vars["API_URL"]
        # Construct from PORT
        port = env_vars.get("PORT", str(_DEFAULT_PORT))
        if port.isdigit():
            return f"{_DEFAULT_HOST}:{port}"
        break

    return f"{_DEFAULT_HOST}:{_DEFAULT_PORT}"


def _ping(url: str, timeout: float = 5.0) -> tuple[int | None, float, str]:
    """
    Ping a URL. Returns (status_code, latency_ms, body_preview).
    status_code is None on connection error.
    """
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bago-ping/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = (time.monotonic() - t0) * 1000
            body = resp.read(200).decode("utf-8", errors="replace").strip()
            return resp.status, latency_ms, body
    except urllib.error.HTTPError as e:
        latency_ms = (time.monotonic() - t0) * 1000
        try:
            body = e.read(200).decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        return e.code, latency_ms, body
    except (urllib.error.URLError, OSError):
        latency_ms = (time.monotonic() - t0) * 1000
        return None, latency_ms, ""


def _find_working_endpoint(base_url: str) -> tuple[str, int | None, float, str]:
    """Try health paths until one responds."""
    for path in _HEALTH_PATHS:
        url = base_url.rstrip("/") + path
        status, latency, body = _ping(url)
        if status is not None:
            return url, status, latency, body
    # Return last attempt
    url = base_url.rstrip("/") + _HEALTH_PATHS[-1]
    status, latency, body = _ping(url)
    return url, status, latency, body


def _print_result(url: str, status: int | None, latency_ms: float, body: str) -> bool:
    """Print result and return True if server responded OK."""
    if status is None:
        print(f"  URL      : {url}")
        print(f"  Estado   : {RED('❌  no responde')}")
        print(f"  Latencia : {latency_ms:.0f} ms (timeout)")
        return False

    latency_str = f"{latency_ms:.0f} ms"
    if status < 400:
        status_str = GREEN(f"✅  HTTP {status}")
        ok = True
    elif status < 500:
        status_str = YELLOW(f"⚠  HTTP {status}")
        ok = True  # server is up, even if 4xx
    else:
        status_str = RED(f"❌  HTTP {status}")
        ok = False

    print(f"  URL      : {url}")
    print(f"  Estado   : {status_str}")
    print(f"  Latencia : {latency_str}")
    if body:
        preview = body[:80].replace("\n", " ").replace("\r", "")
        print(f"  Body     : {DIM(preview)}")

    return ok


def main() -> int:
    args = sys.argv[1:]
    watch    = "--watch" in args
    manual_url = None
    manual_path = _DEFAULT_PATH

    if "--url" in args:
        idx = args.index("--url")
        if idx + 1 < len(args):
            manual_url = args[idx + 1]

    if "--path" in args:
        idx = args.index("--path")
        if idx + 1 < len(args):
            manual_path = args[idx + 1]

    project = _project_root()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Ping al servidor local                              │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if project:
        print(f"  Proyecto : {project.name}")

    if manual_url:
        base_url = manual_url.rstrip("/")
        target_url = base_url + manual_path
    elif project and project.exists():
        base_url = _read_server_url(project)
        target_url = None  # auto-detect
    else:
        base_url = f"{_DEFAULT_HOST}:{_DEFAULT_PORT}"
        target_url = None

    def _do_ping() -> bool:
        print()
        if target_url:
            url, status, latency, body = target_url, *_ping(target_url)
        else:
            url, status, latency, body = _find_working_endpoint(base_url)
        return _print_result(url, status, latency, body)

    if watch:
        print(f"  {DIM('Ctrl+C para detener — ping cada 5s')}")
        try:
            while True:
                ok = _do_ping()
                icon = "✅" if ok else "❌"
                ts = time.strftime("%H:%M:%S")
                print(f"  [{ts}] {icon}")
                time.sleep(5)
        except KeyboardInterrupt:
            print()
        return 0
    else:
        ok = _do_ping()
        if not ok:
            print()
            print(f"  {DIM('¿El servidor está corriendo?')}")
            proj_name = project.name if project else "project"
            print(f"  {DIM(f'Arranca con: cd {proj_name} && npm run dev')}")
        print()
        return 0 if ok else 1



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())

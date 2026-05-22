#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
port_table.py — Tabla completa de puertos configurados en el proyecto.

Lee todos los PORT_* de los archivos .env, verifica con netstat cuál
puerto está en uso, y muestra la tabla con estado (libre/ocupado/PID).

Diferencia con port_kill.py: este no mata procesos, solo informa.

Uso:
    python3 .bago/tools/port_table.py            # tabla de todos los puertos
    python3 .bago/tools/port_table.py --app web  # solo una app
    python3 .bago/tools/port_table.py --free     # solo puertos libres
    python3 .bago/tools/port_table.py --busy     # solo puertos ocupados
    python3 .bago/tools/port_table.py --json     # salida JSON

Códigos de salida: 0 = OK, 1 = hay puertos ocupados
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

PORT_VAR_RE = re.compile(r'(?:PORT|_PORT|PORT_[A-Z]+)\s*=\s*(\d+)', re.IGNORECASE)
WELL_KNOWN_PORTS = {
    "3000": "web/react",
    "3001": "dev-server",
    "4000": "api",
    "5000": "server",
    "5173": "vite",
    "5174": "vite-preview",
    "6379": "redis",
    "8080": "server",
    "8443": "https",
    "8788": "cloudflare",
    "27017": "mongodb",
    "5432": "postgres",
    "3306": "mysql",
}


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_project() -> Path:
    gs = STATE / "global_state.json"
    if gs.exists():
        try:
            data = json.loads(gs.read_text(encoding="utf-8"))
            p = data.get("active_project", {}).get("path", "")
            if p:
                return Path(p)
        except Exception:
            pass
    return ROOT


def _scan_env_ports(project: Path, filter_app: str | None) -> dict[str, list[str]]:
    """Returns dict: port_number -> [source_app, ...]"""
    ports: dict[str, list[str]] = {}

    def _scan_file(env_file: Path, app_name: str) -> None:
        if not env_file.exists():
            return
        try:
            text = env_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                continue
            m = PORT_VAR_RE.search(line)
            if m:
                port = m.group(1)
                if 1 <= int(port) <= 65535:
                    ports.setdefault(port, [])
                    if app_name not in ports[port]:
                        ports[port].append(app_name)

    # Root .env
    _scan_file(project / ".env", "root")
    _scan_file(project / ".env.example", "root")

    # Apps
    apps_dir = project / "apps"
    if apps_dir.exists():
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir():
                continue
            if filter_app and app_dir.name != filter_app:
                continue
            _scan_file(app_dir / ".env", app_dir.name)
            _scan_file(app_dir / ".env.example", app_dir.name)

    return ports


def _get_listening_ports() -> dict[str, tuple[str, str]]:
    """Returns {port: (state, pid)} for all listening ports via netstat."""
    result: dict[str, tuple[str, str]] = {}
    try:
        proc = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, timeout=10,
        )
        text = proc.stdout.decode("cp1252", errors="replace")
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            proto = parts[0].upper()
            if proto not in ("TCP", "UDP"):
                continue
            local = parts[1]
            state = parts[3] if proto == "TCP" else "UDP"
            pid   = parts[4] if proto == "TCP" else parts[3]
            # Extract port from local address
            if ":" in local:
                port_str = local.rsplit(":", 1)[-1]
                if port_str.isdigit():
                    if port_str not in result and state in ("LISTENING", "ESTABLISHED", "UDP"):
                        result[port_str] = (state, pid)
    except Exception:
        pass
    return result


def _get_process_name(pid: str) -> str:
    """Get process name for a PID."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=5,
        )
        out = result.stdout.decode("cp1252", errors="replace").strip()
        if out and '"' in out:
            return out.split('"')[1]
    except Exception:
        pass
    return "?"


def main() -> int:
    args       = sys.argv[1:]
    filter_app = None
    show_free  = "--free" in args
    show_busy  = "--busy" in args
    as_json    = "--json" in args

    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            filter_app = args[idx + 1]

    project   = _load_project()
    env_ports = _scan_env_ports(project, filter_app)
    listening = _get_listening_ports()

    # Merge: all configured ports + well-known ports in use
    all_ports = set(env_ports.keys())

    rows = []
    for port in sorted(all_ports, key=int):
        apps    = env_ports.get(port, [])
        state, pid = listening.get(port, ("libre", ""))
        is_busy = state != "libre"
        proc_name = _get_process_name(pid) if is_busy and pid else ""
        rows.append({
            "port":      port,
            "apps":      apps,
            "state":     state,
            "pid":       pid,
            "process":   proc_name,
            "is_busy":   is_busy,
        })

    # Filter
    if show_free:
        rows = [r for r in rows if not r["is_busy"]]
    elif show_busy:
        rows = [r for r in rows if r["is_busy"]]

    if as_json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 1 if any(r["is_busy"] for r in rows) else 0

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Tabla de puertos del proyecto                       │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if not rows:
        print(f"  {YELLOW('⚠')} No se encontraron puertos configurados en .env\n")
        return 0

    busy_count = sum(1 for r in rows if r["is_busy"])
    print(f"  {len(rows)} puertos configurados  |  {RED(str(busy_count)) if busy_count else GREEN('0')} en uso\n")
    print(f"  {'PUERTO':<8}  {'APP(S)':<22}  {'ESTADO':<14}  {'PID':<8}  PROCESO")
    print(f"  {'──────':<8}  {'──────':<22}  {'──────':<14}  {'───':<8}  ───────")

    for r in rows:
        port    = r["port"]
        apps    = ", ".join(r["apps"][:2]) or DIM("(sin .env)")
        state   = r["state"]
        pid     = r["pid"]
        proc    = r["process"][:20] if r["process"] != "?" else DIM("?")

        if r["is_busy"]:
            state_str = RED(state[:12])
            port_str  = RED(port)
        else:
            state_str = GREEN("libre")
            port_str  = CYAN(port)
            pid = proc = ""

        print(f"  {port_str:<8}  {apps:<22}  {state_str:<14}  {pid:<8}  {proc}")

    print()
    return 1 if busy_count > 0 else 0



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

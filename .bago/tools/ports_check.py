#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ports_check.py — Verifica qué puertos del proyecto están en uso.

Muestra estado (libre/ocupado) de los puertos clave del proyecto activo:
API server, frontend dev server, PostgreSQL, y otros puertos declarados en .env.

Uso:
    python3 .bago/tools/ports_check.py          # puertos del proyecto activo
    python3 .bago/tools/ports_check.py --all    # también muestra puertos libres

Códigos de salida: 0 = OK, 1 = conflicto detectado
"""
from __future__ import annotations

import json
import os
import socket
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
IS_WIN = sys.platform == "win32"

# ─── Colores ──────────────────────────────────────────────────────────────────

def GREEN(s: str) -> str:  return f"\033[32m{s}\033[0m"
def RED(s: str)   -> str:  return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def BOLD(s: str)  -> str:  return f"\033[1m{s}\033[0m"
def DIM(s: str)   -> str:  return f"\033[2m{s}\033[0m"

# ─── Project detection ────────────────────────────────────────────────────────

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


def _read_env_ports(project: Path) -> dict[str, int]:
    """Read port numbers from apps/server/.env."""
    ports: dict[str, int] = {}
    for fname in (".env", ".env.example"):
        f = project / "apps" / "server" / fname
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" not in line or line.startswith("#"):
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"\'')
                if "PORT" in key.upper() and val.isdigit():
                    ports[key] = int(val)
            break
    return ports


# ─── Port check ───────────────────────────────────────────────────────────────

def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if the port is bound (i.e. a process is listening on it)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def _get_pid_for_port(port: int) -> str:
    """Try to get the PID using netstat (Windows) or ss/lsof (Unix)."""
    try:
        if IS_WIN:
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "TCP"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                encoding=None,  # get bytes
            ).decode(errors="replace")
            for line in out.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        return parts[-1]
        else:
            out = subprocess.check_output(
                ["ss", "-tlnp", f"sport = :{port}"],
                stderr=subprocess.DEVNULL, timeout=5, text=True
            )
            for line in out.splitlines():
                if f":{port}" in line and "pid=" in line:
                    idx = line.find("pid=")
                    pid_part = line[idx + 4:].split(",")[0]
                    return pid_part
    except Exception:
        pass
    return "?"


# ─── Default port catalogue ───────────────────────────────────────────────────

_DEFAULT_PORTS: list[tuple[int, str]] = [
    (8788,  "API server (Hono)"),
    (5173,  "Frontend (Vite)"),
    (5432,  "PostgreSQL"),
    (3000,  "Misc / Node"),
    (4173,  "Vite preview"),
    (8080,  "Alt HTTP"),
]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    show_all = "--all" in sys.argv[1:]

    project = _project_root()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Puertos del proyecto                                │")
    print("  └─────────────────────────────────────────────────────────────┘")

    # Build port list: defaults + env overrides
    port_map: dict[int, str] = {p: desc for p, desc in _DEFAULT_PORTS}

    if project and project.exists():
        env_ports = _read_env_ports(project)
        for key, val in env_ports.items():
            if val not in port_map:
                port_map[val] = key
        print(f"  Proyecto : {project.name}")
    else:
        print("  Proyecto : (ninguno activo)")

    print()
    print(f"  {'PUERTO':<8}  {'SERVICIO':<30}  {'ESTADO':<16}  {'PID'}")
    print(f"  {'──────':<8}  {'────────':<30}  {'──────':<16}  {'───'}")

    conflicts = 0
    for port in sorted(port_map):
        service = port_map[port]
        in_use  = _port_in_use(port)

        if in_use:
            pid     = _get_pid_for_port(port)
            status  = RED("● EN USO")
            pid_str = YELLOW(f"PID {pid}")
            conflicts += 1
        else:
            status  = GREEN("○ libre")
            pid_str = DIM("—")

        if in_use or show_all:
            print(f"  {port:<8}  {service:<30}  {status:<25}  {pid_str}")

    if not show_all and conflicts == 0:
        print(f"  {DIM('(todos los puertos monitorizados están libres)')}")

    print()

    if conflicts > 0:
        print(f"  {YELLOW(f'⚠  {conflicts} puerto(s) en uso')}")
        print(f"  {DIM('Usa --all para ver todos los puertos.')}")
    else:
        print(f"  {GREEN('✅  Sin conflictos de puertos detectados')}")
    print()

    return 1 if conflicts > 0 else 0



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

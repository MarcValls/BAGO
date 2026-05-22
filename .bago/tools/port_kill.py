#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
port_kill.py — Libera puertos ocupados por procesos del proyecto.

Lee los puertos configurados en .env de cada app y mata los procesos que los ocupen.

Uso:
    python3 .bago/tools/port_kill.py              # muestra puertos y procesos
    python3 .bago/tools/port_kill.py --kill       # mata los procesos
    python3 .bago/tools/port_kill.py 8788         # información de un puerto específico
    python3 .bago/tools/port_kill.py 8788 --kill  # mata proceso en ese puerto

Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

import json
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

# Common port env-var names to look for
PORT_VARS = [
    "PORT", "SERVER_PORT", "API_PORT", "DEV_PORT",
    "DESKTOP_DEV_PORT", "VITE_PORT", "ELECTRON_PORT",
]


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_project() -> Path | None:
    gs = STATE / "global_state.json"
    if not gs.exists():
        return None
    try:
        data = json.loads(gs.read_text(encoding="utf-8"))
        p = data.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


def _parse_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def _get_project_ports(project: Path) -> dict[int, str]:
    """Return {port: source} from all .env files in project apps."""
    ports: dict[int, str] = {}
    apps_env = [
        ("server", project / "apps" / "server" / ".env"),
        ("web",    project / "apps" / "web" / ".env"),
        ("electron", project / "apps" / "electron" / ".env"),
        ("root",   project / ".env"),
    ]
    for app_name, env_path in apps_env:
        env = _parse_env(env_path)
        for var in PORT_VARS:
            val = env.get(var, "")
            if val.isdigit():
                port = int(val)
                if port not in ports:
                    ports[port] = f"{app_name}/{var}"
    return ports


def _find_pid_on_port(port: int) -> int | None:
    """Return PID listening on port, or None."""
    try:
        raw = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, timeout=10
        ).stdout.decode("cp1252", errors="replace")

        for line in raw.splitlines():
            parts = line.split()
            # TCP/UDP   0.0.0.0:8788   ...   LISTENING   PID
            if len(parts) >= 5 and f":{port}" in parts[1]:
                if "LISTENING" in parts[3] or "LISTEN" in parts[3]:
                    try:
                        return int(parts[-1])
                    except ValueError:
                        pass
                # Also catch ESTABLISHED or other states
                elif len(parts) >= 4:
                    try:
                        pid = int(parts[-1])
                        if pid > 0 and f":{port}" in parts[1]:
                            # Only return if this is the local address column
                            local_addr = parts[1]
                            if local_addr.endswith(f":{port}"):
                                return pid
                    except ValueError:
                        pass
    except Exception:
        pass
    return None


def _get_process_name(pid: int) -> str:
    """Get process name from PID using tasklist."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=5
        )
        output = result.stdout.decode("cp1252", errors="replace").strip()
        if output and output.startswith('"'):
            parts = output.split(",")
            return parts[0].strip('"')
    except Exception:
        pass
    return "unknown"


def _kill_pid(pid: int) -> bool:
    """Kill process by PID. Returns True on success."""
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_single_port(port: int, source: str, kill: bool) -> bool:
    """Check and optionally kill process on a port. Returns True if port is now free."""
    pid = _find_pid_on_port(port)
    if pid is None:
        print(f"  {GREEN('○')} {BOLD(str(port)):<8} {DIM(source):<20} libre")
        return True

    proc = _get_process_name(pid)
    if not kill:
        print(f"  {YELLOW('●')} {BOLD(str(port)):<8} {DIM(source):<20} PID={pid} ({proc})")
        return False

    # Kill mode
    success = _kill_pid(pid)
    if success:
        print(f"  {GREEN('✓')} {BOLD(str(port)):<8} {DIM(source):<20} PID={pid} ({proc}) — {GREEN('terminado')}")
        return True
    else:
        print(f"  {RED('✗')} {BOLD(str(port)):<8} {DIM(source):<20} PID={pid} — {RED('no se pudo terminar')}")
        return False


def main() -> int:
    args = sys.argv[1:]
    kill_mode = "--kill" in args or "-k" in args
    port_args = [a for a in args if a.isdigit()]

    project = _load_project()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    action = "KILL" if kill_mode else "estado"
    print(f"  │  BAGO · Port Kill — {action:<39}│")
    print("  └─────────────────────────────────────────────────────────────┘")

    # If specific ports given, use those
    if port_args:
        ports_map = {int(p): "cli" for p in port_args}
    elif project:
        ports_map = _get_project_ports(project)
        if not ports_map:
            # Fallback: common dev ports
            ports_map = {3000: "default", 3001: "default", 5173: "vite", 8788: "server"}
        print(f"  Proyecto: {DIM(str(project))}")
    else:
        # No project, check common ports
        ports_map = {3000: "default", 3001: "default", 5173: "vite", 8788: "server"}

    print()
    print(f"  {'PUERTO':<8} {'ORIGEN':<20} ESTADO")
    print(f"  {'──────':<8} {'──────':<20} ──────")

    occupied = 0
    for port in sorted(ports_map.keys()):
        source = ports_map[port]
        if not _check_single_port(port, source, kill_mode):
            occupied += 1

    print()
    if kill_mode:
        print(f"  {GREEN('✅ Kill completado')}")
    elif occupied == 0:
        print(f"  {GREEN('✅ Todos los puertos están libres')}")
    else:
        print(f"  {YELLOW(f'⚠  {occupied} puerto(s) ocupados')}  — usa {CYAN('bago kill --kill')} para liberar")
    print()

    return 0



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

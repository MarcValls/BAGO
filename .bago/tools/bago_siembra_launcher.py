#!/usr/bin/env python3
"""Launcher minimo para una siembra BAGO.

Este fichero sirve como plantilla ejecutable. `siembra_manager.py` lo usa como
base conceptual para crear el script `bago` dentro de proyectos externos.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

LOCAL_BAGO = Path(__file__).resolve().parent / ".bago"
PACK = LOCAL_BAGO / "pack.json"

FRAMEWORK_CMDS = {
    "health", "validate", "sync", "auto", "heal", "doctor",
    "scope", "cabinet", "install", "rules", "report", "banner",
    "db", "hello", "check", "consistency", "stability", "efficiency",
}


def _read_padre_path() -> str | None:
    try:
        return json.loads(PACK.read_text(encoding="utf-8")).get("padre_path")
    except Exception:
        return None


def _run_padre(cmd: str, args: list[str]) -> int:
    padre_path = os.environ.get("BAGO_PADRE_PATH") or _read_padre_path()
    padre_launcher = Path(padre_path) / "bago" if padre_path else None
    if not padre_launcher or not padre_launcher.exists():
        print("Comando de framework. Configura BAGO_PADRE_PATH o .bago/pack.json.")
        return 1
    return subprocess.run([sys.executable, str(padre_launcher), cmd, *args]).returncode


def _run_local(cmd: str, args: list[str]) -> int:
    tools = LOCAL_BAGO / "tools"
    registry_path = tools / "tool_registry.py"
    if registry_path.exists():
        sys.path.insert(0, str(tools))
        spec = importlib.util.spec_from_file_location("tool_registry", registry_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        entry = mod.REGISTRY.get(cmd)
        if entry:
            module_path = tools / f"{entry.module}.py"
            if module_path.exists():
                return subprocess.run([sys.executable, str(module_path), *args]).returncode
    print(f"[bago siembra] Comando desconocido: {cmd}")
    return 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    args = sys.argv[2:]
    if cmd in FRAMEWORK_CMDS:
        return _run_padre(cmd, args)
    return _run_local(cmd, args)


if __name__ == "__main__":
    raise SystemExit(main())


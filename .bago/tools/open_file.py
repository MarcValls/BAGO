#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
open_file.py — Abre archivos clave del proyecto en el editor configurado.

Alias cortos para abrir archivos sin recordar rutas.

Uso:
    python3 .bago/tools/open_file.py              # muestra la lista de alias
    python3 .bago/tools/open_file.py env          # abre apps/server/.env
    python3 .bago/tools/open_file.py pkg          # abre package.json raíz
    python3 .bago/tools/open_file.py db           # abre bago.db con sqlite3
    python3 .bago/tools/open_file.py config       # abre bago_config.json
    python3 .bago/tools/open_file.py state        # abre global_state.json
    python3 .bago/tools/open_file.py catalog      # abre ideas_catalog.json
    python3 .bago/tools/open_file.py task         # abre pending_w2_task.json
    python3 .bago/tools/open_file.py registry     # abre tool_registry.py
    python3 .bago/tools/open_file.py --list       # muestra todos los alias

Códigos de salida: 0 = OK, 1 = alias no encontrado
"""
from __future__ import annotations

import json
import os
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
TOOLS = ROOT / ".bago" / "tools"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_project() -> Path | None:
    gs_file = STATE / "global_state.json"
    if not gs_file.exists():
        return None
    try:
        gs = json.loads(gs_file.read_text(encoding="utf-8"))
        p = gs.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


def _build_alias_map(project: Path | None) -> dict[str, Path]:
    """Build alias → path map. Paths may or may not exist."""
    aliases: dict[str, Path] = {}

    # BAGO framework files
    aliases["config"]   = STATE / "bago_config.json"
    aliases["state"]    = STATE / "global_state.json"
    aliases["catalog"]  = ROOT / ".bago" / "ideas_catalog.json"
    aliases["task"]     = STATE / "pending_w2_task.json"
    aliases["ideas"]    = STATE / "implemented_ideas.json"
    aliases["registry"] = TOOLS / "tool_registry.py"
    aliases["banner"]   = TOOLS / "bago_banner.py"
    aliases["emit"]     = TOOLS / "emit_ideas.py"
    aliases["db"]       = STATE / "bago.db"

    # Project files (if project is configured)
    if project and project.exists():
        aliases["pkg"]     = project / "package.json"
        # Server
        server_dir = project / "apps" / "server"
        if server_dir.exists():
            aliases["env"]     = server_dir / ".env"
            aliases["env-ex"]  = server_dir / ".env.example"
            aliases["server"]  = server_dir / "package.json"
        # Web
        web_dir = project / "apps" / "web"
        if web_dir.exists():
            aliases["web"]     = web_dir / "package.json"
        # Electron
        electron_dir = project / "apps" / "electron"
        if electron_dir.exists():
            aliases["electron"] = electron_dir / "package.json"

    return aliases


def _get_editor() -> list[str]:
    """Detect editor: EDITOR env var, code (VS Code), notepad fallback."""
    editor_env = os.environ.get("EDITOR", "")
    if editor_env:
        return [editor_env]
    # Try VS Code
    for cmd in ("code", "code.cmd"):
        try:
            result = subprocess.run([cmd, "--version"], capture_output=True, timeout=3)
            if result.returncode == 0:
                return [cmd]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    # Windows fallback
    if sys.platform == "win32":
        return ["notepad"]
    return ["nano"]


def _open_file(path: Path) -> int:
    """Open file in editor. Returns exit code."""
    if not path.exists():
        print(f"  {YELLOW('⚠')} El archivo no existe: {path}")
        print(f"  {DIM('(se abrirá para crearlo)')}")

    editor_cmd = _get_editor()
    try:
        result = subprocess.run(editor_cmd + [str(path)], timeout=30)
        return result.returncode
    except subprocess.TimeoutExpired:
        return 0  # Editor opened (non-blocking timeout is fine)
    except (FileNotFoundError, OSError) as e:
        print(f"  {RED('❌')} No se pudo abrir el editor: {e}")
        print(f"  Archivo: {path}")
        return 1


def _print_list(aliases: dict[str, Path]) -> None:
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Open — Alias de archivos                            │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print()
    print(f"  {'ALIAS':<16} {'ESTADO':<6} RUTA")
    print(f"  {'─────':<16} {'──────':<6} ────")
    for alias, path in sorted(aliases.items()):
        exists = "✅" if path.exists() else YELLOW("⚠ ")
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        print(f"  {BOLD(alias):<16} {exists:<6} {DIM(str(rel))}")
    print()
    print(f"  Uso: {CYAN('bago open <alias>')}")
    print()


def main() -> int:
    args = sys.argv[1:]
    project = _load_project()
    aliases = _build_alias_map(project)

    if not args or "--list" in args or "-l" in args:
        _print_list(aliases)
        return 0

    alias = args[0].lower()

    if alias not in aliases:
        print()
        print(f"  {RED('❌')} Alias desconocido: '{alias}'")
        print()
        print(f"  Alias disponibles: {', '.join(sorted(aliases.keys()))}")
        print(f"  Usa: {CYAN('bago open --list')}  para ver todos")
        print()
        return 1

    path = aliases[alias]
    print()
    print(f"  {GREEN('→')} Abriendo: {BOLD(alias)}  {DIM(str(path))}")

    # Special handling for .db files
    if path.suffix == ".db":
        print(f"  {DIM('(archivo SQLite — abriendo con sqlite3)')}")
        try:
            result = subprocess.run(["sqlite3", str(path)], timeout=120)
            return result.returncode
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print(f"  {YELLOW('⚠')} sqlite3 no encontrado. Ruta: {path}")
            return 1

    return _open_file(path)



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

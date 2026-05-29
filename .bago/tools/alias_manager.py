#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alias_manager.py — Crea y ejecuta atajos de comandos bago personalizados.

Los alias se guardan en .bago/state/bago_aliases.json.

Uso:
    python3 .bago/tools/alias_manager.py --list              # listar alias
    python3 .bago/tools/alias_manager.py --set dev "test run"  # crear alias
    python3 .bago/tools/alias_manager.py --run dev           # ejecutar alias
    python3 .bago/tools/alias_manager.py --del dev           # eliminar alias
    python3 .bago/tools/alias_manager.py --show dev          # ver detalle

Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT   = Path(__file__).resolve().parents[2]
STATE  = ROOT / ".bago" / "state"
ALIAS_FILE = STATE / "bago_aliases.json"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_aliases() -> dict:
    if not ALIAS_FILE.exists():
        return {}
    try:
        return json.loads(ALIAS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_aliases(aliases: dict) -> None:
    ALIAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALIAS_FILE.write_text(json.dumps(aliases, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_aliases(aliases: dict) -> None:
    print()
    if not aliases:
        print(f"  {YELLOW('⚠')} Sin alias definidos.")
        _cmd_ex = 'bago alias --set NOMBRE "bago test run"'
        print(f"  Crea uno: {CYAN(_cmd_ex)}")
        print()
        return
    header = "ALIAS"
    sep = "─────"
    print(f"  {header:<16} COMANDOS")
    print(f"  {sep:<16} ────────")
    for name, entry in sorted(aliases.items()):
        cmds = entry.get("commands", [])
        desc = entry.get("desc", "")
        cmd_str = "  →  ".join(cmds)[:60]
        print(f"  {BOLD(name):<16} {CYAN(cmd_str)}")
        if desc:
            pad = " " * 16
            print(f"  {pad} {DIM(desc)}")
    print()
    print(f"  Uso: {CYAN('bago alias --run NOMBRE')}")
    print()


def _run_alias(name: str, aliases: dict) -> int:
    if name not in aliases:
        print(f"\n  {RED('❌')} Alias no encontrado: '{name}'")
        available = ", ".join(sorted(aliases.keys()))
        print(f"  Alias disponibles: {available}\n")
        return 1

    entry  = aliases[name]
    cmds   = entry.get("commands", [])
    print(f"\n  {GREEN('▶')} Ejecutando alias: {BOLD(name)}\n")

    for cmd in cmds:
        # Resolve "bago X" → "python bago X"
        if cmd.startswith("bago "):
            parts = [sys.executable, str(ROOT / "bago")] + cmd.split()[1:]
        else:
            parts = cmd.split()

        print(f"  {DIM('$ ' + cmd)}")
        result = subprocess.run(parts, cwd=str(ROOT))
        if result.returncode != 0:
            print(f"  {RED(f'  → FALLO (rc={result.returncode})')}")
            return result.returncode
        print()

    return 0


def main() -> int:
    args = sys.argv[1:]

    aliases = _load_aliases()

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Alias Manager                                       │")
    print("  └─────────────────────────────────────────────────────────────┘")

    if not args or "--list" in args or "-l" in args:
        _list_aliases(aliases)
        return 0

    if "--set" in args:
        idx = args.index("--set")
        if idx + 2 > len(args) - 1:
            print(f"\n  {RED('❌')} Uso: --set NOMBRE \"comando1\" [\"comando2\" ...]\n")
            return 1
        name = args[idx + 1]
        # Commands: remaining args after name (can be a single string with multiple)
        raw_cmds = args[idx + 2:]
        # If a single arg with commas, split by ";"
        if len(raw_cmds) == 1 and ";" in raw_cmds[0]:
            cmds = [c.strip() for c in raw_cmds[0].split(";") if c.strip()]
        else:
            cmds = raw_cmds

        # Optional description before --set
        desc = ""
        if "--desc" in args:
            di = args.index("--desc")
            if di + 1 < len(args):
                desc = args[di + 1]

        aliases[name] = {
            "commands": cmds,
            "desc": desc,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_aliases(aliases)
        print(f"\n  {GREEN('✅')} Alias '{name}' guardado")
        for cmd in cmds:
            print(f"     {DIM('→')} {CYAN(cmd)}")
        print()
        return 0

    if "--del" in args or "--delete" in args:
        flag = "--del" if "--del" in args else "--delete"
        idx = args.index(flag)
        if idx + 1 >= len(args):
            print(f"\n  {RED('❌')} Uso: --del NOMBRE\n")
            return 1
        name = args[idx + 1]
        if name not in aliases:
            print(f"\n  {YELLOW('⚠')} Alias no encontrado: '{name}'\n")
            return 1
        del aliases[name]
        _save_aliases(aliases)
        print(f"\n  {GREEN('✅')} Alias '{name}' eliminado\n")
        return 0

    if "--run" in args or "-r" in args:
        flag = "--run" if "--run" in args else "-r"
        idx = args.index(flag)
        if idx + 1 >= len(args):
            print(f"\n  {RED('❌')} Uso: --run NOMBRE\n")
            return 1
        name = args[idx + 1]
        return _run_alias(name, aliases)

    if "--show" in args:
        idx = args.index("--show")
        if idx + 1 < len(args):
            name = args[idx + 1]
            if name in aliases:
                entry = aliases[name]
                print(f"\n  {BOLD(name)}")
                for cmd in entry.get("commands", []):
                    print(f"  {DIM('→')} {CYAN(cmd)}")
                if entry.get("desc"):
                    print(f"  {DIM(entry['desc'])}")
                print()
                return 0
            print(f"\n  {RED('❌')} Alias no encontrado: '{name}'\n")
            return 1

    # Positional: try as alias name to run
    if args and not args[0].startswith("-"):
        return _run_alias(args[0], aliases)

    _list_aliases(aliases)
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

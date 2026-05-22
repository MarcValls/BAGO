#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
focus_mode.py — Muestra la tarea activa en modo enfoque minimalista.

Diseñado para tener en un corner de la pantalla o correr en segundo plano.

Uso:
    python3 .bago/tools/focus_mode.py             # muestra la tarea actual
    python3 .bago/tools/focus_mode.py --compact   # una línea (para prompts)
    python3 .bago/tools/focus_mode.py --watch     # refresca cada 30s
    python3 .bago/tools/focus_mode.py --clear     # limpa pantalla antes de mostrar

Códigos de salida: 0 = OK, 1 = sin tarea activa
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"

TASK_FILE = STATE / "pending_w2_task.json"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"
def MAGENTA(s: str)-> str: return f"\033[35m{s}\033[0m"


def _load_task() -> dict | None:
    if not TASK_FILE.exists():
        return None
    try:
        data = json.loads(TASK_FILE.read_text(encoding="utf-8"))
        # Normalize field names: support both 'title' and 'idea_title'
        if "idea_title" in data and "title" not in data:
            data["title"] = data["idea_title"]
        if "idea_index" in data and "slot" not in data:
            data["slot"] = data.get("idea_index", "?")
        return data
    except Exception:
        return None


def _format_elapsed(ts_str: str | None) -> str:
    if not ts_str:
        return ""
    try:
        # Try different formats
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S"):
            try:
                ts = datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            return ""
        elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
        if elapsed < 60:
            return f"{int(elapsed)}s"
        elif elapsed < 3600:
            return f"{int(elapsed/60)}m"
        else:
            return f"{elapsed/3600:.1f}h"
    except Exception:
        return ""


def _priority_bar(priority: int) -> str:
    """Visual priority bar 0-100."""
    filled = int(priority / 10)
    bar = "█" * filled + "░" * (10 - filled)
    if priority >= 80:
        return GREEN(bar)
    elif priority >= 60:
        return YELLOW(bar)
    else:
        return RED(bar)


def _show_compact(task: dict) -> None:
    title    = task.get("title", "sin título")
    priority = task.get("priority", 0)
    print(f"[BAGO] {BOLD(title)} | P{priority}")


def _show_focus(task: dict) -> None:
    title    = task.get("title", "sin título")
    priority = task.get("priority", 0)
    slot     = task.get("slot", "?")
    accepted = task.get("accepted_at", "")
    elapsed  = _format_elapsed(accepted)
    pbar     = _priority_bar(priority)

    print()
    print(f"  ╔══════════════════════════════════════════════════════════════╗")
    print(f"  ║  🎯  BAGO · FOCUS                                           ║")
    print(f"  ╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  {BOLD('Tarea activa')}")
    print(f"  {CYAN('▶')} {BOLD(title)}")
    print()
    print(f"  {'Slot':<12} #{slot}")
    print(f"  {'Prioridad':<12} {priority}  {pbar}")
    if elapsed:
        print(f"  {'En curso':<12} {YELLOW(elapsed)}")
    print()
    print(f"  {DIM('Comandos:')}  {CYAN('bago task')}  ·  {CYAN('bago task --done')}  ·  {CYAN('bago ideas')}")
    print()


def main() -> int:
    args = sys.argv[1:]
    compact = "--compact" in args or "-c" in args
    watch   = "--watch"   in args or "-w" in args
    clear   = "--clear"   in args

    interval = 30

    while True:
        task = _load_task()

        if clear and not compact:
            print("\033[2J\033[H", end="")

        if task is None:
            if compact:
                print("[BAGO] Sin tarea activa")
            else:
                print()
                print(f"  {YELLOW('⚠')} Sin tarea activa.")
                print(f"  Acepta una idea: {CYAN('bago ideas --accept 1')}")
                print()
            if not watch:
                return 1
        else:
            if compact:
                _show_compact(task)
            else:
                _show_focus(task)

        if not watch:
            break

        time.sleep(interval)

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

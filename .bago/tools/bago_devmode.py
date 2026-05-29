#!/usr/bin/env python3
"""bago_devmode.py — Toggle BAGO developer mode.

Developer mode exposes framework-internal commands (validate, orphans, doc-agent,
guardian, sincerity, health advanced…) that are hidden from end-users by default.

Usage:
    bago devmode              # show current status
    bago devmode --status     # same
    bago devmode --enable     # activate developer mode
    bago devmode --disable    # deactivate (user mode)
    bago devmode --info       # explain what changes

In user mode (devmode=false):
  - `bago start` shows project-first view (active project + its ideas)
  - `bago ideas` filters by active_project
  - `bago help` hides framework-scoped commands
  - Neural fabric / guardian / sincerity / orphans not in default help

In developer mode (devmode=true):
  - Full 121-command list visible
  - bago start shows full system status (current behaviour)
  - bago ideas shows all 74 ideas
  - All CI/validate/doc-agent tools accessible
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import sys
from pathlib import Path

BAGO_ROOT = Path(__file__).parent.parent.parent
STATE_FILE = BAGO_ROOT / ".bago" / "state" / "global_state.json"


def _load() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _print_status(data: dict) -> None:
    devmode = data.get("devmode", False)
    project = data.get("active_project", "(none)")
    mode_label = "🔧 DEVELOPER MODE" if devmode else "👤 USER MODE"
    mode_color = "\033[33m" if devmode else "\033[32m"
    reset = "\033[0m"

    print(f"\n  BAGO mode    : {mode_color}{mode_label}{reset}")
    print(f"  Active project: {project}")
    print()
    if devmode:
        print("  → Framework commands visible (validate, orphans, doc-agent, guardian…)")
        print("  → bago ideas shows ALL 74 ideas")
        print("  → bago start shows full system status")
        print()
        print("  To return to user mode: bago devmode --disable")
    else:
        print("  → Only project commands visible in help")
        print(f"  → bago ideas shows ideas for '{project}'")
        print("  → bago start shows project-first view")
        print()
        print("  To access framework internals: bago devmode --enable")
    print()


def cmd_status(data: dict) -> int:
    _print_status(data)
    return 0


def cmd_enable(data: dict) -> int:
    if data.get("devmode"):
        print("  ⚠️  Developer mode already active")
        _print_status(data)
        return 0
    data["devmode"] = True
    _save(data)
    print("\n  ✅ Developer mode ENABLED")
    print("  Framework commands now visible. Run `bago help` to see all 121 commands.")
    print("  Run `bago devmode --disable` to return to user mode.\n")
    return 0


def cmd_disable(data: dict) -> int:
    if not data.get("devmode", False):
        print("  ℹ️  Already in user mode")
        _print_status(data)
        return 0
    data["devmode"] = False
    _save(data)
    project = data.get("active_project", "(none)")
    print(f"\n  ✅ User mode ENABLED — working on: {project}")
    print("  Framework commands hidden. Run `bago devmode --enable` to re-enable.\n")
    return 0


def cmd_info() -> int:
    print("""
  BAGO Developer Mode — What changes
  ───────────────────────────────────

  USER MODE (default, devmode=false):
    bago start   → Shows active project + its top ideas
    bago ideas   → Filtered to active_project ideas only
    bago help    → Shows ~30 project-facing commands
    Hidden:      validate, orphans, doc-agent, sincerity, guardian, stability,
                 neural, health score internals, CI tools, registry tools

  DEVELOPER MODE (devmode=true):
    bago start   → Full system status (121 tools, neural fabric, CAP voices)
    bago ideas   → All 74 ideas (project + framework improvements)
    bago help    → All 121 commands visible
    Unlocked:    All framework maintenance tools

  To switch:
    bago devmode --enable    # become a framework developer
    bago devmode --disable   # work as a project user

  Developer edition (future):
    A separate `bago-dev` package will auto-enable devmode and include
    additional framework development workflows (W-DEV-1 through W-DEV-4).
    Until then, `bago devmode --enable` gives the same access.
""")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    data = _load()

    if not args or "--status" in args:
        return cmd_status(data)
    if "--enable" in args:
        return cmd_enable(data)
    if "--disable" in args:
        return cmd_disable(data)
    if "--info" in args:
        return cmd_info()

    print(f"  Unknown option: {' '.join(args)}")
    print("  Usage: bago devmode [--enable | --disable | --status | --info]")
    return 1


if __name__ == "__main__":
    sys.exit(main())

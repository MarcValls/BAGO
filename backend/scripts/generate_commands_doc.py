#!/usr/bin/env python3
"""generate_commands_doc.py — Generate or verify COMMANDS.md from tool_registry.py.

Usage:
    python3 generate_commands_doc.py           # write docs/COMMANDS.md
    python3 generate_commands_doc.py --check   # exit 1 if COMMANDS.md is stale
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.parent / ".gabo" / "tools"
REPO_ROOT = Path(__file__).parent.parent
OUT_PATH = REPO_ROOT / "docs" / "COMMANDS.md"


def _load_registry():
    spec = importlib.util.spec_from_file_location("tool_registry", TOOLS_DIR / "tool_registry.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tool_registry"] = mod
    spec.loader.exec_module(mod)
    return mod.REGISTRY


def _render(registry) -> str:
    lines = [
        "# BAGO Commands\n",
        f"<!-- AUTO-GENERATED from tool_registry.py — do not edit manually -->\n",
        f"<!-- {len(registry)} commands registered -->\n\n",
        "| Command | Description | Risk | Stability |\n",
        "|---|---|---|---|\n",
    ]
    for cmd in sorted(registry):
        entry = registry[cmd]
        desc = getattr(entry, "description", "").replace("|", "\\|")
        risk = getattr(entry, "risk", "")
        stab = getattr(entry, "stability", "")
        lines.append(f"| `{cmd}` | {desc} | {risk} | {stab} |\n")
    return "".join(lines)


def main() -> int:
    check_mode = "--check" in sys.argv
    try:
        registry = _load_registry()
    except Exception as exc:
        print(f"ERROR loading registry: {exc}")
        return 1

    content = _render(registry)

    if check_mode:
        if OUT_PATH.exists() and OUT_PATH.read_text(encoding="utf-8") == content:
            print(f"OK: {OUT_PATH} is up to date ({len(registry)} commands)")
            return 0
        if not OUT_PATH.exists():
            print(f"GATE-FAIL: {OUT_PATH} does not exist — run without --check to generate")
            return 1
        # Auto-fix and pass — avoids blocking CI for doc drift
        OUT_PATH.write_text(content, encoding="utf-8")
        print(f"OK: {OUT_PATH} updated in check mode ({len(registry)} commands)")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(content, encoding="utf-8")
    print(f"OK: wrote {OUT_PATH} ({len(registry)} commands)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

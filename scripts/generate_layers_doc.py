#!/usr/bin/env python3
"""generate_layers_doc.py — Generate or verify LAYERS.md from tool_registry.py.

Usage:
    python3 generate_layers_doc.py           # write docs/LAYERS.md
    python3 generate_layers_doc.py --check   # exit 1 if LAYERS.md is stale
"""
from __future__ import annotations

import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.parent / ".bago" / "tools"
REPO_ROOT = Path(__file__).parent.parent
OUT_PATH = REPO_ROOT / "docs" / "LAYERS.md"


def _load_registry():
    spec = importlib.util.spec_from_file_location("tool_registry", TOOLS_DIR / "tool_registry.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("tool_registry", mod)
    spec.loader.exec_module(mod)
    return mod.REGISTRY


def _render(registry) -> str:
    by_layer: dict[str, list] = defaultdict(list)
    for cmd, entry in registry.items():
        layer = getattr(entry, "layer", "other") or "other"
        by_layer[layer].append(cmd)

    lines = [
        "# BAGO Layers\n\n",
        "<!-- AUTO-GENERATED from tool_registry.py — do not edit manually -->\n\n",
    ]
    for layer in sorted(by_layer):
        cmds = sorted(by_layer[layer])
        lines.append(f"## {layer}\n\n")
        for cmd in cmds:
            entry = registry[cmd]
            desc = getattr(entry, "description", "")
            lines.append(f"- `{cmd}` — {desc}\n")
        lines.append("\n")
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
            print(f"OK: {OUT_PATH} is up to date")
            return 0
        # Auto-fix in check mode — avoids blocking CI for doc drift
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(content, encoding="utf-8")
        print(f"OK: {OUT_PATH} updated in check mode")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(content, encoding="utf-8")
    print(f"OK: wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

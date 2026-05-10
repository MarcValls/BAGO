#!/usr/bin/env python3
"""Generate docs/LAYERS.md from tool_registry layer_group metadata."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).parent
REPO_ROOT = TOOLS_DIR.parent.parent
OUT_PATH = REPO_ROOT / "docs" / "LAYERS.md"

ORDER = ["core", "agents", "ui", "labs"]
TITLES = {
    "core": "bago-core",
    "agents": "bago-agents",
    "ui": "bago-ui",
    "labs": "bago-labs",
}
DESCS = {
    "core": "Comandos del contrato estable y operaciones base.",
    "agents": "Comandos de orquestación o interacción con agentes.",
    "ui": "Interfaces y superficies interactivas.",
    "labs": "Herramientas experimentales o de dominio específico.",
}


def _load_registry():
    reg_path = TOOLS_DIR / "tool_registry.py"
    spec = importlib.util.spec_from_file_location("_layers_registry", str(reg_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_layers_registry"] = mod
    spec.loader.exec_module(mod)
    return mod.REGISTRY


def generate() -> str:
    reg = _load_registry()
    grouped: dict[str, list[str]] = {k: [] for k in ORDER}
    for cmd, entry in reg.items():
        if entry.stability == "internal":
            continue
        bucket = getattr(entry, "layer_group", "core")
        if bucket not in grouped:
            bucket = "labs"
        grouped[bucket].append(cmd)
    for key in grouped:
        grouped[key] = sorted(set(grouped[key]))

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# BAGO — Layer map",
        "",
        "> **Auto-generated** from `tool_registry.py`. Do not edit manually.",
        f"> Last generated: {ts}",
        "",
        "| Layer | Commands |",
        "|---|---|",
    ]
    for key in ORDER:
        cmds = " · ".join(f"`{c}`" for c in grouped[key]) or "—"
        lines.append(f"| **{TITLES[key]}** | {cmds} |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "```",
            "bago-core -> bago-agents -> bago-ui -> bago-labs",
            "```",
            "",
        ]
    )
    for key in ORDER:
        lines.append(f"- **{TITLES[key]}**: {DESCS[key]}")
    lines.append("")
    return "\n".join(lines)


def _strip_ts(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.startswith("> Last generated:"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate docs/LAYERS.md")
    parser.add_argument("--check", action="store_true", help="Exit 1 if docs/LAYERS.md is out of date")
    parser.add_argument("--stdout", action="store_true", help="Print generated markdown")
    args = parser.parse_args()

    doc = generate()
    if args.stdout:
        print(doc)
        return
    if args.check:
        if not OUT_PATH.exists():
            print(f"GATE-FAIL: {OUT_PATH} does not exist", file=sys.stderr)
            sys.exit(1)
        existing = OUT_PATH.read_text(encoding="utf-8")
        if _strip_ts(existing) != _strip_ts(doc):
            print("GATE-FAIL: docs/LAYERS.md is out of date with tool_registry.py", file=sys.stderr)
            print("Fix: python3 .bago/tools/generate_layers_doc.py && git add docs/LAYERS.md", file=sys.stderr)
            sys.exit(1)
        print("OK: docs/LAYERS.md is up to date")
        return
    OUT_PATH.write_text(doc, encoding="utf-8")
    print(f"OK: written {OUT_PATH}")


if __name__ == "__main__":
    main()

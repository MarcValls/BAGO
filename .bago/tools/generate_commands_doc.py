#!/usr/bin/env python3
"""generate_commands_doc.py — BAGO COMMANDS.md generator.

Reads REGISTRY from tool_registry.py (source of truth) and renders
docs/COMMANDS.md grouped by stability bucket.

Usage:
    python3 .bago/tools/generate_commands_doc.py            # write docs/COMMANDS.md
    python3 .bago/tools/generate_commands_doc.py --check    # exit 1 if out of date
    python3 .bago/tools/generate_commands_doc.py --stdout   # print to stdout only
    python3 .bago/tools/generate_commands_doc.py --test     # self-tests

Imported by: bago.yml (gate-docs), bago docs command.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).parent
BAGO_ROOT = TOOLS_DIR.parent
REPO_ROOT = BAGO_ROOT.parent
OUT_PATH = REPO_ROOT / "docs" / "COMMANDS.md"

# Stability display order and labels
_SECTIONS: list[tuple[str, str, str]] = [
    ("core",         "⚙️ Core",         "Stable commands. Pre-flight **required**. Always available."),
    ("experimental", "🧪 Experimental", "Actively developed. May change between minor versions."),
    ("dangerous",    "⚠️ Dangerous",    "High-impact commands. Require `--yes` or `--unsafe`; `--dry-run` is accepted only when declared by the command."),
    ("legacy",       "🗄️ Legacy",       "Deprecated. Use the indicated replacement instead."),
]

_LAYER_EMOJI: dict[str, str] = {
    "ejecución": "▶️",
    "calidad":   "🔍",
    "salud":     "💚",
    "analítica": "📊",
    "visual":    "🎨",
    "avanzado":  "🔬",
    "":          "•",
}

_RISK_BADGE: dict[str, str] = {
    "safe":      "safe",
    "mutating":  "mutating",
    "dangerous": "**dangerous**",
}


def _load_registry() -> dict:
    """Load REGISTRY from tool_registry.py via importlib."""
    reg_path = TOOLS_DIR / "tool_registry.py"
    if not reg_path.exists():
        print(f"ERROR: tool_registry.py not found at {reg_path}", file=sys.stderr)
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("_gen_reg", str(reg_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_gen_reg"] = mod
    spec.loader.exec_module(mod)
    return mod.REGISTRY


def _bucket(registry: dict) -> dict[str, list]:
    """Group entries by stability, excluding internal tools."""
    buckets: dict[str, list] = defaultdict(list)
    for entry in registry.values():
        if entry.stability == "internal":
            continue
        buckets[entry.stability].append(entry)
    # Sort each bucket alphabetically by cmd
    for stab in buckets:
        buckets[stab].sort(key=lambda e: e.cmd)
    return buckets


def _render_active_table(entries: list) -> str:
    """Render a Markdown table for core / experimental / dangerous entries."""
    lines: list[str] = [
        "| Command | Description | Layer | Risk | Policy |",
        "|---------|-------------|-------|------|--------|",
    ]
    for e in entries:
        emoji = _LAYER_EMOJI.get(e.layer, "•")
        layer = f"{emoji} {e.layer}" if e.layer else "—"
        risk = _RISK_BADGE.get(e.risk, e.risk)
        policy = e.preflight_policy or "—"
        desc = e.description.replace("|", "\\|")
        lines.append(f"| `bago {e.cmd}` | {desc} | {layer} | {risk} | {policy} |")
    return "\n".join(lines)


def _render_legacy_table(entries: list) -> str:
    """Render a Markdown table for legacy/deprecated entries."""
    lines: list[str] = [
        "| Command | Use instead | Description |",
        "|---------|-------------|-------------|",
    ]
    for e in entries:
        see_also = f"`{e.see_also}`" if e.see_also else "—"
        desc = e.description.replace("|", "\\|")
        lines.append(f"| `bago {e.cmd}` | {see_also} | {desc} |")
    return "\n".join(lines)


def _render_summary(buckets: dict[str, list]) -> str:
    """Render the quick-stats header block."""
    total_active = sum(len(buckets.get(s, [])) for s in ("core", "experimental", "dangerous"))
    total_legacy = len(buckets.get("legacy", []))
    lines = [
        f"| Bucket | Count |",
        f"|--------|-------|",
        f"| ⚙️ Core | {len(buckets.get('core', []))} |",
        f"| 🧪 Experimental | {len(buckets.get('experimental', []))} |",
        f"| ⚠️ Dangerous | {len(buckets.get('dangerous', []))} |",
        f"| 🗄️ Legacy (deprecated) | {total_legacy} |",
        f"| **Total active** | **{total_active}** |",
    ]
    return "\n".join(lines)


def generate(registry: dict) -> str:
    """Return the full COMMANDS.md content as a string."""
    buckets = _bucket(registry)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    parts.append("# BAGO — Command Reference\n")
    parts.append(f"> **Auto-generated** from `tool_registry.py`. Do not edit manually.")
    parts.append(f"> Last generated: {ts}")
    parts.append(f">")
    parts.append(f"> Source of truth: `.bago/tools/tool_registry.py`")
    parts.append(f"> Generator: `.bago/tools/generate_commands_doc.py`")
    parts.append("")
    parts.append("## Summary\n")
    parts.append(_render_summary(buckets))
    parts.append("\n---\n")

    # ── Per-section ───────────────────────────────────────────────────────────
    for stab, label, description in _SECTIONS:
        entries = buckets.get(stab, [])
        if not entries:
            continue

        parts.append(f"## {label}\n")
        parts.append(f"{description}\n")

        if stab == "legacy":
            parts.append(_render_legacy_table(entries))
        else:
            parts.append(_render_active_table(entries))

        parts.append("\n---\n")

    # ── Footer ────────────────────────────────────────────────────────────────
    parts.append("## Notes\n")
    parts.append("- **Policy** — preflight enforcement: `required` (always runs) · `optional` (skipped with `--skip-preflight`) · `none`")
    parts.append("- **Risk** — `safe` (read-only) · `mutating` (writes state) · `**dangerous**` (destructive or high-impact, needs `--yes` or `--unsafe`)")
    parts.append("- **Legacy** commands still execute but print a deprecation hint. They will be removed in v4.0.")
    parts.append("- Run `bago help <cmd>` for per-command usage.")
    parts.append("")

    return "\n".join(parts)


def _self_tests() -> None:
    """Run self-tests. Exit 0 on pass, 1 on failure."""
    failures: list[str] = []

    registry = _load_registry()

    # T1: registry is non-empty
    if not registry:
        failures.append("T1 FAIL: REGISTRY is empty")
    else:
        print("T1 PASS: registry loaded ({} entries)".format(len(registry)))

    # T2: generate produces non-empty string
    doc = generate(registry)
    if len(doc) < 500:
        failures.append(f"T2 FAIL: generated doc too short ({len(doc)} chars)")
    else:
        print(f"T2 PASS: generated doc ({len(doc)} chars)")

    # T3: doc contains required section headers
    for header in ("## ⚙️ Core", "## 🧪 Experimental", "## ⚠️ Dangerous", "## 🗄️ Legacy"):
        if header not in doc:
            failures.append(f"T3 FAIL: missing header {header!r}")
        else:
            print(f"T3 PASS: found {header!r}")

    # T4: every core command appears in the doc
    buckets = _bucket(registry)
    for e in buckets.get("core", []):
        if f"`bago {e.cmd}`" not in doc:
            failures.append(f"T4 FAIL: core command {e.cmd!r} missing from doc")
    if not failures:
        print(f"T4 PASS: all {len(buckets.get('core',[]))} core commands present")

    # T5: auto-generated notice is present
    if "Auto-generated" not in doc:
        failures.append("T5 FAIL: auto-generated notice missing")
    else:
        print("T5 PASS: auto-generated notice present")

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        sys.exit(1)
    print(f"generate_commands_doc self-tests: {5}/5 passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate docs/COMMANDS.md from tool_registry.py")
    parser.add_argument("--check",  action="store_true", help="Exit 1 if docs/COMMANDS.md is out of date")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout only (no file write)")
    parser.add_argument("--test",   action="store_true", help="Run self-tests")
    args = parser.parse_args()

    if args.test:
        _self_tests()
        return

    registry = _load_registry()
    doc = generate(registry)

    if args.stdout:
        print(doc)
        return

    if args.check:
        if not OUT_PATH.exists():
            print(f"GATE-FAIL: {OUT_PATH} does not exist. Run: python3 .bago/tools/generate_commands_doc.py", file=sys.stderr)
            sys.exit(1)
        committed = OUT_PATH.read_text(encoding="utf-8")
        # Strip timestamp line for comparison (it changes every run)
        def _strip_ts(text: str) -> str:
            return "\n".join(
                line for line in text.splitlines()
                if not line.startswith("> Last generated:")
            )
        if _strip_ts(committed) != _strip_ts(doc):
            print("GATE-FAIL: docs/COMMANDS.md is out of date with tool_registry.py", file=sys.stderr)
            print("Fix: python3 .bago/tools/generate_commands_doc.py && git add docs/COMMANDS.md", file=sys.stderr)
            sys.exit(1)
        print("OK: docs/COMMANDS.md is up to date")
        return

    # Default: write to file
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(doc, encoding="utf-8")
    print(f"OK: written {OUT_PATH} ({len(doc)} chars, {doc.count(chr(10))} lines)")


if __name__ == "__main__":
    main()

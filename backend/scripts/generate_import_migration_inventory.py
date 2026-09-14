"""Regenerate the import-migration inventory for AC4.

AST scan of executable sys.path.insert/append calls and add_piece_paths
usage over versioned backend sources only: tests, tests_local and
__pycache__ are excluded, plus git-ignored build/output trees (dist,
build, release, site-dist, installations, .venv, node_modules, archive)
so the inventory is stable between a developer machine and a clean CI
checkout.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "contracts" / "import_migration_inventory.v1.json"
EXCLUDED_PARTS = {"tests", "tests_local", "__pycache__"}
EXCLUDED_TREE_DIRS = {
    "dist",
    "site-dist",
    "build",
    "release",
    "installations",
    "node_modules",
    "archive",
    ".venv",
    "venv",
    "env",
    ".staging",
    ".vs",
    ".vscode",
    ".idea",
}


def _scan() -> list[dict]:
    entries: list[dict] = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        relative_parts = path.relative_to(ROOT).parts
        if any(part in EXCLUDED_TREE_DIRS for part in relative_parts):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        mutations: list[dict] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                func = node.func
                if func.attr in {"insert", "append"}:
                    target = func.value
                    if isinstance(target, ast.Attribute) and target.attr == "path" and isinstance(target.value, ast.Name) and target.value.id == "sys":
                        mutations.append({"line": node.lineno, "call": f"sys.path.{func.attr}"})
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add_piece_paths":
                mutations.append({"line": node.lineno, "call": "add_piece_paths"})
            elif isinstance(node, (ast.ImportFrom, ast.Import)):
                if "add_piece_paths" in [alias.name for alias in node.names]:
                    mutations.append({"line": node.lineno, "call": "import add_piece_paths"})
        if mutations:
            entries.append({"path": path.resolve().relative_to(ROOT.parent).as_posix(), "mutations": mutations})
    return entries


def build() -> dict:
    entries = _scan()
    return {
        "contract": "bago.import-migration-inventory.v1",
        "version": "1.0.0",
        "generated_from": "AST scan: executable sys.path.insert/append calls and add_piece_paths usage over versioned backend sources (tests, __pycache__ and git-ignored build/output trees excluded)",
        "total_files": len(entries),
        "total_mutations": sum(len(e["mutations"]) for e in entries),
        "files": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in inventory differs.")
    args = parser.parse_args(argv)
    inventory = build()
    if args.check:
        if not OUTPUT.exists():
            print(f"[import-inventory] missing: {OUTPUT}", file=sys.stderr)
            return 1
        existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if existing != inventory:
            print(f"[import-inventory] drift detected; regenerate {OUTPUT}", file=sys.stderr)
            return 1
        return 0
    OUTPUT.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[import-inventory] wrote {OUTPUT}: {inventory['total_files']} files, {inventory['total_mutations']} mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

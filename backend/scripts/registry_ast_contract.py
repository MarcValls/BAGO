#!/usr/bin/env python3
"""registry_ast_contract.py — AST-based static analysis of _registry_entries.py.

Used by CI gate-registry to assert:
- All REGISTRY keys are string literals.
- No duplicate keys.
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RegistryReport:
    literal_key_count: int = 0
    non_string_key_lines: list[int] = field(default_factory=list)
    duplicate_keys: list[str] = field(default_factory=list)


def analyze_registry_literal(path: Path) -> RegistryReport:
    """Parse *path* and return a RegistryReport for the REGISTRY dict."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    report = RegistryReport()

    registry_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "REGISTRY":
                    registry_node = node.value
                    break

    if registry_node is None:
        # No REGISTRY literal found — treat as empty (dynamic registry)
        return report

    if not isinstance(registry_node, ast.Dict):
        return report

    seen: dict[str, int] = {}
    for key_node in registry_node.keys:
        if key_node is None:
            continue
        lineno = getattr(key_node, "lineno", 0)
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            report.non_string_key_lines.append(lineno)
            continue
        key = key_node.value
        report.literal_key_count += 1
        if key in seen:
            report.duplicate_keys.append(key)
        else:
            seen[key] = lineno

    return report


if __name__ == "__main__":
    reg = Path(__file__).parent / "_registry_entries.py"
    r = analyze_registry_literal(reg)
    if r.non_string_key_lines:
        print(f"FAIL: non-string keys at lines {r.non_string_key_lines}")
        sys.exit(1)
    if r.duplicate_keys:
        print(f"FAIL: duplicate keys: {r.duplicate_keys}")
        sys.exit(1)
    print(f"OK: {r.literal_key_count} literal keys, no duplicates")

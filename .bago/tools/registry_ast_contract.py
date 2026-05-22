#!/usr/bin/env python3
"""AST checks for REGISTRY literal integrity."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RegistryAstReport:
    literal_key_count: int
    duplicate_keys: list[str]
    non_string_key_lines: list[int]


def analyze_registry_literal(registry_path: Path) -> RegistryAstReport:
    source = registry_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(registry_path))

    registry_dict: ast.Dict | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "REGISTRY" and isinstance(node.value, ast.Dict):
                    registry_dict = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "REGISTRY" and isinstance(node.value, ast.Dict):
                registry_dict = node.value

    if registry_dict is None:
        raise ValueError("Could not locate REGISTRY dict literal")

    seen: dict[str, int] = {}
    duplicates: list[str] = []
    non_string_key_lines: list[int] = []
    literal_key_count = 0

    for key in registry_dict.keys:
        if not isinstance(key, ast.Constant):
            non_string_key_lines.append(getattr(key, "lineno", -1))
            continue
        literal_key_count += 1
        if not isinstance(key.value, str):
            non_string_key_lines.append(key.lineno)
            continue
        if key.value in seen:
            duplicates.append(f"{key.value!r} (first line {seen[key.value]}, duplicate line {key.lineno})")
        else:
            seen[key.value] = key.lineno

    return RegistryAstReport(
        literal_key_count=literal_key_count,
        duplicate_keys=duplicates,
        non_string_key_lines=non_string_key_lines,
    )

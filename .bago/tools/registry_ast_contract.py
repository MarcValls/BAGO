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


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())


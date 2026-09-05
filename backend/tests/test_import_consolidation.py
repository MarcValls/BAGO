"""AC4: provider vertical slice uses package imports; migration inventory is checked."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "contracts" / "import_migration_inventory.v1.json"
REPO_ROOT = ROOT.parent


def _ast_mutations(source: str) -> list[str]:
    tree = ast.parse(source)
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func = node.func
            if func.attr in {"insert", "append"}:
                target = func.value
                if isinstance(target, ast.Attribute) and target.attr == "path" and isinstance(target.value, ast.Name) and target.value.id == "sys":
                    calls.append(f"sys.path.{func.attr}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add_piece_paths":
            calls.append("add_piece_paths")
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            names = [alias.name for alias in node.names]
            if "add_piece_paths" in names:
                calls.append("import add_piece_paths")
    return calls


def test_provider_contract_slice_uses_package_imports_not_sys_path() -> None:
    """The consolidated provider slice (contracts + routing) has no sys.path mutation."""
    slice_files = [
        ROOT / "bago_core" / "providers" / "__init__.py",
        ROOT / "bago_core" / "providers" / "contracts.py",
        ROOT / "bago_core" / "providers" / "routing.py",
    ]
    for path in slice_files:
        assert _ast_mutations(path.read_text(encoding="utf-8")) == [], f"{path} mutates sys.path"


def test_provider_facades_delegate_to_package_slice() -> None:
    """Compatibility facades in .bago/core re-export from bago_core.providers."""
    for facade, expected in (
        (ROOT / ".bago" / "core" / "provider_adapter.py", "bago_core.providers.contracts"),
        (ROOT / ".bago" / "core" / "model_equivalence.py", "bago_core.providers.routing"),
    ):
        source = facade.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("bago_core.providers")
        ]
        assert expected in imports, f"{facade} does not import from {expected}"
        assert "__all__" in source


def test_session_core_consumes_providers_via_package_imports() -> None:
    """session_manager and switch_engine reach providers through bago_core.providers."""
    for path in (
        ROOT / ".bago" / "core" / "session_manager.py",
        ROOT / ".bago" / "core" / "switch_engine.py",
    ):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        package_imports = [
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("bago_core.providers")
        ]
        assert package_imports, f"{path} lacks bago_core.providers package imports"


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


def test_migration_inventory_is_current_and_machine_checkable() -> None:
    """The remaining sys.path/add_piece_paths migration surface matches the inventory.

    Scans versioned sources only: same exclusions as the generator, so a
    clean CI checkout and a developer machine produce identical results.
    """
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert inventory["contract"] == "bago.import-migration-inventory.v1"
    assert inventory["version"] == "1.0.0"

    actual: dict[str, list[dict[str, str]]] = {}
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in ("tests", "tests_local", "__pycache__") for part in path.parts):
            continue
        if any(part in EXCLUDED_TREE_DIRS for part in path.relative_to(ROOT).parts):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        mutations: list[dict[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                func = node.func
                if func.attr in {"insert", "append"}:
                    target = func.value
                    if isinstance(target, ast.Attribute) and target.attr == "path" and isinstance(target.value, ast.Name) and target.value.id == "sys":
                        mutations.append({"line": str(node.lineno), "call": f"sys.path.{func.attr}"})
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add_piece_paths":
                mutations.append({"line": str(node.lineno), "call": "add_piece_paths"})
            elif isinstance(node, (ast.ImportFrom, ast.Import)):
                if "add_piece_paths" in [alias.name for alias in node.names]:
                    mutations.append({"line": str(node.lineno), "call": "import add_piece_paths"})
        if mutations:
            relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
            actual[relative] = mutations

    recorded = {
        entry["path"]: [{"line": str(m["line"]), "call": m["call"]} for m in entry["mutations"]]
        for entry in inventory["files"]
    }
    assert recorded == actual, (
        "Migration inventory drift. Run the AST scan to regenerate "
        "backend/contracts/import_migration_inventory.v1.json."
    )
    assert inventory["total_files"] == len(actual)
    assert inventory["total_mutations"] == sum(len(m) for m in actual.values())

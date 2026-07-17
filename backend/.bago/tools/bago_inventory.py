#!/usr/bin/env python3
"""Portable workspace inventory for BAGO.

Usage:
    python bago_inventory.py [--root DIR] [--format text|md|json] [--test]

Exit codes:
    0 = ok
    2 = runtime error
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".bago\\backups"}
SOURCE_EXTS = {".py", ".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx", ".ps1", ".cmd"}
SCRIPT_EXTS = {".py", ".ps1", ".cmd", ".bat", ".sh"}

TOOL_DIRS = (Path("tools"), Path(".bago") / "tools")
AGENT_DIRS = (Path("agents"), Path(".bago") / "agents")
SCRIPT_DIRS = (Path("scripts"),)
MODULE_DIRS = (
    Path("bago_core"),
    Path(".bago") / "core",
    Path(".bago") / "chat",
    Path(".bago") / "providers",
    Path("electron"),
    Path("manager"),
    Path("ui-react") / "src",
)


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def should_skip_dir(path_name: str) -> bool:
    return path_name in SKIP_DIRS or path_name == ".bago\\state" or path_name == ".bago/state"


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def _collect_files(root: Path, rel_dirs: tuple[Path, ...], exts: set[str]) -> list[Path]:
    found: list[Path] = []
    for rel_dir in rel_dirs:
        base = root / rel_dir
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix.lower() not in exts:
                continue
            if any(should_skip_dir(part) for part in path.parts):
                continue
            found.append(path)
    return found


def parse_python(path: Path, root: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text, filename=str(path))
    funcs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append({
                "name": node.name,
                "line": node.lineno,
                "doc": ast.get_docstring(node) or "",
            })
    return {
        "path": _rel(path, root),
        "kind": "python",
        "doc": ast.get_docstring(tree) or "",
        "functions": funcs,
    }


def parse_json_manifest(path: Path, root: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    data = json.loads(text)
    keys = sorted(data.keys())[:20] if isinstance(data, dict) else []
    return {
        "path": _rel(path, root),
        "kind": "json",
        "type": type(data).__name__,
        "top_keys": keys,
    }


def _scan_category(root: Path, rel_dirs: tuple[Path, ...], exts: set[str], kind: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in _collect_files(root, rel_dirs, exts):
        if path.suffix.lower() == ".py":
            try:
                items.append(parse_python(path, root))
            except Exception as exc:  # noqa: BLE001
                items.append({"path": _rel(path, root), "kind": kind, "error": str(exc)})
        else:
            items.append({"path": _rel(path, root), "kind": kind})
    return items


def gather_inventory(root: Path) -> dict[str, object]:
    tools = _scan_category(root, TOOL_DIRS, {".py"}, "tool")
    agents = _scan_category(root, AGENT_DIRS, {".py"}, "agent")
    scripts = _scan_category(root, SCRIPT_DIRS, SCRIPT_EXTS, "script")
    modules = _scan_category(root, MODULE_DIRS, SOURCE_EXTS, "module")

    manifests: list[dict[str, object]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        base = Path(dirpath)
        for name in filenames:
            if name.endswith(".json"):
                path = base / name
                try:
                    manifests.append(parse_json_manifest(path, root))
                except Exception as exc:  # noqa: BLE001
                    manifests.append({"path": _rel(path, root), "kind": "json", "error": str(exc)})

    return {
        "root": str(root),
        "tools": tools,
        "agents": agents,
        "scripts": scripts,
        "modules": modules,
        "manifests": sorted(manifests, key=lambda item: item["path"]),
        "summary": {
            "tool_files": len(tools),
            "agent_files": len(agents),
            "script_files": len(scripts),
            "module_files": len(modules),
            "json_manifests": len(manifests),
            "total_pieces": len(tools) + len(agents) + len(scripts) + len(modules),
        },
    }


def _format_items(label: str, items: list[dict[str, object]], limit: int | None = None) -> list[str]:
    if not items:
        return [f"{label}: 0"]
    lines = [f"{label}: {len(items)}"]
    shown = items if limit is None else items[:limit]
    for item in shown:
        line = f"  - {item['path']}"
        if item.get("kind") == "python" and item.get("functions") is not None:
            line += f" ({len(item['functions'])} functions)"
        if "error" in item:
            line += f" ERROR {item['error']}"
        lines.append(line)
    if limit is not None and len(items) > limit:
        lines.append(f"  ... y {len(items) - limit} más")
    return lines


def format_startup_text(data: dict[str, object], limit: int = 5) -> str:
    lines = [
        f"Inventario BAGO: {data['summary']['total_pieces']} piezas rastreadas",
        f"  tools={data['summary']['tool_files']} agents={data['summary']['agent_files']} scripts={data['summary']['script_files']} modules={data['summary']['module_files']} manifests={data['summary']['json_manifests']}",
        "",
    ]
    lines += _format_items("Tools", data["tools"], limit)
    lines.append("")
    lines += _format_items("Agents", data["agents"], limit)
    lines.append("")
    lines += _format_items("Scripts", data["scripts"], limit)
    lines.append("")
    lines += _format_items("Modules", data["modules"], limit)
    return "\n".join(lines)


def format_text(data: dict[str, object]) -> str:
    lines = [
        f"Inventory root: {data['root']}",
        f"Tools: {data['summary']['tool_files']}",
        f"Agents: {data['summary']['agent_files']}",
        f"Scripts: {data['summary']['script_files']}",
        f"Modules: {data['summary']['module_files']}",
        f"JSON manifests: {data['summary']['json_manifests']}",
    ]
    lines.extend(_format_items("Tool files", data["tools"]))
    lines.append("")
    lines.extend(_format_items("Agent files", data["agents"]))
    lines.append("")
    lines.extend(_format_items("Script files", data["scripts"]))
    lines.append("")
    lines.extend(_format_items("Module files", data["modules"]))
    if data["manifests"]:
        lines.append("")
        lines.append("JSON manifests:")
        for item in data["manifests"][:40]:
            if "error" in item:
                lines.append(f"  - {item['path']} ERROR {item['error']}")
            else:
                lines.append(f"  - {item['path']} keys={','.join(item.get('top_keys', []))}")
    return "\n".join(lines)


def format_md(data: dict[str, object]) -> str:
    lines = [
        f"# Inventory for `{data['root']}`",
        "",
        f"- Tools: {data['summary']['tool_files']}",
        f"- Agents: {data['summary']['agent_files']}",
        f"- Scripts: {data['summary']['script_files']}",
        f"- Modules: {data['summary']['module_files']}",
        f"- JSON manifests: {data['summary']['json_manifests']}",
        "",
        "## Tools",
    ]
    for item in data["tools"]:
        lines.append(f"- `{item['path']}`")
        for func in item.get("functions", []):
            lines.append(f"  - `{func['name']}`: {func['doc'][:80]}")
    lines.append("")
    lines.append("## Agents")
    for item in data["agents"]:
        lines.append(f"- `{item['path']}`")
    lines.append("")
    lines.append("## Scripts")
    for item in data["scripts"]:
        lines.append(f"- `{item['path']}`")
    lines.append("")
    lines.append("## Modules")
    for item in data["modules"]:
        lines.append(f"- `{item['path']}`")
    lines.append("")
    lines.append("## JSON manifests")
    for item in data["manifests"]:
        if "error" in item:
            lines.append(f"- `{item['path']}` ERROR {item['error']}")
        else:
            lines.append(f"- `{item['path']}` keys={', '.join(item.get('top_keys', []))}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable workspace inventory")
    parser.add_argument("--root", default="", help="Project root")
    parser.add_argument("--format", default="text", choices=["text", "md", "json"])
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()

    root = resolve_root(args.root)
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] invalid root: {root}", file=sys.stderr)
        return 2

    try:
        data = gather_inventory(root)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] bago_inventory failed: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(data, indent=2, ensure_ascii=True))
    elif args.format == "md":
        print(format_md(data))
    else:
        print(format_text(data))
    return 0


def run_self_tests() -> int:
    import tempfile

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "tools").mkdir()
        (root / "agents").mkdir()
        (root / "scripts").mkdir()
        (root / "bago_core").mkdir()
        (root / "tools" / "alpha.py").write_text('"""tool doc"""\n\n\ndef run():\n    """do work"""\n    return 1\n', encoding="utf-8")
        (root / "agents" / "agent_a.py").write_text('def act():\n    return True\n', encoding="utf-8")
        (root / "scripts" / "boot.py").write_text('print("boot")\n', encoding="utf-8")
        (root / "bago_core" / "core_a.py").write_text('def core():\n    return 1\n', encoding="utf-8")
        (root / "manifest.json").write_text('{"name": "demo", "version": 1}', encoding="utf-8")
        data = gather_inventory(root)
        record("inventory:tool_file", data["summary"]["tool_files"] == 1, f"tools={data['summary']['tool_files']}")
        record("inventory:agent_file", data["summary"]["agent_files"] == 1, f"agents={data['summary']['agent_files']}")
        record("inventory:script_file", data["summary"]["script_files"] == 1, f"scripts={data['summary']['script_files']}")
        record("inventory:module_file", data["summary"]["module_files"] == 1, f"modules={data['summary']['module_files']}")
        record("inventory:manifest", data["summary"]["json_manifests"] == 1, f"json={data['summary']['json_manifests']}")
        record("inventory:function_doc", data["tools"][0]["functions"][0]["doc"] == "do work", "doc ok")
        record("inventory:text_output", "Tool files:" in format_text(data), "text ok")
        record("inventory:md_output", "## Scripts" in format_md(data), "md ok")
        record("inventory:startup_output", "Inventario BAGO" in format_startup_text(data), "startup ok")

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

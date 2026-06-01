#!/usr/bin/env python3
"""Portable project inventory for BAGO 4.x.

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


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def should_skip_dir(path_name: str) -> bool:
    return path_name in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "backups"}


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
        "path": str(path.relative_to(root)),
        "kind": "python",
        "doc": ast.get_docstring(tree) or "",
        "functions": funcs,
    }


def parse_json_manifest(path: Path, root: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    data = json.loads(text)
    if isinstance(data, dict):
        keys = sorted(data.keys())[:20]
    else:
        keys = []
    return {
        "path": str(path.relative_to(root)),
        "kind": "json",
        "type": type(data).__name__,
        "top_keys": keys,
    }


def gather_inventory(root: Path) -> dict[str, object]:
    tools = []
    agents = []
    manifests = []
    python_targets = []
    for rel_dir in (Path("tools"), Path(".bago") / "tools"):
        base = root / rel_dir
        if base.exists():
            python_targets.extend(sorted(base.glob("*.py")))
    agent_targets = []
    for rel_dir in (Path("agents"), Path(".bago") / "agents"):
        base = root / rel_dir
        if base.exists():
            agent_targets.extend(sorted(base.glob("*.py")))
    for path in python_targets:
        tools.append(parse_python(path, root))
    for path in agent_targets:
        agents.append(parse_python(path, root))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        base = Path(dirpath)
        for name in filenames:
            if name.endswith(".json"):
                path = base / name
                try:
                    manifests.append(parse_json_manifest(path, root))
                except Exception as exc:  # noqa: BLE001
                    manifests.append({
                        "path": str(path.relative_to(root)),
                        "kind": "json",
                        "error": str(exc),
                    })
    return {
        "root": str(root),
        "tools": tools,
        "agents": agents,
        "manifests": sorted(manifests, key=lambda item: item["path"]),
        "summary": {
            "tool_files": len(tools),
            "agent_files": len(agents),
            "json_manifests": len(manifests),
        },
    }


def format_text(data: dict[str, object]) -> str:
    lines = [
        f"Inventory root: {data['root']}",
        f"Tools: {data['summary']['tool_files']}",
        f"Agents: {data['summary']['agent_files']}",
        f"JSON manifests: {data['summary']['json_manifests']}",
    ]
    if data["tools"]:
        lines.append("Tool files:")
        for item in data["tools"]:
            lines.append(f"  - {item['path']} ({len(item['functions'])} functions)")
            for func in item["functions"]:
                lines.append(f"      * {func['name']}: {func['doc'][:80]}")
    if data["agents"]:
        lines.append("Agent files:")
        for item in data["agents"]:
            lines.append(f"  - {item['path']} ({len(item['functions'])} functions)")
    if data["manifests"]:
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
        f"- JSON manifests: {data['summary']['json_manifests']}",
        "",
        "## Tools",
    ]
    for item in data["tools"]:
        lines.append(f"- `{item['path']}`")
        for func in item["functions"]:
            lines.append(f"  - `{func['name']}`: {func['doc'][:80]}")
    lines.append("")
    lines.append("## Agents")
    for item in data["agents"]:
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
    parser = argparse.ArgumentParser(description="Portable project inventory")
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
        (root / "tools" / "alpha.py").write_text('"""tool doc"""\n\n\ndef run():\n    """do work"""\n    return 1\n', encoding="utf-8")
        (root / "agents" / "agent_a.py").write_text('def act():\n    return True\n', encoding="utf-8")
        (root / "manifest.json").write_text('{"name": "demo", "version": 1}', encoding="utf-8")
        data = gather_inventory(root)
        record("inventory:tool_file", data["summary"]["tool_files"] == 1, f"tools={data['summary']['tool_files']}")
        record("inventory:agent_file", data["summary"]["agent_files"] == 1, f"agents={data['summary']['agent_files']}")
        record("inventory:manifest", data["summary"]["json_manifests"] == 1, f"json={data['summary']['json_manifests']}")
        record("inventory:function_doc", data["tools"][0]["functions"][0]["doc"] == "do work", "doc ok")
        record("inventory:text_output", "Tool files:" in format_text(data), "text ok")
        record("inventory:md_output", "## Tools" in format_md(data), "md ok")

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

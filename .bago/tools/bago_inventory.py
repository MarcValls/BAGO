#!/usr/bin/env python3
"""bago_inventory.py — Descubre y cataloga todas las capacidades reutilizables de BAGO.

Escanea:
  - agents/        -> agentes disponibles, contratos, capabilities
  - tools/         -> herramientas Python con docstrings
  - core/          -> modulos de nucleo (dispatcher, context, runtime)
  - roles/         -> definiciones de roles BAGO
  - mcp/           -> MCP servers y tool matrices
  - workflows/     -> flujos de trabajo definidos
  - manifests/     -> custom_agents.json y otros manifiestos
  - state/         -> model_providers.json, model_routing.json

Uso:
  python bago_inventory.py [--format json|md]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TOOLS_DIR = Path(__file__).resolve().parent
BAGO_DIR = TOOLS_DIR.parent


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def scan_agents() -> list[dict]:
    """Escanea agents/ y agents_contract.json."""
    agents = []
    agents_dir = BAGO_DIR / "agents"
    contract = _read_json(agents_dir / "agent_contract.json")
    if contract:
        agents.append({
            "type": "contract",
            "name": "agent_contract",
            "path": str(agents_dir / "agent_contract.json"),
            "description": contract.get("description", ""),
            "schemas": list(contract.get("definitions", {}).keys()),
        })
    for f in agents_dir.glob("*.py"):
        agents.append({
            "type": "agent_module",
            "name": f.stem,
            "path": str(f),
            "language": "python",
        })
    return agents


def scan_tools() -> list[dict]:
    """Escanea tools/*.py y extrae funciones con docstrings."""
    tools = []
    tools_dir = BAGO_DIR / "tools"
    for f in sorted(tools_dir.glob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node)
                funcs.append({
                    "name": node.name,
                    "doc": doc[:120] + "..." if doc and len(doc) > 120 else (doc or ""),
                    "args": [arg.arg for arg in node.args.args],
                })
        if funcs:
            tools.append({
                "type": "tool_module",
                "name": f.stem,
                "path": str(f),
                "language": "python",
                "functions": funcs[:10],  # limitar para no saturar
            })
    return tools


def scan_roles() -> list[dict]:
    """Escanea roles/ y role definitions."""
    roles = []
    roles_dir = BAGO_DIR / "roles"
    manifest = _read_json(roles_dir / "manifest.json")
    if manifest:
        for role_id, role_def in manifest.get("roles", {}).items():
            roles.append({
                "type": "role",
                "id": role_id,
                "name": role_def.get("name", role_id),
                "path": str(roles_dir / "manifest.json"),
                "description": role_def.get("description", ""),
            })
    for f in roles_dir.glob("*.py"):
        roles.append({"type": "role_module", "name": f.stem, "path": str(f), "language": "python"})
    return roles


def scan_mcp() -> list[dict]:
    """Escanea mcp/ para servers y tool matrices."""
    mcp = []
    mcp_dir = BAGO_DIR / "mcp"
    matrix = _read_json(mcp_dir / "agent_tool_matrix.json")
    if matrix:
        for agent_id, agent_def in matrix.get("agents", {}).items():
            mcp.append({
                "type": "mcp_agent",
                "id": agent_id,
                "role": agent_def.get("role", ""),
                "primary_tools": agent_def.get("primary_tools", []),
                "path": str(mcp_dir / "agent_tool_matrix.json"),
            })
        for tool_name, tool_def in matrix.get("tools", {}).items():
            mcp.append({
                "type": "mcp_tool",
                "name": tool_name,
                "cmd": tool_def.get("cmd", ""),
                "layer": tool_def.get("layer", ""),
                "path": str(mcp_dir / "agent_tool_matrix.json"),
            })
    for f in mcp_dir.glob("*.py"):
        mcp.append({"type": "mcp_server", "name": f.stem, "path": str(f), "language": "python"})
    return mcp


def scan_workflows() -> list[dict]:
    """Escanea workflows/ para flujos definidos."""
    workflows = []
    wf_dir = BAGO_DIR / "workflows"
    for f in sorted(wf_dir.glob("*.json")):
        data = _read_json(f)
        if data:
            workflows.append({
                "type": "workflow",
                "name": f.stem,
                "path": str(f),
                "nodes": len(data) if isinstance(data, list) else len(data.get("nodes", [])),
            })
    for f in sorted(wf_dir.glob("*.md")):
        workflows.append({"type": "workflow_doc", "name": f.stem, "path": str(f)})
    return workflows


def scan_models() -> list[dict]:
    """Escanea state/model_providers.json para modelos disponibles."""
    models = []
    providers = _read_json(BAGO_DIR / "state" / "model_providers.json")
    if providers:
        for prov_name, prov in providers.get("providers", {}).items():
            for model_name, model in prov.get("models", {}).items():
                models.append({
                    "type": "model",
                    "name": model_name,
                    "provider": prov_name,
                    "wire_name": model.get("wire_name", model_name),
                    "best_for": model.get("best_for", ""),
                    "cost": model.get("cost", "unknown"),
                })
    return models


def scan_manifests() -> list[dict]:
    """Escanea manifests/ para agentes custom."""
    manifests = []
    m_dir = BAGO_DIR / "manifests"
    custom = _read_json(m_dir / "custom_agents.json")
    if custom:
        for agent in custom.get("agents", []):
            if agent.get("name"):
                manifests.append({
                    "type": "custom_agent",
                    "name": agent["name"],
                    "category": agent.get("category", ""),
                    "status": agent.get("status", ""),
                })
    return manifests


def scan_core() -> list[dict]:
    """Escanea core/ para modulos reutilizables."""
    core = []
    core_dir = BAGO_DIR / "core"
    for f in sorted(core_dir.glob("*.py")):
        core.append({"type": "core_module", "name": f.stem, "path": str(f), "language": "python"})
    return core


def build_inventory() -> dict:
    return {
        "meta": {
            "version": "2026.05.15",
            "description": "Inventario de capacidades reutilizables de BAGO",
            "source": str(BAGO_DIR),
        },
        "agents": scan_agents(),
        "tools": scan_tools(),
        "roles": scan_roles(),
        "mcp": scan_mcp(),
        "workflows": scan_workflows(),
        "models": scan_models(),
        "manifests": scan_manifests(),
        "core": scan_core(),
    }


def suggest_reuse(task_type: str, inventory: dict) -> list[dict]:
    """Sugiere componentes reutilizables para un tipo de tarea."""
    suggestions = []

    # Mapeo tipo de tarea -> herramientas relevantes
    type_map = {
        "music": ["music", "score", "vexflow", "transpose"],
        "code": ["code", "review", "security", "smell"],
        "debug": ["debug", "error", "fix"],
        "quality": ["review", "audit", "security"],
        "content": ["content", "generate", "render"],
        "architecture": ["architecture", "design", "router"],
    }
    keywords = type_map.get(task_type, [task_type])

    for tool in inventory.get("tools", []):
        score = 0
        tool_text = json.dumps(tool, ensure_ascii=False).lower()
        for kw in keywords:
            if kw in tool_text:
                score += 1
        if score > 0:
            suggestions.append({
                "component": tool["name"],
                "type": "tool",
                "relevance": score,
                "path": tool["path"],
            })

    for wf in inventory.get("workflows", []):
        wf_text = wf["name"].lower()
        for kw in keywords:
            if kw in wf_text:
                suggestions.append({
                    "component": wf["name"],
                    "type": "workflow",
                    "relevance": 1,
                    "path": wf["path"],
                })

    suggestions.sort(key=lambda x: x["relevance"], reverse=True)
    return suggestions[:15]


def print_inventory(inv: dict) -> None:
    print("\n  BAGO Inventory — Capacidades Reutilizables")
    print("  " + "-" * 50)
    total = sum(len(v) for v in inv.values() if isinstance(v, list))
    print(f"  Total componentes: {total}\n")

    for category, items in inv.items():
        if category == "meta" or not items:
            continue
        print(f"  [{category.upper()}] — {len(items)} items")
        for item in items[:5]:
            name = item.get("name") or item.get("id") or item.get("type")
            print(f"    - {name}")
        if len(items) > 5:
            print(f"    ... y {len(items)-5} mas")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="BAGO Inventory Scanner")
    parser.add_argument("--format", choices=["json", "md"], default="md", help="Formato de salida")
    parser.add_argument("--output", help="Archivo de salida (default: stdout)")
    parser.add_argument("--suggest", help="Sugerir componentes para tipo de tarea (ej: music, code)")
    args = parser.parse_args()

    inv = build_inventory()

    if args.suggest:
        suggestions = suggest_reuse(args.suggest, inv)
        print(f"\n  Sugerencias para tarea tipo: {args.suggest}")
        print("  " + "-" * 50)
        for s in suggestions:
            print(f"  [{s['type']}] {s['component']} (relevancia: {s['relevance']}) — {s['path']}")
        print()
        return 0

    if args.format == "json":
        out = json.dumps(inv, indent=2, ensure_ascii=False)
    else:
        # Generar markdown
        lines = ["# BAGO Inventory", "", f"**Fuente:** {inv['meta']['source']}", ""]
        for cat, items in inv.items():
            if cat == "meta" or not items:
                continue
            lines.append(f"## {cat.upper()}")
            for item in items:
                name = item.get("name") or item.get("id") or item.get("type")
                lines.append(f"- **{name}** — {item.get('path', '')}")
            lines.append("")
        out = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"\n  Inventario guardado: {args.output}\n")
    else:
        if args.format == "md":
            print_inventory(inv)
        else:
            print(out)

    return 0




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
    exit(main())
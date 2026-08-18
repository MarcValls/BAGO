#!/usr/bin/env python3
"""Startup inventory helpers for the BAGO REPL.

Reports only pieces BAGO can actually USE — not raw disk file counts.
Queries the real registries (tool_registry, agent_gateway, script_registry)
instead of scanning the filesystem by extension.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import renderer as R


def _bago_install_root() -> Path | None:
    """Resuelve el directorio raíz de BAGO (donde están .bago/tools/)."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2],           # .../BAG4.8/ from .bago/chat/repl_inventory.py
    ]
    for c in candidates:
        if (c / ".bago" / "tools").is_dir():
            return c
    return None


# ── Carga diferida de registros reales ─────────────────────────────────────────

def _load_tool_registry() -> dict[str, Any]:
    """Carga el REGISTRY canónico desde .bago/tools/tool_registry.py."""
    root = _bago_install_root()
    if root is None:
        return {}
    reg_path = root / ".bago" / "tools" / "tool_registry.py"
    if not reg_path.exists():
        return {}
    tools_dir = str(reg_path.parent)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    try:
        spec = importlib.util.spec_from_file_location("_inv_tool_registry", reg_path)
        if spec is None or spec.loader is None:
            return {}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, "REGISTRY", {})
    except Exception:
        return {}


def _load_agent_gateway():
    """Carga AgentGateway desde .bago/core/agent_gateway.py."""
    root = _bago_install_root()
    if root is None:
        return None
    core_dir = str(root / ".bago" / "core")
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    try:
        from agent_gateway import AgentGateway
        return AgentGateway()
    except Exception:
        return None


def _load_script_registry():
    """Carga ScriptRegistry desde .bago/core/script_registry.py."""
    root = _bago_install_root()
    if root is None:
        return None
    core_dir = str(root / ".bago" / "core")
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    try:
        from script_registry import ScriptRegistry
        return ScriptRegistry(repo_root=root)
    except Exception:
        return None


# ── Inventario usable ──────────────────────────────────────────────────────────

def gather_usable_inventory() -> dict[str, Any]:
    """Consulta los registros reales y devuelve solo lo que BAGO puede usar.

    Categorías:
      tools   — entradas en REGISTRY, no deprecated, con archivo en disco
      agents  — agentes registrados en AgentGateway
      scripts — ScriptSpecs habilitados y existentes en disco
    """
    root = _bago_install_root()
    tools_dir = root / ".bago" / "tools" if root else None

    # ── Tools ──
    registry = _load_tool_registry()
    tools_list: list[dict[str, Any]] = []
    for cmd, entry in sorted(registry.items()):
        if getattr(entry, "deprecated", False):
            continue
        module = getattr(entry, "module", "")
        has_schema = bool(getattr(entry, "schema", None))
        # Verificar que el archivo existe
        file_exists = False
        if tools_dir:
            for candidate in [tools_dir / f"{module}.py", tools_dir / module / "__main__.py"]:
                if candidate.exists():
                    file_exists = True
                    break
        tools_list.append({
            "cmd": cmd,
            "module": module,
            "description": getattr(entry, "description", ""),
            "layer": getattr(entry, "layer", ""),
            "scope": getattr(entry, "scope", ""),
            "stability": getattr(entry, "stability", ""),
            "has_schema": has_schema,
            "file_exists": file_exists,
            "llm_invocable": file_exists,  # to_openai() envía todas las no-deprecated al LLM
        })

    # ── Agents ──
    gateway = _load_agent_gateway()
    agents_list: list[dict[str, Any]] = []
    if gateway is not None:
        for agent in gateway.list_agents():
            agents_list.append({
                "name": agent.name,
                "description": agent.description,
                "preferred_provider": getattr(agent, "preferred_provider", ""),
                "preferred_model": getattr(agent, "preferred_model", ""),
                "active": agent.name == gateway.active.name,
            })

    # ── Scripts ──
    script_reg = _load_script_registry()
    scripts_list: list[dict[str, Any]] = []
    if script_reg is not None:
        for spec in script_reg.list_scripts():
            scripts_list.append({
                "id": spec["id"],
                "battery": spec["battery"],
                "description": spec["description"],
                "path": spec["path"],
                "enabled": spec["enabled"],
                "exists": spec["exists"],
                "usable": spec["enabled"] and spec["exists"],
            })

    summary = {
        "tools": len(tools_list),
        "agents": len(agents_list),
        "scripts": len(scripts_list),
        "tools_llm": sum(1 for t in tools_list if t["llm_invocable"]),
        "scripts_usable": sum(1 for s in scripts_list if s["usable"]),
        "total": len(tools_list) + len(agents_list) + len(scripts_list),
    }
    return {
        "tools": tools_list,
        "agents": agents_list,
        "scripts": scripts_list,
        "summary": summary,
    }


def format_usable_summary(data: dict[str, Any]) -> str:
    """Una línea con conteos honestos de piezas usables."""
    s = data["summary"]
    return (
        f"tools={s['tools']} ({s['tools_llm']} invocables por LLM)  "
        f"agents={s['agents']}  "
        f"scripts={s['scripts']} ({s['scripts_usable']} ejecutables)"
    )


def format_category_lines(data: dict[str, Any], category: str) -> list[str]:
    """Una línea por pieza, para la vista detallada paginada."""
    if category == "tools":
        lines = []
        for t in data["tools"]:
            mark = "🤖" if t["llm_invocable"] else "🔧"
            stab = f"[{t['stability']}]" if t["stability"] and t["stability"] != "experimental" else ""
            schema_tag = " +schema" if t["has_schema"] else ""
            lines.append(f"{mark} /{t['cmd']}  —  {t['description'][:55]}{schema_tag}  {stab}")
        return lines
    if category == "agents":
        lines = []
        for a in data["agents"]:
            mark = "★" if a["active"] else "○"
            lines.append(f"{mark} {a['name']}  —  {a['description'][:60]}")
        return lines
    if category == "scripts":
        lines = []
        for s in data["scripts"]:
            mark = "✓" if s["usable"] else "!"
            lines.append(f"{mark} {s['id']}  —  {s['description'][:55]}  ({s['path']})")
        return lines
    return []


# ── Startup display ────────────────────────────────────────────────────────────

def print_workspace_inventory(base_path: Path) -> None:
    """Imprime el inventario honesto al arrancar el REPL."""
    try:
        data = gather_usable_inventory()
        s = data["summary"]
        print(R.bold("\nInventario usable de BAGO"))
        print(R.dim(f"  {format_usable_summary(data)}"))
        print(R.dim(f"  Total de piezas usables: {s['total']}"))
        print()
        print(R.dim("Usa /inventory para ver el detalle por categoría."))
        print()
    except Exception as exc:
        print(R.warn(f"Inventario no disponible: {exc}"))
        print()


# ── Vista detallada para el menú ───────────────────────────────────────────────

INVENTORY_CATEGORIES = [
    ("tools",   "Herramientas",   "Tools registradas — invocables por LLM o por CLI"),
    ("agents",  "Agentes",        "Agentes especializados con system-prompt propio"),
    ("scripts", "Scripts",        "Scripts en baterías funcionales — ejecutables"),
]


def inventory_category_labels(data: dict[str, Any]) -> list[str]:
    """Etiquetas para el menú de categorías del inventario."""
    labels = []
    for cat_id, cat_name, cat_desc in INVENTORY_CATEGORIES:
        count = len(data.get(cat_id, []))
        labels.append(f"{cat_name}  ·  {count} piezas  —  {cat_desc}")
    return labels
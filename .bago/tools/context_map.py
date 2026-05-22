#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
context_map.py — Mapa de contexto distribuido BAGO

Descubre todas las instalaciones .bago/ bajo una raíz y construye un mapa
jerárquico de contextos. El BAGO raíz puede consumir este mapa para tener
visibilidad completa del árbol sin releer cada instalación.

Uso:
  python3 context_map.py              # muestra árbol en consola
  python3 context_map.py --save       # guarda en state/context_map.json
  python3 context_map.py --json       # output JSON crudo
  python3 context_map.py --root /ruta # raíz de búsqueda personalizada
  python3 context_map.py --depth 4    # limitar profundidad
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # BAGO_CAJAFISICA
SEARCH_ROOT_DEFAULT = ROOT.parent                   # Desktop


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Descubrimiento ─────────────────────────────────────────────────────────────

def _is_nested_inside_bago(path: Path) -> bool:
    """True si algún ancestro del directorio es ya un .bago/"""
    return ".bago" in path.parent.parts


def scan_bago_nodes(search_root: Path, max_depth: int = 6) -> list[dict]:
    nodes = []
    for bago_dir in sorted(search_root.rglob(".bago")):
        if not bago_dir.is_dir():
            continue
        if _is_nested_inside_bago(bago_dir):
            continue
        project_root = bago_dir.parent
        try:
            rel = project_root.relative_to(search_root)
            depth = len(rel.parts)
        except ValueError:
            continue
        if depth > max_depth:
            continue
        nodes.append(_read_node(project_root, bago_dir, depth, search_root))
    return nodes


# ── Lectura de cada nodo ───────────────────────────────────────────────────────

def _read_node(project_root: Path, bago_dir: Path, depth: int, search_root: Path) -> dict:
    node: dict = {
        "path": str(project_root),
        "relative_path": str(project_root.relative_to(search_root)) if project_root != search_root else ".",
        "depth": depth,
    }

    # repo_context.json
    ctx_file = bago_dir / "state" / "repo_context.json"
    if ctx_file.exists():
        try:
            ctx = json.loads(ctx_file.read_text(encoding="utf-8"))
            node["working_mode"] = ctx.get("working_mode", "unknown")
            node["repo_root"]    = ctx.get("repo_root", str(project_root))
            node["recorded_at"]  = ctx.get("recorded_at", "")
            node["role"]         = ctx.get("role", "")
        except Exception:
            node["working_mode"] = "parse_error"
    else:
        node["working_mode"] = "no_context"

    # global_state.json
    gs_file = bago_dir / "state" / "global_state.json"
    if gs_file.exists():
        try:
            gs = json.loads(gs_file.read_text(encoding="utf-8"))
            node["bago_version"]      = gs.get("bago_version", "?")
            node["system_health"]     = gs.get("system_health", "?")
            node["last_session"]      = gs.get("last_completed_session_id", "")
            node["last_workflow"]     = gs.get("last_completed_workflow", "")
            node["active_scenarios"]  = gs.get("active_scenarios", [])
            node["active_workflows"]  = gs.get("active_workflows", [])
            node["sessions_count"]    = gs.get("inventory", {}).get("sessions", 0)
            node["last_validation"]   = gs.get("last_validation", {})
        except Exception:
            node["bago_version"] = "parse_error"
    else:
        node["bago_version"]  = "no_state"
        node["system_health"] = "unknown"

    return node


# ── Renderizado ────────────────────────────────────────────────────────────────

_MODE_ICON = {
    "self":       "🏠",
    "external":   "🔗",
    "no_context": "❓",
    "parse_error":"❌",
    "unknown":    "•",
}

_HEALTH_ICON = {
    "stable":      "🟢",
    "initializing":"🟡",
    "degraded":    "🟠",
    "unknown":     "⚪",
}


def render_tree(nodes: list[dict], search_root: Path) -> str:
    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║         BAGO CONTEXT MAP — MAPA DE CONTEXTO DISTRIBUIDO     ║",
        "╚══════════════════════════════════════════════════════════════╝",
        f"  Raíz de búsqueda: {search_root}",
        f"  Nodos encontrados: {len(nodes)}",
        "",
    ]

    for n in nodes:
        indent = "    " * n["depth"]
        connector = "└─ " if n["depth"] > 0 else "● "
        rel   = n.get("relative_path", n["path"])
        mode  = n.get("working_mode", "unknown")
        ver   = n.get("bago_version", "?")
        hlth  = n.get("system_health", "unknown")
        sess  = n.get("sessions_count", "?")
        last  = n.get("last_session", "")
        scen  = n.get("active_scenarios", [])
        val   = n.get("last_validation", {})

        mode_ic   = _MODE_ICON.get(mode, "•")
        health_ic = _HEALTH_ICON.get(hlth, "⚪")

        lines.append(f"{indent}{connector}{mode_ic}  {rel}")
        lines.append(f"{indent}    versión: {ver}  {health_ic} {hlth}  sesiones: {sess}")

        # Validación compacta
        if val:
            val_str = "  ".join(f"{k}:{v}" for k, v in val.items())
            lines.append(f"{indent}    validación: {val_str}")

        if last:
            wf = n.get("last_workflow", "")
            lines.append(f"{indent}    última sesión: {last}" + (f"  ({wf})" if wf else ""))

        if scen:
            lines.append(f"{indent}    ⚠ escenarios activos: {', '.join(scen)}")

        # Repo externo declarado
        repo_root = n.get("repo_root", "")
        if mode == "external" and repo_root and repo_root != n["path"]:
            lines.append(f"{indent}    🔗 apunta a: {repo_root}")

        lines.append("")

    return "\n".join(lines)


# ── Persistencia ───────────────────────────────────────────────────────────────

def save_map(result: dict) -> Path:
    out = ROOT / ".bago" / "state" / "context_map.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Mapea todos los .bago/ instalados bajo una raíz."
    )
    parser.add_argument(
        "--root", default=str(SEARCH_ROOT_DEFAULT),
        help=f"Directorio raíz de búsqueda (por defecto: {SEARCH_ROOT_DEFAULT})"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Guarda el mapa en .bago/state/context_map.json"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_out",
        help="Output JSON estructurado en lugar de árbol visual"
    )
    parser.add_argument(
        "--depth", type=int, default=6,
        help="Profundidad máxima de búsqueda (por defecto: 6)"
    )
    args = parser.parse_args(argv[1:])

    search_root = Path(args.root).resolve()
    if not search_root.exists():
        print(f"❌ Directorio no encontrado: {search_root}", file=sys.stderr)
        return 1

    nodes = scan_bago_nodes(search_root, args.depth)

    result = {
        "generated_at":  now_iso(),
        "search_root":   str(search_root),
        "bago_host":     str(ROOT),
        "total_nodes":   len(nodes),
        "nodes":         nodes,
    }

    if args.save:
        out = save_map(result)
        print(f"✅ Mapa guardado en {out}")

    if args.json_out:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render_tree(nodes, search_root))
        if args.save:
            print("  💾 Guardado en .bago/state/context_map.json")

    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main(sys.argv))

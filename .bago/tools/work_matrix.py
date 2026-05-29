#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
work_matrix.py — Matriz de rutas de trabajo BAGO.

Muestra qué agente y herramientas usar según el tipo de trabajo.
Fuente canónica: .bago/mcp/agent_tool_matrix.json

Uso:
    bago work_matrix                        → tabla completa
    bago work_matrix --type code            → ruta para un tipo específico
    bago work_matrix --agent ANALISTA       → herramientas de un agente
    bago work_matrix --list-types           → lista de tipos disponibles
    bago work_matrix --json                 → output JSON completo
    bago work_matrix --mcp-tools            → índice de herramientas MCP
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import json
import os
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS_DIR.parent
REPO_ROOT = BAGO_ROOT.parent
MATRIX_PATH = BAGO_ROOT / "mcp" / "agent_tool_matrix.json"

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
RED = "\033[31m"


def _load_matrix() -> dict:
    if not MATRIX_PATH.exists():
        print(f"[work_matrix] ERROR: Matriz no encontrada en {MATRIX_PATH}", file=sys.stderr)
        sys.exit(1)
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _agent_color(agent: str) -> str:
    colors = {
        "MAESTRO_BAGO": MAGENTA,
        "ANALISTA_Contexto": CYAN,
        "ARQUITECTO_Soluciones": BLUE,
        "CENTINELA_SINCERIDAD": RED,
        "GENERADOR_Contenido": GREEN,
        "INICIADOR_MAESTRO": YELLOW,
        "ORGANIZADOR_Entregables": CYAN,
        "ADAPTADOR_PROYECTO": GREEN,
        "GUIA_VERTICE": MAGENTA,
    }
    for key, color in colors.items():
        if key in agent:
            return color
    return RESET


def show_full_matrix(matrix: dict) -> None:
    work_types = matrix.get("work_types", {})
    print(f"\n{BOLD}{'─'*72}{RESET}")
    print(f"{BOLD}  BAGO — MATRIZ DE RUTAS DE TRABAJO{RESET}")
    print(f"{BOLD}{'─'*72}{RESET}")
    print(f"  {'TIPO':<18} {'AGENTE':<25} {'TOOLS MCP':<30}")
    print(f"  {'─'*18} {'─'*25} {'─'*30}")
    for wtype, info in work_types.items():
        agent = info.get("agent", "?")
        tools = ", ".join(info.get("mcp_tools", [])[:3])
        color = _agent_color(agent)
        print(f"  {CYAN}{wtype:<18}{RESET} {color}{agent:<25}{RESET} {DIM}{tools}{RESET}")
    print(f"{BOLD}{'─'*72}{RESET}")
    print(f"  {DIM}bago work_matrix --type <tipo>   → detalle de ruta{RESET}")
    print(f"  {DIM}bago work_matrix --list-types     → ver todos los tipos{RESET}\n")


def show_work_type(matrix: dict, wtype: str) -> int:
    work_types = matrix.get("work_types", {})
    # Partial match
    matched = {k: v for k, v in work_types.items() if wtype.lower() in k.lower()}
    if not matched:
        print(f"[work_matrix] Tipo '{wtype}' no encontrado.", file=sys.stderr)
        print(f"Tipos disponibles: {', '.join(work_types.keys())}", file=sys.stderr)
        return 1

    agents_info = matrix.get("agents", {})

    for key, info in matched.items():
        agent_name = info.get("agent", "?")
        agent_data = agents_info.get(agent_name, {})
        color = _agent_color(agent_name)

        print(f"\n{BOLD}{'─'*60}{RESET}")
        print(f"{BOLD}  RUTA: {CYAN}{key.upper()}{RESET}{BOLD} — {info.get('label', '')}{RESET}")
        print(f"{'─'*60}{RESET}")
        print(f"  {BOLD}Agente:{RESET}      {color}{agent_name}{RESET}")
        print(f"  {BOLD}Rol:{RESET}         {DIM}{agent_data.get('role', '—')}{RESET}")
        print(f"  {BOLD}Descripción:{RESET} {info.get('description', '—')}")
        print(f"  {BOLD}Riesgo:{RESET}      {info.get('risk', 'safe')}")
        print()
        tools = info.get("mcp_tools", [])
        if tools:
            print(f"  {BOLD}MCP Tools:{RESET}")
            for t in tools:
                print(f"    • {GREEN}{t}{RESET}")
        cmds = info.get("cli_cmds", [])
        if cmds:
            print(f"  {BOLD}CLI BAGO:{RESET}")
            for c in cmds:
                print(f"    {DIM}$ bago {c}{RESET}")
        print(f"{'─'*60}{RESET}\n")
    return 0


def show_agent(matrix: dict, agent_query: str) -> int:
    agents = matrix.get("agents", {})
    matched = {k: v for k, v in agents.items() if agent_query.upper() in k.upper()}
    if not matched:
        print(f"[work_matrix] Agente '{agent_query}' no encontrado.", file=sys.stderr)
        print(f"Agentes: {', '.join(agents.keys())}", file=sys.stderr)
        return 1

    for name, info in matched.items():
        color = _agent_color(name)
        print(f"\n{BOLD}{'─'*60}{RESET}")
        print(f"{BOLD}  AGENTE: {color}{name}{RESET}")
        print(f"{'─'*60}{RESET}")
        print(f"  {BOLD}Rol:{RESET}            {info.get('role', '—')}")
        print(f"  {BOLD}Archivo:{RESET}        {DIM}{info.get('file', '—')}{RESET}")
        print()
        for label, key in [("MCP Tools primarias", "primary_tools"), ("MCP Tools secundarias", "secondary_tools")]:
            tools = info.get(key, [])
            if tools:
                print(f"  {BOLD}{label}:{RESET}")
                for t in tools:
                    print(f"    • {GREEN}{t}{RESET}")
        cmds = info.get("cli_cmds", [])
        if cmds:
            print(f"  {BOLD}Comandos CLI:{RESET}")
            for c in cmds:
                print(f"    {DIM}$ bago {c}{RESET}")
        # Work types that use this agent
        work_types = matrix.get("work_types", {})
        my_types = [k for k, v in work_types.items() if v.get("agent") == name]
        if my_types:
            print(f"  {BOLD}Tipos de trabajo:{RESET} {', '.join(my_types)}")
        print(f"{'─'*60}{RESET}\n")
    return 0


def show_list_types(matrix: dict) -> None:
    work_types = matrix.get("work_types", {})
    print(f"\n{BOLD}Tipos de trabajo disponibles:{RESET}")
    for wtype, info in work_types.items():
        print(f"  {CYAN}{wtype:<20}{RESET} {info.get('label', '')}")
    print(f"\n{DIM}Usa: bago work_matrix --type <tipo>{RESET}\n")


def show_mcp_index(matrix: dict) -> None:
    index = matrix.get("mcp_tools_index", {})
    print(f"\n{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}  ÍNDICE DE HERRAMIENTAS MCP{RESET}")
    print(f"{BOLD}{'─'*70}{RESET}")
    print(f"  {'MCP TOOL':<22} {'CMD BAGO':<18} {'LAYER':<14} AGENTES")
    print(f"  {'─'*22} {'─'*18} {'─'*14} {'─'*20}")
    for tool, info in index.items():
        cmd = info.get("cmd") or "—"
        layer = info.get("layer", "?")
        agents = info.get("agents", [])
        agent_str = ", ".join(a.split("_")[0] for a in agents) if agents != ["ALL"] else "ALL"
        print(f"  {GREEN}{tool:<22}{RESET} {DIM}{cmd:<18}{RESET} {CYAN}{layer:<14}{RESET} {DIM}{agent_str}{RESET}")
    print(f"{BOLD}{'─'*70}{RESET}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Matriz de rutas de trabajo BAGO — qué agente y tools usar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--type", "-t", metavar="TIPO",
                        help="Mostrar ruta para un tipo de trabajo (code, quality, security...)")
    parser.add_argument("--agent", "-a", metavar="AGENTE",
                        help="Mostrar herramientas de un agente (ANALISTA, ARQUITECTO...)")
    parser.add_argument("--list-types", "-l", action="store_true",
                        help="Listar todos los tipos de trabajo disponibles")
    parser.add_argument("--mcp-tools", "-m", action="store_true",
                        help="Mostrar índice completo de herramientas MCP")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output JSON completo de la matriz")
    args = parser.parse_args()

    matrix = _load_matrix()

    if args.json:
        print(json.dumps(matrix, indent=2, ensure_ascii=False))
        return 0

    if args.list_types:
        show_list_types(matrix)
        return 0

    if args.mcp_tools:
        show_mcp_index(matrix)
        return 0

    if args.type:
        return show_work_type(matrix, args.type)

    if args.agent:
        return show_agent(matrix, args.agent)

    # Default: full matrix
    show_full_matrix(matrix)
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
    raise SystemExit(main())
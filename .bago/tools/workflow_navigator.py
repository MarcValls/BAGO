#!/usr/bin/env python3
"""workflow_navigator.py — Navegador de workflows BAGO.

Lee WORKFLOW_GRAPH.json y el estado actual del sistema para sugerir
el siguiente workflow más adecuado dado el contexto actual.

Uso:
    python3 workflow_navigator.py                    # sugiere workflow según estado
    python3 workflow_navigator.py --from w7_foco_sesion  # transiciones desde un workflow
    python3 workflow_navigator.py --list             # lista todos los nodos del grafo
    python3 workflow_navigator.py --graph            # muestra el grafo completo
    python3 workflow_navigator.py --test             # self-tests
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BAGO_ROOT   = Path(__file__).parent.parent
TOOLS_DIR   = BAGO_ROOT / "tools"
GRAPH_FILE  = BAGO_ROOT / "workflows" / "WORKFLOW_GRAPH.json"
STATE_FILE  = BAGO_ROOT / "state" / "global_state.json"

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_CYN  = "\033[0;36m"
_RST  = "\033[0m"
_BOLD = "\033[1m"


def _load_graph() -> dict:
    if not GRAPH_FILE.exists():
        return {}
    return json.loads(GRAPH_FILE.read_text("utf-8"))


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text("utf-8"))


# ── Lógica de sugerencia ───────────────────────────────────────────────────────

def _infer_current_workflow(state: dict) -> str | None:
    """Infiere el workflow más probable según el estado actual."""
    sprint = state.get("sprint_status", {})
    return sprint.get("active_workflow")


def suggest_next(state: dict | None = None) -> list[dict]:
    """Devuelve lista de workflows sugeridos con su justificación.

    Cada elemento: {"workflow_id": str, "label": str, "reason": str, "priority": int}
    """
    if state is None:
        state = _load_state()
    graph = _load_graph()
    if not graph:
        return []

    nodes   = graph.get("nodes", {})
    edges   = graph.get("edges", [])
    current = _infer_current_workflow(state)
    sprint  = state.get("sprint_status", {})
    pending = sprint.get("pending_w2_task", "")
    health  = state.get("last_validation", {})
    guardian = state.get("guardian_findings", {})
    health_pct = guardian.get("health_pct", 100)

    suggestions: list[dict] = []

    if current:
        # Transiciones válidas desde el workflow activo
        outgoing = [e for e in edges if e["from"] == current]
        for edge in outgoing:
            target_id = edge["to"]
            if target_id in nodes and not nodes[target_id].get("restricted"):
                suggestions.append({
                    "workflow_id": target_id,
                    "label":       nodes[target_id]["label"],
                    "reason":      edge["condition"],
                    "priority":    2,
                    "via":         edge["label"],
                })
    else:
        # Sin workflow activo — sugerir según contexto
        if pending:
            suggestions.append({
                "workflow_id": "w7_foco_sesion",
                "label":       nodes["w7_foco_sesion"]["label"],
                "reason":      f"tarea pendiente detectada: {pending[:80]}",
                "priority":    1,
                "via":         "tarea pendiente → sesión foco",
            })
        if health_pct < 60:
            suggestions.append({
                "workflow_id": "w2_implementacion_controlada",
                "label":       nodes["w2_implementacion_controlada"]["label"],
                "reason":      f"Guardian health {health_pct}% < 60% — requiere corrección técnica",
                "priority":    1,
                "via":         "guardian degradado → implementación controlada",
            })
        suggestions.append({
            "workflow_id": "w8_exploracion",
            "label":       nodes["w8_exploracion"]["label"],
            "reason":      "sin workflow activo ni tarea urgente — exploración libre",
            "priority":    3,
            "via":         "estado libre → exploración",
        })
        suggestions.append({
            "workflow_id": "w6_ideacion_aplicada",
            "label":       nodes["w6_ideacion_aplicada"]["label"],
            "reason":      "sin dirección clara — generar ideas contextualizadas",
            "priority":    3,
            "via":         "estado libre → ideación",
        })

    suggestions.sort(key=lambda x: x["priority"])
    return suggestions


def transitions_from(workflow_id: str) -> list[dict]:
    """Devuelve todas las transiciones posibles desde un workflow dado."""
    graph = _load_graph()
    edges = graph.get("edges", [])
    nodes = graph.get("nodes", {})
    result = []
    for edge in edges:
        if edge["from"] == workflow_id:
            target = nodes.get(edge["to"], {})
            result.append({
                "to":        edge["to"],
                "label":     target.get("label", edge["to"]),
                "condition": edge["condition"],
                "via":       edge["label"],
            })
    return result


# ── Presentación ───────────────────────────────────────────────────────────────

def _print_suggestions(suggestions: list[dict]) -> None:
    if not suggestions:
        print(f"\n  {_YEL}No hay sugerencias disponibles.{_RST}")
        return
    print(f"\n  {_BOLD}Workflows sugeridos:{_RST}")
    for i, s in enumerate(suggestions, 1):
        prio_color = _GRN if s["priority"] == 1 else (_YEL if s["priority"] == 2 else _CYN)
        print(f"\n  {prio_color}{i}. {s['label']}{_RST}  ({s['workflow_id']})")
        print(f"     {s['reason']}")
        print(f"     → vía: {s['via']}")


def _print_transitions(workflow_id: str, trans: list[dict]) -> None:
    print(f"\n  {_BOLD}Transiciones desde {workflow_id}:{_RST}")
    if not trans:
        print(f"  {_YEL}  Sin transiciones definidas.{_RST}")
        return
    for t in trans:
        print(f"\n  → {_GRN}{t['label']}{_RST}  ({t['to']})")
        print(f"     Condición: {t['condition']}")


def _print_node_list(nodes: dict) -> None:
    print(f"\n  {_BOLD}Workflows en el grafo ({len(nodes)}):{_RST}")
    for wid, node in nodes.items():
        restricted = " [RESTRINGIDO]" if node.get("restricted") else ""
        print(f"  {_CYN}{wid}{_RST}{restricted}")
        print(f"    {node['purpose'][:80]}")


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _run_tests() -> int:
    results: list[tuple[str, bool, str]] = []

    # T01 — grafo existe y tiene nodes + edges
    graph = _load_graph()
    t01 = bool(graph.get("nodes")) and bool(graph.get("edges"))
    results.append(("T01:graph_has_nodes_and_edges", t01, ""))

    # T02 — todos los edges referencian nodos existentes
    if graph:
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])
        broken_refs = [
            e for e in edges
            if e["from"] not in nodes or e["to"] not in nodes
        ]
        t02 = len(broken_refs) == 0
        results.append(("T02:edge_refs_valid", t02,
                         f"{len(broken_refs)} refs rotos" if broken_refs else ""))

    # T03 — suggest_next sin estado devuelve lista
    fake_state: dict = {}
    sugg = suggest_next(fake_state)
    t03 = isinstance(sugg, list) and len(sugg) > 0
    results.append(("T03:suggest_next_returns_list", t03, ""))

    # T04 — suggest_next con tarea pendiente prioriza w7
    state_w_task = {"sprint_status": {"pending_w2_task": "CHG-TEST"}}
    sugg_task = suggest_next(state_w_task)
    t04 = any(s["workflow_id"] == "w7_foco_sesion" for s in sugg_task)
    results.append(("T04:suggest_w7_when_task_pending", t04, ""))

    # T05 — transitions_from devuelve lista para nodo válido
    trans = transitions_from("w7_foco_sesion")
    t05 = isinstance(trans, list) and len(trans) > 0
    results.append(("T05:transitions_from_w7", t05, ""))

    # T06 — no hay nodo w0 en sugerencias normales (es restringido)
    sugg_all = suggest_next({})
    t06 = not any(s["workflow_id"] == "w0_free_session" for s in sugg_all)
    results.append(("T06:w0_not_suggested_normally", t06, ""))

    # T07 — grafo no tiene edges duplicados
    if graph:
        edges = graph.get("edges", [])
        seen = set()
        duplicates = 0
        for e in edges:
            key = (e["from"], e["to"])
            if key in seen:
                duplicates += 1
            seen.add(key)
        t07 = duplicates == 0
        results.append(("T07:no_duplicate_edges", t07,
                         f"{duplicates} duplicados" if duplicates else ""))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        sym = "✅" if ok else "❌"
        print(f"  {sym}  {name}" + (f": {detail}" if detail else ""))
    print(f"\n  {passed}/{len(results)} pasaron")

    output = {
        "tool": "workflow_navigator",
        "status": "ok" if failed == 0 else "fail",
        "checks": [{"name": n, "passed": ok} for n, ok, _ in results],
    }
    print(json.dumps(output))
    return 0 if failed == 0 else 1


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--test" in args:
        sys.exit(_run_tests())

    if "--list" in args:
        graph = _load_graph()
        _print_node_list(graph.get("nodes", {}))
        sys.exit(0)

    if "--graph" in args:
        graph = _load_graph()
        print(json.dumps(graph, indent=2, ensure_ascii=False))
        sys.exit(0)

    if "--from" in args:
        i = args.index("--from")
        wid = args[i + 1] if i + 1 < len(args) else ""
        if not wid:
            print("  Especifica un workflow_id con --from", file=sys.stderr)
            sys.exit(1)
        trans = transitions_from(wid)
        _print_transitions(wid, trans)
        sys.exit(0)

    # Default: sugerir workflow según estado actual
    state = _load_state()
    current = _infer_current_workflow(state)
    if current:
        print(f"\n  Workflow activo: {_BOLD}{current}{_RST}")
    else:
        print(f"\n  {_YEL}Sin workflow activo{_RST}")

    suggestions = suggest_next(state)
    _print_suggestions(suggestions)
    print()

#!/usr/bin/env python3
"""bago_dynamic_router.py — Dynamic router: Task → Type → Agent → Role → Tools → Model.

Integrates:
  - model_routing.json   (task keywords → provider + model)
  - agent_tool_matrix.json (task type → BAGO agent role + tools)
  - llm_config.json      (available models per provider)

Returns a complete routing decision with all dimensions.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
from pathlib import Path
from typing import Any

STATE_DIR = Path(__file__).resolve().parents[1] / "state"
ROUTING_FILE = STATE_DIR / "model_routing.json"
MATRIX_FILE = Path(__file__).resolve().parents[1] / "mcp" / "agent_tool_matrix.json"


def _read_json(path: Path, fallback: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return fallback


def _task_type(task: str) -> str:
    """Map free-form task to canonical BAGO task type."""
    text = task.lower()
    if any(k in text for k in ["partitura", "score", "musicxml", "transponer", "transpose", "arreglo", "midi", "nota", "compas"]):
        return "music"
    if any(k in text for k in ["pr", "pull request", "review", "diff", "revisar", "riesgo"]):
        return "quality"
    if any(k in text for k in ["test", "tests", "bug", "debug", "error", "fix"]):
        return "debug"
    if any(k in text for k in ["implementa", "implementar", "crea", "crear", "edita", "script", "archivo", "deploy"]):
        return "code"
    if any(k in text for k in ["arquitectura", "diseno", "router", "sistema", "estructura"]):
        return "architecture"
    if any(k in text for k in ["explica", "explicar", "resumen", "brainstorm", "idea", "plan"]):
        return "content"
    if any(k in text for k in ["instala", "configura", "servidor", "produccion"]):
        return "coordination"
    return "code"


def _match_rule(task: str) -> dict:
    """Match task against model_routing.json rules."""
    text = task.lower()
    rules = _read_json(ROUTING_FILE, {}).get("rules", [])
    best: dict | None = None
    best_hits = 0
    for rule in rules:
        hits = sum(1 for kw in rule.get("keywords", []) if kw.lower() in text)
        if hits > best_hits:
            best_hits = hits
            best = rule
    if best:
        return {
            "provider": best["provider"],
            "model": best["model"],
            "reason": best["reason"],
            "rule_id": best["id"],
        }
    fb = _read_json(ROUTING_FILE, {}).get("fallback", {})
    return {
        "provider": fb.get("provider", "codex"),
        "model": fb.get("model", "gpt-5.4"),
        "reason": "Fallback",
        "rule_id": "fallback",
    }


def _agent_role(task_type: str) -> dict:
    """Map task type to BAGO agent role from agent_tool_matrix.json."""
    matrix = _read_json(MATRIX_FILE, {})
    agents = matrix.get("agents", {})
    tools_map = matrix.get("tools", {})

    # Find best matching agent by role keywords
    role_map = {
        "music": "GENERADOR_Contenido",
        "quality": "ANALISTA_Contexto",
        "debug": "ANALISTA_Contexto",
        "code": "ARQUITECTO_Soluciones",
        "architecture": "ARQUITECTO_Soluciones",
        "content": "GENERADOR_Contenido",
        "coordination": "ORGANIZADOR_Entregables",
    }

    role_id = role_map.get(task_type, "ADAPTADOR_PROYECTO")
    agent_def = agents.get(role_id, {})

    # Get tools for this task type
    primary_tools = agent_def.get("primary_tools", []) if isinstance(agent_def.get("primary_tools"), list) else agent_def.get("primary_tools", "").split()
    secondary_tools = agent_def.get("secondary_tools", []) if isinstance(agent_def.get("secondary_tools"), list) else agent_def.get("secondary_tools", "").split()
    all_tools = primary_tools + secondary_tools

    # Filter to tools that mention this task type
    type_tools = []
    for tool_name, tool_def in tools_map.items():
        if tool_name.replace("bago_", "") in all_tools or tool_name in all_tools:
            type_tools.append({
                "name": tool_name,
                "cmd": tool_def.get("cmd"),
                "layer": tool_def.get("layer"),
            })

    return {
        "role_id": role_id,
        "role_name": agent_def.get("role", role_id),
        "role_file": agent_def.get("file", ""),
        "primary_tools": primary_tools,
        "secondary_tools": secondary_tools,
        "type_tools": type_tools,
    }


def dynamic_route(task: str, available_agents: list[dict] | None = None) -> dict:
    """Full dynamic router: returns complete routing decision.

    Dimensions:
      - task_type: canonical BAGO task type
      - provider:  execution provider (codex, copilot, ollama-local, etc.)
      - model:     specific model name
      - agent:     execution agent id
      - role:      BAGO agent role (ANALISTA, ARQUITECTO, etc.)
      - tools:     recommended BAGO tools for this task
      - confidence: routing confidence (0-100)
    """
    task_type = _task_type(task)
    rule = _match_rule(task)
    role = _agent_role(task_type)

    provider = rule["provider"]
    model = rule["model"]

    # Map provider to agent id
    provider_to_agent = {
        "codex": "codex",
        "copilot": "copilot",
        "ollama-local": "ollama",
        "ollama-cloud": "ollama-cloud",
        "openclaw": "codex",
        "local": "ollama",
    }
    agent_id = provider_to_agent.get(provider, provider)

    # Check if agent is available
    available_ids = {a["id"] for a in (available_agents or []) if a.get("available")}
    fallback_chain = []
    if agent_id not in available_ids and available_agents:
        # Find closest available
        for preferred in ["codex", "copilot", "ollama", "ollama-cloud"]:
            if preferred in available_ids:
                agent_id = preferred
                model = _agent_first_model(preferred, available_agents)
                break
        fallback_chain = [rule["provider"], agent_id]
    else:
        fallback_chain = [agent_id]

    # Confidence based on rule match quality
    confidence = 92 if rule["rule_id"] != "fallback" else 65

    return {
        "task": task,
        "task_type": task_type,
        "agent": agent_id,
        "model": model,
        "provider": provider,
        "role": role["role_id"],
        "role_name": role["role_name"],
        "role_file": role["role_file"],
        "tools": role["type_tools"],
        "primary_tools": role["primary_tools"],
        "secondary_tools": role["secondary_tools"],
        "confidence": confidence,
        "reason": rule["reason"],
        "rule_id": rule["rule_id"],
        "fallback_chain": fallback_chain,
    }


def _agent_first_model(agent_id: str, agents: list[dict]) -> str:
    for a in agents:
        if a.get("id") == agent_id and a.get("models"):
            return a["models"][0]
    return "gpt-5.4"


def print_route(task: str, available_agents: list[dict] | None = None) -> None:
    d = dynamic_route(task, available_agents)
    print()
    print("  BAGO Dynamic Router")
    print("  " + "-" * 50)
    print(f"  Tarea     : {d['task']}")
    print(f"  Tipo      : {d['task_type']}")
    print(f"  Agente    : {d['agent']}")
    print(f"  Modelo    : {d['model']}")
    print(f"  Rol       : {d['role']} — {d['role_name']}")
    print(f"  Confianza : {d['confidence']}%")
    print(f"  Regla     : {d['rule_id']}")
    print(f"  Motivo    : {d['reason']}")
    if d['fallback_chain'] and len(d['fallback_chain']) > 1:
        print(f"  Fallback  : {' -> '.join(d['fallback_chain'])}")
    if d['tools']:
        print(f"  Tools     : {', '.join(t['name'] for t in d['tools'][:5])}")
    print()


if __name__ == "__main__":
    agents = [
        {"id": "ollama", "available": True, "models": ["qwen2.5-coder:7b"]},
        {"id": "codex", "available": True, "models": ["gpt-5.5", "gpt-5.4", "gpt-5.3-codex"]},
        {"id": "copilot", "available": True, "models": ["claude-sonnet-4.6", "claude-opus-4.7"]},
    ]
    tests = [
        "transponer partitura de piano a Mi menor",
        "revisar esta partitura de bajo",
        "implementar login en varios archivos",
        "brainstorm ideas para arreglo musical",
        "explicame este error de python",
        "analizar repo completo de partituras",
        "render preview de score",
        "auditoria de seguridad del codigo",
    ]
    for t in tests:
        print_route(t, agents)

#!/usr/bin/env python3
"""bago_orchestrator.py — Selecciona modelo óptimo según tarea, disponibilidad y coste.

Integra:
  - model_providers.json    (catálogo de modelos)
  - model_orchestrator.json (política de selección)
  - model_routing.json      (reglas por keyword)
  - Detección de health de proveedores

Uso:
  python bago_orchestrator.py [--mode offline|economico|estandar|full] [tarea]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parents[1] / "state"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _check_provider(name: str, cmd: str) -> bool:
    """Ejecuta health check de un proveedor."""
    try:
        if "curl" in cmd:
            result = subprocess.run(cmd.split(), capture_output=True, timeout=5)
            return result.returncode == 0
        else:
            result = subprocess.run(cmd.split(), capture_output=True, timeout=5)
            return result.returncode == 0
    except Exception:
        return False


def detect_providers(providers: dict, health_checks: dict) -> dict:
    """Detecta qué proveedores están disponibles."""
    available = {}
    for name, cmd in health_checks.items():
        available[name] = _check_provider(name, cmd)
    return available


def select_mode(auto_rules: list, providers_available: dict, args_mode: str | None) -> str:
    """Selecciona modo: explícito o automático."""
    if args_mode:
        return args_mode
    # Auto-detect
    ollama_local = providers_available.get("ollama-local", False)
    ollama_cloud = providers_available.get("ollama-cloud", False)
    copilot = providers_available.get("copilot", False)
    codex = providers_available.get("codex", False)
    internet = ollama_cloud or copilot or codex

    if ollama_local and not internet:
        return "offline"
    if ollama_local and internet and not codex:
        return "economico"
    if ollama_local and internet and codex:
        return "estandar"
    if all([ollama_local, ollama_cloud, copilot, codex]):
        return "full"
    return "offline"  # fallback seguro


def orchestrate(task: str, mode_name: str | None = None) -> dict:
    """Orquestador principal: selecciona modelo óptimo."""
    providers_data = _read_json(STATE_DIR / "model_providers.json")
    orchestrator = _read_json(STATE_DIR / "model_orchestrator.json")
    routing = _read_json(STATE_DIR / "model_routing.json")

    modes = orchestrator.get("modes", {})
    health_checks = orchestrator.get("health_checks", {})
    task_prefs = orchestrator.get("task_preference", {})
    auto_rules = orchestrator.get("auto_mode_selection", {}).get("rules", [])

    # 1. Detectar proveedores disponibles
    providers_available = detect_providers(providers_data.get("providers", {}), health_checks)

    # 2. Seleccionar modo
    mode = select_mode(auto_rules, providers_available, mode_name)
    mode_config = modes.get(mode, modes.get("offline", {}))

    # 3. Encontrar regla de routing por tarea
    text = task.lower()
    route = None
    for rule in routing.get("rules", []):
        hits = sum(1 for kw in rule.get("keywords", []) if kw.lower() in text)
        if hits >= 1:
            route = rule
            break

    # 4. Encontrar preferencia de tarea
    task_type = None
    for pref_name, pref in task_prefs.items():
        if any(kw in text for kw in pref.get("keywords", [])):
            task_type = pref_name
            break
    if not task_type and route:
        task_type = route.get("id", "")

    # 5. Filtrar modelos por modo (allowed_providers)
    allowed = set(mode_config.get("allowed_providers", []))
    candidates = []
    for prov_name, prov in providers_data.get("providers", {}).items():
        if prov_name not in allowed:
            continue
        if not providers_available.get(prov_name, False):
            continue
        for model_name, model in prov.get("models", {}).items():
            candidates.append({
                "name": model_name,
                "provider": prov_name,
                "wire_name": model.get("wire_name", model_name),
                "cost": model.get("cost", "unknown"),
                "best_for": model.get("best_for", ""),
                "tokens": model.get("max_prompt_tokens", 0),
                "size_mb": model.get("size_mb", 0),
            })

    # 6. Scorear candidatos
    def score(c):
        s = 0
        # Coste: menor es mejor
        cost_order = {"free": 0, "included": 1, "subscription": 2, "openai_credits": 3}
        s += (3 - cost_order.get(c["cost"], 3)) * 10
        # Preferencia de tarea
        if task_type and c["name"] in task_prefs.get(task_type, {}).get("models", []):
            s += 25
        # Complejidad de tarea: si es compleja, penalizar modelos mini
        complex_tasks = ["code_complex", "code_frontier", "review_deep", "music_edit", "long_context"]
        simple_tasks = ["code_fast", "brainstorm", "music_render"]
        if task_type in complex_tasks:
            if "mini" in c["name"] or c["size_mb"] < 1000:
                s -= 15  # Penalizar mini para tareas complejas
            else:
                s += 10  # Bonus para modelos grandes
        if task_type in simple_tasks:
            if "mini" in c["name"] or c["size_mb"] < 1000:
                s += 15  # Bonus para mini en tareas simples
        return s

    candidates.sort(key=score, reverse=True)

    if not candidates:
        return {
            "error": "No hay modelos disponibles para el modo '$mode'",
            "mode": mode,
            "providers_available": providers_available,
        }

    best = candidates[0]
    return {
        "task": task,
        "mode": mode,
        "model": best["name"],
        "provider": best["provider"],
        "wire_name": best["wire_name"],
        "cost": best["cost"],
        "reason": f"Modo: {mode}. Mejor score por coste y disponibilidad." + (f" Tarea: {task_type}" if task_type else ""),
        "alternatives": [c["name"] for c in candidates[1:4]],
        "providers_available": providers_available,
        "candidates_count": len(candidates),
    }


def print_orchestration(task: str, mode: str | None = None) -> None:
    result = orchestrate(task, mode)
    if "error" in result:
        print(f"\n  ERROR {result['error']}")
        print(f"     Proveedores: {result['providers_available']}")
        return

    print(f"\n  BAGO Orchestrator")
    print(f"  {'-'*46}")
    print(f"  Tarea:      {result['task']}")
    print(f"  Modo:       {result['mode']}")
    print(f"  Modelo:     {result['model']} [{result['provider']}]")
    print(f"  Wire:       {result['wire_name']}")
    print(f"  Coste:      {result['cost']}")
    print(f"  Razón:      {result['reason']}")
    if result['alternatives']:
        print(f"  Alternativas: {', '.join(result['alternatives'])}")
    print(f"  Candidatos: {result['candidates_count']}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BAGO Model Orchestrator")
    parser.add_argument("task", nargs="?", default="transponer partitura", help="Tarea a orquestar")
    parser.add_argument("--mode", choices=["offline", "economico", "estandar", "full"], help="Forzar modo")
    parser.add_argument("--check", action="store_true", help="Solo ver disponibilidad")
    args = parser.parse_args()

    if args.check:
        providers_data = _read_json(STATE_DIR / "model_providers.json")
        orchestrator = _read_json(STATE_DIR / "model_orchestrator.json")
        health = detect_providers(providers_data.get("providers", {}), orchestrator.get("health_checks", {}))
        print("\n  Disponibilidad de proveedores:")
        for name, ok in health.items():
            icon = "OK" if ok else "NO"
            print(f"    {icon} {name}")
        print()
    else:
        print_orchestration(args.task, args.mode)

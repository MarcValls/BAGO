#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from bago.providers import best_model_for_provider, detect_strategy  # type: ignore
from bago.routing_runtime import active_settings, apply_preset, load_presets, resolve_contract, validate_contract, load_providers_snapshot  # type: ignore
from bago_dynamic_router import dynamic_route  # type: ignore


def _available_agents(providers: dict) -> list[dict]:
    out = []
    provider_to_agent = {
        "codex": "codex",
        "copilot": "copilot",
        "ollama-local": "ollama",
        "ollama-cloud": "ollama-cloud",
    }
    for prov, pdata in providers.items():
        models = list((pdata or {}).get("models", {}).keys())
        out.append({
            "id": provider_to_agent.get(prov, prov),
            "available": bool(models),
            "models": models,
        })
    return out


def _best_model_name(provider: str, providers: dict) -> str:
    best = best_model_for_provider(provider, providers)
    return best[0] if best else "?"


def _candidate_chain(task: str, providers: dict, preset: dict, decision: dict, strategy: str, strategy_providers: list[str]) -> list[str]:
    order = []
    primary = f"{decision.get('provider', '?')}/{decision.get('model', '?')}"
    order.append(primary)
    for prov in strategy_providers:
        order.append(f"{prov}/{_best_model_name(prov, providers)}")
    for prov in preset.get("provider_order", []):
        order.append(f"{prov}/{_best_model_name(prov, providers)}")
    for item in decision.get("fallback_chain", []):
        mapped = {"ollama": "ollama-local", "codex": "codex", "copilot": "copilot", "ollama-cloud": "ollama-cloud"}.get(item, item)
        order.append(f"{mapped}/{_best_model_name(mapped, providers)}")
    dedup = []
    seen = set()
    for item in order:
        if item.endswith('/?'):
            continue
        if item not in seen:
            seen.add(item)
            dedup.append(item)
    return dedup


def _render_graph(task: str, preset_name: str, preset: dict, decision: dict, strategy: str, strategy_providers: list[str], contract_text: str, contract_eval: dict, chain: list[str]) -> str:
    lines = []
    lines.append("")
    lines.append("  BAGO Route Graph")
    lines.append("  " + "=" * 62)
    lines.append(f"  Preset   : {preset_name}  |  orch={preset.get('orch_mode', '?')}")
    lines.append(f"  Tarea    : {task}")
    lines.append("")
    lines.append("  [INPUT]")
    lines.append("     |")
    lines.append(f"     v")
    lines.append(f"  [ANALYZER] type={decision.get('task_type')}  rule={decision.get('rule_id')}  conf={decision.get('confidence')}%")
    lines.append("     |")
    lines.append(f"     +--> primary: {decision.get('provider')}/{decision.get('model')}")
    lines.append(f"     +--> role   : {decision.get('role')} ({decision.get('role_name')})")
    if decision.get("tools"):
        tool_names = ", ".join(t.get("name", "?") for t in decision["tools"][:4])
        lines.append(f"     +--> tools  : {tool_names}")
    lines.append("     |")
    lines.append(f"     v")
    lines.append(f"  [STRATEGY] {strategy}")
    if strategy_providers:
        lines.append(f"     | providers: {' -> '.join(strategy_providers)}")
    lines.append(f"     v")
    lines.append("  [MODEL CHAIN]")
    for idx, item in enumerate(chain, start=1):
        marker = "*" if idx == 1 else "+"
        lines.append(f"     {marker} {idx}. {item}")
    loop_cfg = preset.get("contract_loop", {})
    lines.append("     |")
    lines.append(f"     v")
    lines.append(f"  [CONTRACT LOOP] enabled={loop_cfg.get('enabled')}  max_iter={loop_cfg.get('max_iter')}  min_score={loop_cfg.get('min_score')}")
    if contract_text:
        first = contract_text.splitlines()[0]
        lines.append(f"     | contract: {first[:70]}")
    else:
        lines.append("     | contract: (no explicito; se inferira desde la entrada)")
    lines.append(f"     v")
    lines.append(f"  [GATE] score={contract_eval.get('score')}  ok={contract_eval.get('ok')}")
    if contract_eval.get("unmet"):
        for unmet in contract_eval["unmet"][:4]:
            lines.append(f"     - unmet: {unmet}")
    lines.append("     |")
    lines.append("     v")
    lines.append("  [OUTPUT] cerrar solo cuando el gate cumpla el contrato")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visualiza routing BAGO como grafo de nodos")
    parser.add_argument("--task", default="")
    parser.add_argument("--preset", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--contract", default="")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args(argv)

    presets = load_presets()
    if args.test:
        print("route_graph self-test OK" if presets else "route_graph self-test FAIL")
        return 0 if presets else 1

    if args.list_presets:
        print()
        print("  BAGO routing presets")
        print("  " + "-" * 50)
        for name, info in presets.items():
            print(f"  {name:<18} {info.get('description', '')}")
        print()
        return 0

    if args.preset and args.apply:
        apply_preset(args.preset)

    settings = active_settings()
    preset_name = args.preset or settings["preset_name"]
    preset = presets.get(preset_name, presets[settings["preset_name"]])
    providers = load_providers_snapshot()

    task = args.task.strip()
    if not task:
        print("Uso: bago route-graph --task \"tu tarea\"", file=sys.stderr)
        return 1

    decision = dynamic_route(task, _available_agents(providers))
    active_provider_ids = [p for p, pdata in providers.items() if (pdata or {}).get("models")]
    strategy, strategy_providers = detect_strategy(task, active_provider_ids)
    contract_text = resolve_contract(task, args.contract)
    contract_eval = validate_contract(contract_text, "")
    chain = _candidate_chain(task, providers, preset, decision, strategy, strategy_providers)

    payload = {
        "task": task,
        "preset": preset_name,
        "decision": decision,
        "strategy": strategy,
        "strategy_providers": strategy_providers,
        "contract": contract_text,
        "contract_gate": contract_eval,
        "candidate_chain": chain,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(_render_graph(task, preset_name, preset, decision, strategy, strategy_providers, contract_text, contract_eval, chain))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""agent_model_manager.py — Gestión dinámica de modelos por agente BAGO.

Permite asignar, consultar y listar el modelo LLM que usa cada agente BAGO.

Uso:
  python agent_model_manager.py list
  python agent_model_manager.py get agent_tools
  python agent_model_manager.py set agent_tools claude-opus-4.7
  python agent_model_manager.py models           # lista modelos disponibles
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import json
import sys
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
_TOOLS_DIR     = Path(__file__).resolve().parent
_BAGO_DIR      = _TOOLS_DIR.parent
_STATE_DIR     = _BAGO_DIR / "state"
_LLM_CFG       = _STATE_DIR / "llm_config.json"
_AGENTS_REG    = _STATE_DIR / "agents_registry.json"

# ── Colores ───────────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

BOLD    = lambda t: _c("1", t)
GREEN   = lambda t: _c("1;32", t)
YELLOW  = lambda t: _c("1;33", t)
CYAN    = lambda t: _c("1;36", t)
RED     = lambda t: _c("1;31", t)
DIM     = lambda t: _c("2", t)

# ── Iconos por categoría ──────────────────────────────────────────────────────
_CATEGORY_ICON = {
    "tools": "🔧",
    "tests": "🧪",
    "docs":  "📝",
    "ops":   "⚙️ ",
}

# ── I/O helpers ───────────────────────────────────────────────────────────────

def _load_json(path: Path, fallback: dict | list) -> dict | list:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(RED(f"[ERROR] No se pudo leer {path}: {e}"), file=sys.stderr)
    return fallback


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── Lógica principal ──────────────────────────────────────────────────────────

def load_llm_config() -> dict:
    return _load_json(_LLM_CFG, {})


def load_agents_registry() -> dict:
    return _load_json(_AGENTS_REG, {})


def all_available_models(cfg: dict) -> list[str]:
    """Devuelve lista plana de todos los modelos conocidos."""
    models: list[str] = []
    for group in cfg.get("available_models", {}).values():
        models.extend(group)
    return models


def get_agent_model(agent_id: str) -> str | None:
    """Devuelve el modelo asignado al agente (prioridad: registry > llm_config)."""
    registry = load_agents_registry()
    agent = registry.get(agent_id)
    if agent and isinstance(agent, dict):
        if agent.get("model"):
            return agent["model"]
    cfg = load_llm_config()
    return cfg.get("agent_models", {}).get(agent_id)


def set_agent_model(agent_id: str, model: str) -> tuple[bool, str]:
    """Asigna un modelo a un agente. Actualiza registry + llm_config."""
    cfg = load_llm_config()
    registry = load_agents_registry()

    # Validar que el modelo es conocido
    known = all_available_models(cfg)
    if known and model not in known:
        return False, f"Modelo '{model}' no está en la lista de modelos disponibles."

    # Validar que el agente existe
    if agent_id not in registry or not isinstance(registry.get(agent_id), dict):
        return False, f"Agente '{agent_id}' no encontrado en agents_registry.json."

    # Actualizar registry
    registry[agent_id]["model"] = model
    _save_json(_AGENTS_REG, registry)

    # Actualizar llm_config
    if "agent_models" not in cfg:
        cfg["agent_models"] = {}
    cfg["agent_models"][agent_id] = model
    _save_json(_LLM_CFG, cfg)

    return True, f"Modelo de {agent_id} → {model}"


# ── Comandos CLI ──────────────────────────────────────────────────────────────

def cmd_list(_args: argparse.Namespace) -> int:
    registry = load_agents_registry()
    cfg = load_llm_config()
    agent_models_cfg = cfg.get("agent_models", {})

    agents = {k: v for k, v in registry.items() if isinstance(v, dict) and k != "_meta"}
    if not agents:
        print(YELLOW("No hay agentes registrados."))
        return 0

    print(BOLD("\n🤖 BAGO Agents — Modelos asignados\n"))
    print(f"  {'ID':<18} {'CATEGORÍA':<10} {'MODELO':<30} {'ESTADO'}")
    print("  " + "─" * 72)

    for agent_id, info in sorted(agents.items()):
        cat  = info.get("category", "")
        icon = _CATEGORY_ICON.get(cat, "◈")
        model_from_reg = info.get("model", "")
        model_from_cfg = agent_models_cfg.get(agent_id, "")
        model = model_from_reg or model_from_cfg or DIM("(sin asignar)")
        active = GREEN("activo") if info.get("active") else DIM("inactivo")
        print(f"  {CYAN(agent_id):<27} {icon} {cat:<9} {YELLOW(model):<39} {active}")

    print()
    print(DIM(f"  Config: {_LLM_CFG}"))
    print(DIM(f"  Registry: {_AGENTS_REG}"))
    print()
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    model = get_agent_model(args.agent_id)
    if model:
        print(f"{CYAN(args.agent_id)} → {GREEN(model)}")
    else:
        print(YELLOW(f"Agente '{args.agent_id}' no tiene modelo asignado."))
        return 1
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    ok, msg = set_agent_model(args.agent_id, args.model)
    if ok:
        print(GREEN(f"✓ {msg}"))
    else:
        print(RED(f"✗ {msg}"))
        return 1
    return 0


def cmd_models(_args: argparse.Namespace) -> int:
    cfg = load_llm_config()
    available = cfg.get("available_models", {})
    if not available:
        print(YELLOW("No hay modelos configurados en llm_config.json"))
        return 1

    print(BOLD("\n📋 Modelos disponibles\n"))
    for group, models in available.items():
        print(f"  {CYAN(group)}:")
        for m in models:
            print(f"    {DIM('·')} {m}")
    print()
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gestión dinámica de modelos por agente BAGO",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list",   help="Lista agentes y sus modelos asignados")
    sub.add_parser("models", help="Lista todos los modelos disponibles")

    p_get = sub.add_parser("get", help="Obtiene el modelo de un agente")
    p_get.add_argument("agent_id", help="ID del agente (ej: agent_tools)")

    p_set = sub.add_parser("set", help="Asigna un modelo a un agente")
    p_set.add_argument("agent_id", help="ID del agente (ej: agent_tools)")
    p_set.add_argument("model",    help="Modelo a asignar (ej: claude-opus-4.7)")

    args = parser.parse_args()

    if args.command == "list":
        return cmd_list(args)
    elif args.command == "get":
        return cmd_get(args)
    elif args.command == "set":
        return cmd_set(args)
    elif args.command == "models":
        return cmd_models(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

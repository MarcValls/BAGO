#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera demostraciones sintéticas para entrenar BCPolicy del tool orchestrator.

Cada transición simula una tarea de usuario, la herramienta óptima para resolverla,
y una recompensa alta para permitir bootstrap de BC cuando no hay logs reales.

Uso:
    python generate_synthetic_tool_demos.py --episodes 500 --output .bago/rl/logs/synthetic_tool_demos.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

_RL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RL_DIR))

from adapters.orchestrator.tool_schemas import TOOL_NAMES

# Mapeo semántico: palabras clave del dominio -> herramienta óptima + sinónimos
TASK_TEMPLATES = [
    # bago_search
    ("Busca donde se configura el timeout de red en este proyecto", "bago_search", 0.95),
    ("Encuentra todos los archivos relacionados con autenticación", "bago_search", 0.92),
    ("Quiero saber dónde se define el routing de modelos", "bago_search", 0.90),
    ("Localiza la configuración de Ollama y los providers", "bago_search", 0.93),
    ("Dime dónde está la lógica de health check", "bago_search", 0.88),
    ("Search for anything related to environment variables", "bago_search", 0.85),
    ("Find config files about secrets or credentials", "bago_search", 0.91),
    # bago_list
    ("Lista todos los scripts en .bago/tools con sus tamaños", "bago_list", 0.94),
    ("Muéstrame el árbol de directorios del proyecto", "bago_list", 0.96),
    ("Dame un listado de los archivos modificados recientemente en git", "bago_list", 0.90),
    ("List all Python files under adapters/orchestrator", "bago_list", 0.89),
    ("Quiero ver los archivos de estado JSON", "bago_list", 0.87),
    # bago_read
    ("Lee el archivo global_state.json y muéstrame su contenido", "bago_read", 0.95),
    ("Abre bago_tool_orchestrator.py y dime qué hace", "bago_read", 0.93),
    ("Read the release notes file", "bago_read", 0.90),
    ("Muestrame el contenido de validate.py", "bago_read", 0.92),
    ("Quiero leer el README del módulo RL", "bago_read", 0.88),
    # bago_call_search
    ("Busca la definición de la función orchestrate_task", "bago_call_search", 0.94),
    ("Encuentra todas las clases que heredan de BasePolicy", "bago_call_search", 0.91),
    ("Find where compute_reward is defined", "bago_call_search", 0.90),
    ("Dime dónde se llama a ollama_client.chat", "bago_call_search", 0.89),
    ("Busca métodos relacionados con train_bandit", "bago_call_search", 0.87),
    # bago_grep_smart
    ("Haz grep de todas las asignaciones de la variable alpha", "bago_grep_smart", 0.92),
    ("Encuentra todos los comentarios TODO en el código", "bago_grep_smart", 0.90),
    ("Grep for every import of numpy", "bago_grep_smart", 0.88),
    ("Busca strings que contengan 'ollama' en los fuentes", "bago_grep_smart", 0.85),
    ("Localiza todas las llamadas a print o logging", "bago_grep_smart", 0.86),
]


def generate_task(template: str) -> str:
    """Añade variación sintáctica menor a una plantilla de tarea."""
    prefixes = ["", "Por favor, ", "Necesito que ", "¿Puedes ", "Dime: "]
    suffixes = ["", "?", " rápido", " por favor", " ahora mismo"]
    return random.choice(prefixes) + template + random.choice(suffixes)


def build_transition(task: str, tool: str, reward: float, step: int = 0) -> dict:
    return {
        "timestamp": "2026-05-29T12:00:00",
        "session_id": "synthetic_demo",
        "user_task": task,
        "step": step,
        "action": {"tool": tool, "args": {"query": task, "interactive": False}},
        "result": {"status": "success", "output": f"Resultado simulado de {tool}"},
        "reward": reward,
        "model_used": "synthetic_demo",
        "domain": "mixed",
    }


def generate_demos(n_episodes: int, output_path: Path) -> None:
    random.seed(42)
    episodes = 0
    written = 0
    with open(output_path, "w", encoding="utf-8") as f:
        while episodes < n_episodes:
            for template, tool, base_reward in TASK_TEMPLATES:
                if episodes >= n_episodes:
                    break
                task = generate_task(template)
                reward = min(base_reward + random.uniform(-0.05, 0.05), 1.0)
                tr = build_transition(task, tool, reward, step=0)
                f.write(json.dumps(tr, ensure_ascii=False) + "\n")
                written += 1
                episodes += 1
    print(f"[OK] {written} transiciones sintéticas escritas en {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera demostraciones sintéticas para tool orchestrator BC")
    parser.add_argument("--episodes", type=int, default=500, help="Número de episodios/transiciones")
    parser.add_argument("--output", type=Path, default=_RL_DIR / "logs" / "synthetic_tool_demos.jsonl",
                        help="Ruta de salida JSONL")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    generate_demos(args.episodes, args.output)


if __name__ == "__main__":
    main()

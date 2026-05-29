# -*- coding: utf-8 -*-
"""rl_logger.py — Logging de transiciones RL y cálculo de recompensa compuesta."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

LOGS_DIR = Path(__file__).resolve().parents[3] / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TRANSITIONS_FILE = LOGS_DIR / "tool_orchestrator_transitions.jsonl"


def compute_reward(tool_result: dict, user_satisfaction: int | None = None) -> float:
    """Recompensa compuesta: éxito técnico + calidad de salida + feedback usuario."""
    r = 0.0
    if tool_result.get("success"):
        r += 0.5
    stdout_len = len(tool_result.get("stdout", ""))
    if 100 < stdout_len < 4000:
        r += 0.3
    if user_satisfaction is not None:
        r += (user_satisfaction / 5.0) * 0.5
    return min(r, 1.0)


def log_transition(transition: dict) -> None:
    """Append transition to RL log para futuro entrenamiento."""
    with open(TRANSITIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(transition, ensure_ascii=False) + "\n")


def build_transition(
    model: str,
    user_task: str,
    step: int,
    messages: list[dict],
    tool_name: str,
    args: dict[str, Any],
    tool_result: dict,
    user_satisfaction: int | None = None,
) -> dict:
    """Construye una transición completa lista para loggear."""
    return {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "user_task": user_task,
        "step": step,
        "context": [m["content"] for m in messages[-3:]],
        "action": {"tool": tool_name, "args": args},
        "result": {
            "success": tool_result["success"],
            "exit_code": tool_result["exit_code"],
            "output_length": len(tool_result.get("stdout", ""))
        },
        "reward": compute_reward(tool_result, user_satisfaction),
    }

#!/usr/bin/env python3
"""bago_adaptive_engine.py — Motor BAGO Balanceado Adaptativo (B/A).

Principios:
  B = Balanceado: distribuye carga entre agentes, evita saturar uno solo.
  A = Adaptativo: ajusta timeouts y seleccion basado en historial real.

Persiste en: .bago/state/execution_history.jsonl
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parents[1] / "state"
HISTORY_FILE = STATE_DIR / "execution_history.jsonl"


def _load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(l) for l in lines if l.strip()]


def _save_event(event: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def get_percentile_durations(task_type: str, agent: str, percentile: float = 0.8) -> int:
    """Devuelve duracion en ms en el percentil dado para (task_type, agent)."""
    history = _load_history()
    values = [
        h["duration_ms"]
        for h in history
        if h.get("task_type") == task_type and h.get("agent") == agent and h.get("success")
    ]
    if not values:
        return 0
    values.sort()
    idx = int(len(values) * percentile)
    idx = min(idx, len(values) - 1)
    return values[idx]


def adaptive_timeout(task_type: str, agent: str, base: int, min_ms: int = 5000, max_ms: int = 120000) -> int:
    """Ajusta timeout basado en historial (percentil 80) con margen 1.5x."""
    p80 = get_percentile_durations(task_type, agent, 0.8)
    if p80 == 0:
        return base
    suggested = int(p80 * 1.5)
    return max(min_ms, min(max_ms, suggested))


def agent_score(agent_id: str, window_hours: float = 1.0) -> float:
    """Score 0-100 basado en tasa de exito reciente. Penaliza fallos."""
    history = _load_history()
    cutoff = time.time() - (window_hours * 3600)
    recent = [h for h in history if h.get("agent") == agent_id and h.get("timestamp", 0) > cutoff]
    if not recent:
        return 75.0  # neutro
    ok = sum(1 for h in recent if h.get("success"))
    rate = ok / len(recent)
    # Penalizacion exponencial por fallos consecutivos
    consecutive_fails = 0
    for h in reversed(recent):
        if not h.get("success"):
            consecutive_fails += 1
        else:
            break
    penalty = min(0.4, consecutive_fails * 0.15)
    score = (rate * 100) - (penalty * 100)
    return max(0.0, score)


def pick_balanced_agent(candidates: list[dict], task_type: str) -> dict:
    """Elige agente balanceado: reglas del router + score adaptativo."""
    if not candidates:
        return {}
    scored = []
    for c in candidates:
        aid = c.get("id", c.get("agent", ""))
        base_score = c.get("score", 50)
        adaptive = agent_score(aid)
        # Mezcla: 60% reglas + 40% historial adaptativo
        final = (base_score * 0.6) + (adaptive * 0.4)
        scored.append({**c, "adaptive_score": final, "agent_id": aid})
    scored.sort(key=lambda x: x["adaptive_score"], reverse=True)
    return scored[0]


def record_execution(task: str, task_type: str, agent: str, model: str, success: bool, duration_ms: int, error: str = "") -> None:
    """Guarda evento para que la siguiente ejecucion sea mas adaptativa."""
    event = {
        "timestamp": time.time(),
        "task": task,
        "task_type": task_type,
        "agent": agent,
        "model": model,
        "success": success,
        "duration_ms": duration_ms,
        "error": error,
    }
    _save_event(event)


def print_adaptive_summary(task_type: str, agent: str) -> None:
    p50 = get_percentile_durations(task_type, agent, 0.5)
    p80 = get_percentile_durations(task_type, agent, 0.8)
    score = agent_score(agent)
    print(f"  [Adaptativo] Historial {task_type}/{agent}: p50={p50}ms p80={p80}ms score={score:.1f}")


if __name__ == "__main__":
    print("BAGO Adaptive Engine")
    print_adaptive_summary("music", "copilot")

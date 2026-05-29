#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_tool_env.py — Entorno RL para aprender a seleccionar herramientas BAGO.

Lee transiciones generadas por bago_tool_orchestrator.py y las convierte
en un entorno Gymnasium donde un agente aprende a predecir la mejor herramienta
para una tarea dada.

Acciones: 5 herramientas de análisis
  0 = bago_search
  1 = bago_list
  2 = bago_read
  3 = bago_call_search
  4 = bago_grep_smart

Observación:
  - Embedding de dominio de la tarea (10 dims, one-hot por dominio)
  - Longitud de la tarea (normalizada)
  - Step count (cuántas herramientas ya se usaron)

Recompensa:
  - 1.0 si la herramienta elegida coincide con la que obtuvo mejor reward en log
  - 0.5 si coincide con cualquier herramienta que funcionó
  - 0.0 si no coincide o falló
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

# ── Config ──────────────────────────────────────────────────────────────────
RL_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = RL_DIR.parent / "logs"
TRANSITIONS_FILE = LOGS_DIR / "tool_orchestrator_transitions.jsonl"

DOMAINS = (
    "security", "quality", "testing", "structure", "workflow",
    "database", "communication", "performance", "debug", "documentation",
)
NUM_DOMAINS = len(DOMAINS)
NUM_ACTIONS = 5
TOOL_NAMES = [
    "bago_search", "bago_list", "bago_read", "bago_call_search", "bago_grep_smart"
]
TOOL_INDEX = {name: i for i, name in enumerate(TOOL_NAMES)}


def _keyword_to_domain(task: str) -> int:
    """Heurística simple: asigna dominio según keywords en la tarea."""
    task_lower = task.lower()
    keywords = {
        "security": ["secret", "token", "credencial", "auth", "password"],
        "quality": ["lint", "quality", "deuda", "debt", "smell"],
        "testing": ["test", "prueba", "coverage", "jest", "pytest"],
        "structure": ["archivo", "file", "estructura", "tree", "folder", "list"],
        "workflow": ["workflow", "flujo", "pipeline", "orquest"],
        "database": ["db", "sql", "base de datos", "query", "schema"],
        "communication": ["api", "http", "request", "endpoint"],
        "performance": ["perf", "rapido", "slow", "memory", "cpu"],
        "debug": ["bug", "error", "crash", "debug", "fallo"],
        "documentation": ["doc", "readme", "comment", "document"],
    }
    scores = [0] * NUM_DOMAINS
    for i, domain in enumerate(DOMAINS):
        for kw in keywords.get(domain, []):
            if kw in task_lower:
                scores[i] += 1
    return int(np.argmax(scores)) if max(scores) > 0 else 0


def _load_transitions(path: Path) -> list[dict]:
    """Carga transiciones JSONL."""
    if not path.exists():
        return []
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data


# ── Environment ─────────────────────────────────────────────────────────────

class BagoToolEnv(gym.Env):
    """Entorno para aprender selección de herramientas BAGO desde logs reales."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        transitions_file: Path = TRANSITIONS_FILE,
        render_mode: str | None = None,
    ) -> None:
        super().__init__()
        self.render_mode = render_mode
        self.transitions = _load_transitions(transitions_file)
        self._grouped = self._group_by_task()

        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(NUM_DOMAINS + 2,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(NUM_ACTIONS)

        self._current_task: str = ""
        self._current_group: list[dict] = []
        self._step_count: int = 0

    def _group_by_task(self) -> dict[str, list[dict]]:
        """Agrupa transiciones por tarea de usuario."""
        grouped: dict[str, list[dict]] = {}
        for tr in self.transitions:
            task = tr.get("user_task", "")
            grouped.setdefault(task, []).append(tr)
        return grouped

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        if not self._grouped:
            # Sin datos: crear una transición sintética mínima
            self._current_task = "busca archivos de configuración"
            self._current_group = []
            obs = self._encode_obs(self._current_task, 0)
            return obs, {"task": self._current_task, "synthetic": True}

        self._current_task = self.np_random.choice(list(self._grouped.keys()))
        self._current_group = self._grouped[self._current_task]
        self._step_count = 0
        obs = self._encode_obs(self._current_task, self._step_count)
        return obs, {"task": self._current_task, "transitions": len(self._current_group)}

    def _encode_obs(self, task: str, step_count: int) -> np.ndarray:
        domain_idx = _keyword_to_domain(task)
        domain_vec = np.zeros(NUM_DOMAINS, dtype=np.float32)
        domain_vec[domain_idx] = 1.0
        task_len = min(len(task) / 200.0, 1.0)
        step_norm = min(step_count / 5.0, 1.0)
        return np.concatenate([domain_vec, [task_len, step_norm]]).astype(np.float32)

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        reward = 0.0
        best_tool = None
        best_reward = -1.0

        if self._current_group:
            for tr in self._current_group:
                tr_tool = tr.get("action", {}).get("tool", "")
                tr_reward = tr.get("reward", 0.0)
                if tr_reward > best_reward:
                    best_reward = tr_reward
                    best_tool = tr_tool

        chosen_tool = TOOL_NAMES[action] if 0 <= action < NUM_ACTIONS else ""

        if chosen_tool == best_tool and best_reward > 0.3:
            reward = 1.0
        elif any(tr.get("action", {}).get("tool") == chosen_tool and tr.get("reward", 0) > 0.2 for tr in self._current_group):
            reward = 0.5
        elif best_tool is None:
            reward = 0.1  # datos insuficientes, neutral

        self._step_count += 1
        obs = self._encode_obs(self._current_task, self._step_count)
        terminated = self._step_count >= 3
        truncated = False
        info = {
            "chosen_tool": chosen_tool,
            "best_tool": best_tool,
            "best_reward": best_reward,
            "task": self._current_task,
        }
        return obs, reward, terminated, truncated, info

    def render(self) -> None:
        if self.render_mode == "human":
            print(f"Task: {self._current_task[:60]}... | step={self._step_count}")


# ── CLI sanity check ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    env = BagoToolEnv()
    obs, info = env.reset()
    print("BagoToolEnv creado.")
    print(f"  Observación shape: {obs.shape}")
    print(f"  Tarea: {info.get('task', 'N/A')}")
    print(f"  Transiciones disponibles: {info.get('transitions', 0)}")
    print(f"  Acciones: {NUM_ACTIONS} ({TOOL_NAMES})")
    if info.get("transitions", 0) > 0:
        for _ in range(3):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            print(f"  Acción={TOOL_NAMES[action]} reward={reward:.2f} (best={info['best_tool']})")
            if terminated:
                break
    print("OK")

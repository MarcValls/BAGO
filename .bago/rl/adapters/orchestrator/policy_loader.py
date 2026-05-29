# -*- coding: utf-8 -*-
"""policy_loader.py — Carga política entrenada y predice herramienta desde tarea de usuario."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# Importamos policies desde training (relativo a .bago/rl)
import sys
_RL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RL_DIR))

from training.policies import BCPolicy, LinUCBPolicy
from envs.bago_tool_env import NUM_ACTIONS, NUM_DOMAINS, TOOL_NAMES


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
    DOMAINS = (
        "security", "quality", "testing", "structure", "workflow",
        "database", "communication", "performance", "debug", "documentation",
    )
    scores = [0] * NUM_DOMAINS
    for i, domain in enumerate(DOMAINS):
        for kw in keywords.get(domain, []):
            if kw in task_lower:
                scores[i] += 1
    return int(np.argmax(scores)) if max(scores) > 0 else 0


def encode_observation(task: str, step_count: int = 0) -> np.ndarray:
    """Convierte tarea de usuario en vector de observación 12-dim."""
    domain_idx = _keyword_to_domain(task)
    domain_vec = np.zeros(NUM_DOMAINS, dtype=np.float32)
    domain_vec[domain_idx] = 1.0
    task_len = min(len(task) / 200.0, 1.0)
    step_norm = min(step_count / 5.0, 1.0)
    return np.concatenate([domain_vec, [task_len, step_norm]]).astype(np.float32)


def load_policy(checkpoint_path: Path):
    """Detecta tipo de política (LinUCB o BC) y la carga."""
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        raw = f.read()
    if '"A":' in raw:
        return LinUCBPolicy.load(checkpoint_path)
    else:
        return BCPolicy.load(checkpoint_path)


def predict_tool(policy, task: str, step_count: int = 0) -> tuple[str, float | None]:
    """Predice la herramienta óptima para una tarea dada.

    Retorna (tool_name, confidence_score).
    """
    obs = encode_observation(task, step_count)
    if isinstance(policy, LinUCBPolicy):
        action = policy.select(obs)
        # Calcular score como max p-value
        scores = []
        for a in range(policy.n_actions):
            theta = policy.thetas[a]
            inv_A = np.linalg.inv(policy.A[a])
            p = theta @ obs + policy.alpha * np.sqrt(obs @ inv_A @ obs)
            scores.append(p)
        confidence = float(np.max(scores))
    else:  # BCPolicy
        logits = policy.W @ obs + policy.bias
        probs = np.exp(logits - np.max(logits))
        probs = probs / probs.sum()
        action = int(np.argmax(probs))
        confidence = float(probs[action])
    return TOOL_NAMES[action], confidence

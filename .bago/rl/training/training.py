# -*- coding: utf-8 -*-
"""training.py — Rutinas de entrenamiento y evaluación para políticas de herramientas BAGO."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

_RL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RL_DIR))

from envs.bago_tool_env import BagoToolEnv, NUM_ACTIONS, NUM_DOMAINS, TOOL_NAMES
from policies import BCPolicy, LinUCBPolicy

CHECKPOINTS_DIR = _RL_DIR / "checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


def train_bandit(episodes: int, alpha: float, save_path: Path) -> dict[str, float]:
    env = BagoToolEnv()
    n_features = env.observation_space.shape[0]
    policy = LinUCBPolicy(NUM_ACTIONS, n_features, alpha)

    rewards = []
    best_tool_hits = 0
    for ep in range(episodes):
        obs, info = env.reset()
        terminated = False
        ep_reward = 0.0
        while not terminated:
            action = policy.select(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            policy.update(action, obs, reward)
            ep_reward += reward
            if info.get("best_tool") == TOOL_NAMES[action] and reward > 0.5:
                best_tool_hits += 1
        rewards.append(ep_reward)

    policy.save(save_path)
    avg_reward = np.mean(rewards[-100:]) if len(rewards) >= 100 else np.mean(rewards)
    return {
        "episodes": episodes,
        "avg_reward_last_100": float(avg_reward),
        "best_tool_accuracy": best_tool_hits / episodes if episodes else 0,
        "checkpoint": str(save_path),
    }


def train_bc(epochs: int, lr: float, save_path: Path, transitions_file: Path | None = None) -> dict[str, float]:
    env = BagoToolEnv(transitions_file=transitions_file) if transitions_file else BagoToolEnv()
    n_features = env.observation_space.shape[0]
    policy = BCPolicy(NUM_ACTIONS, n_features, lr)

    transitions = []
    for tr in env.transitions:
        action_name = tr.get("action", {}).get("tool", "")
        if action_name not in TOOL_NAMES:
            continue
        action = TOOL_NAMES.index(action_name)
        reward = tr.get("reward", 0.0)
        task = tr.get("user_task", "")
        step = tr.get("step", 0)
        domain_idx = env.unwrapped._keyword_to_domain(task) if hasattr(env.unwrapped, "_keyword_to_domain") else 0
        domain_vec = np.zeros(NUM_DOMAINS, dtype=np.float32)
        domain_vec[domain_idx] = 1.0
        obs = np.concatenate([
            domain_vec,
            [min(len(task) / 200.0, 1.0), min(step / 5.0, 1.0)]
        ]).astype(np.float32)
        transitions.append((obs, action, reward))

    if not transitions:
        print("[WARN] No hay transiciones para entrenar BC. Ejecuta el orquestador primero o genera demos sintéticas.")
        return {"error": "no_transitions"}

    losses = []
    for epoch in range(epochs):
        random.shuffle(transitions)
        epoch_loss = 0.0
        for obs, action, reward in transitions:
            loss = policy.train_step(obs, action, reward)
            epoch_loss += loss
        avg_loss = epoch_loss / len(transitions)
        losses.append(avg_loss)
        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch + 1}/{epochs} — loss={avg_loss:.4f}")

    policy.save(save_path)
    return {
        "epochs": epochs,
        "transitions_used": len(transitions),
        "final_loss": float(losses[-1]) if losses else None,
        "checkpoint": str(save_path),
    }


def evaluate_policy(checkpoint_path: Path, episodes: int = 100, transitions_file: Path | None = None) -> dict[str, float]:
    env = BagoToolEnv(transitions_file=transitions_file) if transitions_file else BagoToolEnv()
    n_features = env.observation_space.shape[0]

    with open(checkpoint_path, "r", encoding="utf-8") as f:
        raw = f.read()
    if '"A":' in raw:
        policy = LinUCBPolicy.load(checkpoint_path)
    else:
        policy = BCPolicy.load(checkpoint_path)

    rewards = []
    best_hits = 0
    for _ in range(episodes):
        obs, info = env.reset()
        terminated = False
        ep_reward = 0.0
        while not terminated:
            if isinstance(policy, LinUCBPolicy):
                action = policy.select(obs)
            else:
                action = policy.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            ep_reward += reward
            if info.get("best_tool") == TOOL_NAMES[action] and reward > 0.5:
                best_hits += 1
        rewards.append(ep_reward)

    return {
        "episodes": episodes,
        "avg_reward": float(np.mean(rewards)),
        "best_tool_accuracy": best_hits / episodes,
    }

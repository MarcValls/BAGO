#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_tool_orchestrator.py — Entrena política RL para seleccionar herramientas BAGO.

Lee transiciones de bago_tool_orchestrator.py y entrena un agente LinUCB
(Fase 1) o Behavioral Cloning (Fase 2) para predecir la mejor herramienta
dado el contexto de la tarea.

Uso:
    python train_tool_orchestrator.py --mode bandit --episodes 5000
    python train_tool_orchestrator.py --mode bc --epochs 30
    python train_tool_orchestrator.py --eval --checkpoint .bago/rl/checkpoints/tool_policy.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Insertamos .bago/rl en path para importar envs
_RL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RL_DIR))

from envs.bago_tool_env import BagoToolEnv, NUM_ACTIONS, NUM_DOMAINS, TOOL_NAMES

# ── Paths ──────────────────────────────────────────────────────────────────
CHECKPOINTS_DIR = _RL_DIR / "checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


# ── LinUCB Policy ───────────────────────────────────────────────────────────

class LinUCBPolicy:
    """Política LinUCB para selección de herramientas BAGO."""

    def __init__(self, n_actions: int, n_features: int, alpha: float = 1.0):
        self.n_actions = n_actions
        self.n_features = n_features
        self.alpha = alpha
        self.A = [np.eye(n_features) for _ in range(n_actions)]
        self.b = [np.zeros(n_features) for _ in range(n_actions)]
        self.thetas = [np.zeros(n_features) for _ in range(n_actions)]
        self._update_all()

    def _update_all(self) -> None:
        for a in range(self.n_actions):
            try:
                self.thetas[a] = np.linalg.solve(self.A[a], self.b[a])
            except np.linalg.LinAlgError:
                self.thetas[a] = np.zeros(self.n_features)

    def select(self, x: np.ndarray) -> int:
        scores = []
        for a in range(self.n_actions):
            theta = self.thetas[a]
            inv_A = np.linalg.inv(self.A[a])
            p = theta @ x + self.alpha * np.sqrt(x @ inv_A @ x)
            scores.append(p)
        return int(np.argmax(scores))

    def update(self, action: int, x: np.ndarray, reward: float) -> None:
        self.A[action] += np.outer(x, x)
        self.b[action] += reward * x
        self._update_all()

    def save(self, path: Path) -> None:
        data = {
            "n_actions": self.n_actions,
            "n_features": self.n_features,
            "alpha": float(self.alpha),
            "A": [a.tolist() for a in self.A],
            "b": [b.tolist() for b in self.b],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "LinUCBPolicy":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pol = cls(data["n_actions"], data["n_features"], data["alpha"])
        pol.A = [np.array(a) for a in data["A"]]
        pol.b = [np.array(b) for b in data["b"]]
        pol._update_all()
        return pol


# ── BC (Behavioral Cloning) Policy ──────────────────────────────────────────

class BCPolicy:
    """Política simple de clasificación lineal para BC."""

    def __init__(self, n_actions: int, n_features: int, lr: float = 0.01):
        self.n_actions = n_actions
        self.n_features = n_features
        self.lr = lr
        self.W = np.zeros((n_actions, n_features))
        self.bias = np.zeros(n_actions)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()

    def predict(self, x: np.ndarray) -> int:
        logits = self.W @ x + self.bias
        probs = self._softmax(logits)
        return int(np.argmax(probs))

    def train_step(self, x: np.ndarray, action: int, reward: float) -> float:
        logits = self.W @ x + self.bias
        probs = self._softmax(logits)
        target = np.zeros(self.n_actions)
        target[action] = 1.0
        # Weighted by reward: good transitions have higher gradient
        grad = (probs - target) * reward
        self.W -= self.lr * np.outer(grad, x)
        self.bias -= self.lr * grad
        loss = -np.log(max(probs[action], 1e-8)) * reward
        return float(loss)

    def save(self, path: Path) -> None:
        data = {
            "n_actions": self.n_actions,
            "n_features": self.n_features,
            "W": self.W.tolist(),
            "bias": self.bias.tolist(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "BCPolicy":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pol = cls(data["n_actions"], data["n_features"])
        pol.W = np.array(data["W"])
        pol.bias = np.array(data["bias"])
        return pol


# ── Training ─────────────────────────────────────────────────────────────────

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


def train_bc(epochs: int, lr: float, save_path: Path) -> dict[str, float]:
    env = BagoToolEnv()
    n_features = env.observation_space.shape[0]
    policy = BCPolicy(NUM_ACTIONS, n_features, lr)

    # Extraer transiciones del log para entrenamiento supervisado
    transitions = []
    for tr in env.transitions:
        action_name = tr.get("action", {}).get("tool", "")
        if action_name not in TOOL_NAMES:
            continue
        action = TOOL_NAMES.index(action_name)
        reward = tr.get("reward", 0.0)
        # Reconstruir obs desde task + step
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
        print("[WARN] No hay transiciones para entrenar BC. Ejecuta el orquestador primero.")
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


def evaluate_policy(checkpoint_path: Path, episodes: int = 100) -> dict[str, float]:
    env = BagoToolEnv()
    n_features = env.observation_space.shape[0]

    if checkpoint_path.suffix == ".json":
        # Detectar tipo por contenido
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            raw = f.read()
        if '"A":' in raw:
            policy = LinUCBPolicy.load(checkpoint_path)
        else:
            policy = BCPolicy.load(checkpoint_path)
    else:
        raise ValueError("Checkpoint debe ser .json")

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


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena política RL para herramientas BAGO")
    parser.add_argument("--mode", choices=["bandit", "bc"], default="bandit",
                        help="Algoritmo: bandit (LinUCB) o bc (Behavioral Cloning)")
    parser.add_argument("--episodes", type=int, default=2000, help="Episodios (bandit)")
    parser.add_argument("--epochs", type=int, default=30, help="Épocas (bc)")
    parser.add_argument("--alpha", type=float, default=1.0, help="Exploración LinUCB")
    parser.add_argument("--lr", type=float, default=0.01, help="Learning rate BC")
    parser.add_argument("--eval", action="store_true", help="Modo evaluación")
    parser.add_argument("--checkpoint", type=Path, help="Checkpoint para evaluar")
    parser.add_argument("--save", type=Path, help="Ruta de guardado")
    args = parser.parse_args()

    if args.eval:
        if not args.checkpoint:
            print("[ERROR] --eval requiere --checkpoint")
            sys.exit(1)
        print(f"Evaluando {args.checkpoint}...")
        metrics = evaluate_policy(args.checkpoint)
        print(json.dumps(metrics, indent=2))
        return

    if args.mode == "bandit":
        save = args.save or CHECKPOINTS_DIR / "tool_policy_bandit.json"
        print(f"Entrenando LinUCB ({args.episodes} episodios, alpha={args.alpha})...")
        metrics = train_bandit(args.episodes, args.alpha, save)
    else:
        save = args.save or CHECKPOINTS_DIR / "tool_policy_bc.json"
        print(f"Entrenando BC ({args.epochs} epochs, lr={args.lr})...")
        metrics = train_bc(args.epochs, args.lr, save)

    print("\n=== Métricas ===")
    print(json.dumps(metrics, indent=2))
    print(f"\nCheckpoint guardado en: {save}")


if __name__ == "__main__":
    main()

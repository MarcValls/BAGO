#!/usr/bin/env python3
"""train_bandit.py — Entrenamiento de Contextual Bandit para routing de herramientas BAGO.

Fase 1 del plan de integración de RL.
Implementa LinUCB (Upper Confidence Bound) lineal para selección de herramientas.

Uso:
    python train_bandit.py --episodes 5000 --save policy_bandit.json
    python train_bandit.py --eval policy_bandit.json --episodes 100
    python train_bandit.py --test

Códigos: RL-T001 (entrenamiento OK), RL-T002 (evaluación OK), RL-T003 (policy guardada)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Insertamos .bago/rl en el path para importar envs
_RL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RL_DIR))

from envs.bago_bandit_env import BagoBanditEnv


class LinUCBPolicy:
    """Política LinUCB para bandits contextuales.

    Cada acción tiene su propio modelo lineal con eliminación regularizada.
    A_t = A + x_t x_t^T
    b_t = b + r_t x_t
    theta_t = A_t^{-1} b_t
    """

    def __init__(self, n_actions: int, n_features: int, alpha: float = 1.0):
        self.n_actions = n_actions
        self.n_features = n_features
        self.alpha = alpha
        # Un modelo por acción
        self.A: list[np.ndarray] = [
            np.eye(n_features) for _ in range(n_actions)
        ]
        self.b: list[np.ndarray] = [
            np.zeros(n_features) for _ in range(n_actions)
        ]
        self.thetas: list[np.ndarray] = [
            np.zeros(n_features) for _ in range(n_actions)
        ]
        self._update_all_thetas()

    def _update_all_thetas(self) -> None:
        for a in range(self.n_actions):
            self.thetas[a] = np.linalg.solve(self.A[a], self.b[a])

    def select_action(self, context: np.ndarray) -> int:
        """Selecciona acción maximizando UCB = x^T theta + alpha * sqrt(x^T A^{-1} x)."""
        ucbs = np.zeros(self.n_actions)
        for a in range(self.n_actions):
            theta = self.thetas[a]
            # x^T theta
            mean = float(np.dot(context, theta))
            # alpha * sqrt(x^T A^{-1} x)
            # Resolvemos A y = x => y = A^{-1} x; luego x^T y
            try:
                y = np.linalg.solve(self.A[a], context)
                std = np.sqrt(np.dot(context, y))
            except np.linalg.LinAlgError:
                std = 1e6  # A is singular → explore aggressively
            ucbs[a] = mean + self.alpha * std
        return int(np.argmax(ucbs))

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        """Actualiza el modelo de la acción elegida con la transición observada."""
        ctx = np.asarray(context, dtype=np.float64)
        self.A[action] += np.outer(ctx, ctx)
        self.b[action] += reward * ctx
        # Recompute theta for this action only
        try:
            self.thetas[action] = np.linalg.solve(self.A[action], self.b[action])
        except np.linalg.LinAlgError:
            pass  # skip update if singular

    def predict_means(self, context: np.ndarray) -> np.ndarray:
        """Devuelve las medias predichas para todas las acciones."""
        means = np.zeros(self.n_actions)
        for a in range(self.n_actions):
            means[a] = float(np.dot(context, self.thetas[a]))
        return means

    def save(self, path: Path) -> None:
        data = {
            "alpha": self.alpha,
            "n_actions": self.n_actions,
            "n_features": self.n_features,
            "A": [a.tolist() for a in self.A],
            "b": [b.tolist() for b in self.b],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LinUCBPolicy":
        data = json.loads(path.read_text(encoding="utf-8"))
        policy = cls(
            n_actions=data["n_actions"],
            n_features=data["n_features"],
            alpha=data["alpha"],
        )
        policy.A = [np.array(a, dtype=np.float64) for a in data["A"]]
        policy.b = [np.array(b, dtype=np.float64) for b in data["b"]]
        policy._update_all_thetas()
        return policy


def train(
    episodes: int = 5000,
    alpha: float = 1.0,
    seed: int = 42,
    contexts: list[str] | None = None,
) -> tuple[LinUCBPolicy, dict[str, Any]]:
    """Entrena una política LinUCB en el entorno BagoBanditEnv."""
    random.seed(seed)
    np.random.seed(seed)

    env = BagoBanditEnv()
    n_actions = len(env.actions)
    n_features = len(env.observation_space["domain_signal"].shape)
    if n_features == 1:
        n_features = env.observation_space["domain_signal"].shape[0]

    policy = LinUCBPolicy(n_actions=n_actions, n_features=n_features, alpha=alpha)

    default_contexts = [
        "revisar seguridad del código",
        "lint y formato",
        "preparar para producción",
        "auditoría completa",
        "chequear dependencias",
        "debug error",
        "documentar funciones",
        "mejorar rendimiento",
    ]
    contexts = contexts or default_contexts

    total_reward = 0.0
    successes = 0
    action_counts = [0] * n_actions

    for ep in range(episodes):
        context_text = random.choice(contexts)
        obs, info = env.reset(options={"context": context_text})
        ctx = obs["domain_signal"]
        action = policy.select_action(ctx)
        action_counts[action] += 1
        obs_next, reward, terminated, truncated, info = env.step(action)
        policy.update(action, ctx, reward)
        total_reward += reward
        if info.get("success", False):
            successes += 1

    metrics = {
        "episodes": episodes,
        "total_reward": round(total_reward, 2),
        "avg_reward": round(total_reward / episodes, 4),
        "success_rate": round(successes / episodes, 4),
        "action_distribution": {
            env.actions[i]: action_counts[i] for i in range(n_actions)
        },
    }
    return policy, metrics


def evaluate(policy_path: Path, episodes: int = 1000, seed: int = 123) -> dict[str, Any]:
    """Evalúa una política guardada sin actualizar (off-policy)."""
    policy = LinUCBPolicy.load(policy_path)
    env = BagoBanditEnv()
    random.seed(seed)
    np.random.seed(seed)

    total_reward = 0.0
    successes = 0
    default_contexts = [
        "revisar seguridad del código",
        "lint y formato",
        "preparar para producción",
        "auditoría completa",
        "chequear dependencias",
        "debug error",
        "documentar funciones",
        "mejorar rendimiento",
    ]

    for _ in range(episodes):
        context_text = random.choice(default_contexts)
        obs, _ = env.reset(options={"context": context_text})
        ctx = obs["domain_signal"]
        action = policy.select_action(ctx)
        obs_next, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if info.get("success", False):
            successes += 1

    return {
        "episodes": episodes,
        "total_reward": round(total_reward, 2),
        "avg_reward": round(total_reward / episodes, 4),
        "success_rate": round(successes / episodes, 4),
    }


def _self_test() -> int:
    print("[train_bandit] Self-test starting...")

    # Test 1: LinUCB creación
    policy = LinUCBPolicy(n_actions=3, n_features=5, alpha=1.0)
    ctx = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
    a = policy.select_action(ctx)
    assert 0 <= a < 3, "action out of bounds"
    policy.update(a, ctx, 1.0)
    print("  ✓ LinUCB create/select/update")

    # Test 2: entrenamiento corto
    policy2, metrics = train(episodes=100, alpha=1.0, seed=42)
    assert metrics["episodes"] == 100
    assert "avg_reward" in metrics
    print(f"  ✓ Train OK (avg_reward={metrics['avg_reward']})")

    # Test 3: guardar y cargar
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "policy.json"
        policy2.save(path)
        policy3 = LinUCBPolicy.load(path)
        assert policy3.n_actions == policy2.n_actions
        print("  ✓ Save/Load OK")

    # Test 4: evaluación
        metrics_eval = evaluate(path, episodes=50, seed=99)
        assert "avg_reward" in metrics_eval
        print(f"  ✓ Eval OK (avg_reward={metrics_eval['avg_reward']})")

    print("[train_bandit] Self-test PASSED (4/4)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BAGO Bandit Training (LinUCB)")
    parser.add_argument("--episodes", type=int, default=5000, help="Número de episodios")
    parser.add_argument("--alpha", type=float, default=1.0, help="Parámetro de exploración UCB")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--save", type=Path, default=None, help="Ruta para guardar política")
    parser.add_argument("--eval", type=Path, default=None, help="Ruta de política a evaluar")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args()

    if args.test:
        return _self_test()

    if args.eval:
        if not args.eval.exists():
            print(f"[train_bandit] Policy not found: {args.eval}", file=sys.stderr)
            return 1
        metrics = evaluate(args.eval, episodes=args.episodes, seed=args.seed)
        print(json.dumps(metrics, indent=2))
        return 0

    policy, metrics = train(episodes=args.episodes, alpha=args.alpha, seed=args.seed)
    print(json.dumps(metrics, indent=2))

    if args.save:
        policy.save(args.save)
        print(f"[train_bandit] Policy saved to {args.save}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

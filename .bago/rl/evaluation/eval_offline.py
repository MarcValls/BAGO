"""Evaluación off-policy para política BC entrenada en Fase 2.

Compara la política BC contra el baseline heurístico en un entorno simulado.

Ejemplo:
    python .bago/rl/evaluation/eval_offline.py \
        --model .bago/rl/checkpoints/bc_synthetic.pt \
        --baseline heuristic \
        --episodes 500
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    import torch
    _TORCH = True
except Exception:
    _TORCH = False
    torch = None  # type: ignore[misc]

# ---------------------------------------------------------------------------
# Entorno simulado ligero (sin dependencia gymnasium para eval rápida)
# ---------------------------------------------------------------------------
ACTIONS = [
    "next_tool", "retry", "skip", "request_validation",
    "handoff_human", "abort", "change_strategy",
]


def encode_obs_dict(obs: dict[str, Any]) -> list[float]:
    flat: list[float] = []
    flat.append(float(obs["stage_id"]))
    flat.append(float(obs["retry_count"]))
    flat.extend(obs["queue_pressure"].tolist())
    flat.extend(obs["budget_left"].tolist())
    flat.extend(obs["last_validator_score"].tolist())
    flat.append(float(obs["last_error_code"]))
    flat.extend(obs["tools_available"].tolist())
    return flat


class TinyWorkflowEnv:
    """Simulador mínimo del workflow para eval off-policy."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)
        self.reset()

    def reset(self) -> dict[str, Any]:
        self.stage_id = 0
        self.retry_count = 0
        self.queue_pressure = self.rng.random()
        self.budget = 1.0
        self.validator_score = 1.0
        self.last_error_code = 0
        self.tools_available = self.rng.integers(0, 2, size=32).astype(np.int8)
        return self._obs()

    def _obs(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "retry_count": self.retry_count,
            "queue_pressure": np.array([self.queue_pressure], dtype=np.float32),
            "budget_left": np.array([self.budget], dtype=np.float32),
            "last_validator_score": np.array([self.validator_score], dtype=np.float32),
            "last_error_code": self.last_error_code,
            "tools_available": self.tools_available.copy(),
        }

    def step(self, action: int) -> tuple[dict[str, Any], float, bool]:
        action_name = ACTIONS[action]
        success = self.rng.random() > 0.3
        latency = self.rng.exponential(2.0)
        cost = 0.05 + self.rng.random() * 0.1

        reward = 1.0 if success else -0.5
        reward -= latency * 0.05 + cost * 0.5

        if action_name == "next_tool" and success:
            self.stage_id += 1
            self.retry_count = 0
            self.last_error_code = 0
        elif action_name == "retry":
            self.retry_count += 1
            if not success:
                self.last_error_code = int(self.rng.integers(1, 32))
        elif action_name == "request_validation":
            self.validator_score = min(1.0, self.validator_score + 0.2)
        elif action_name == "handoff_human":
            self.queue_pressure = max(0.0, self.queue_pressure - 0.3)
            reward += 0.5
        elif action_name == "abort":
            reward -= 1.0

        self.budget = max(0.0, self.budget - cost)
        self.queue_pressure = min(1.0, self.queue_pressure + self.rng.random() * 0.1)
        self.validator_score = max(0.0, self.validator_score - 0.05)

        done = (
            action_name == "abort"
            or self.stage_id >= 10
            or self.budget <= 0.0
        )
        return self._obs(), float(reward), done


def heuristic_policy(obs: dict[str, Any], rng: np.random.Generator) -> int:
    """Baseline heurístico simple (reglas fijas)."""
    budget = float(obs["budget_left"][0])
    score = float(obs["last_validator_score"][0])
    retry = int(obs["retry_count"])
    error = int(obs["last_error_code"])
    stage = int(obs["stage_id"])

    if budget < 0.1:
        return ACTIONS.index("abort")
    if score < 0.3:
        return ACTIONS.index("request_validation")
    if retry >= 2 and error != 0:
        return ACTIONS.index("handoff_human")
    if error != 0 and retry < 2:
        return ACTIONS.index("retry")
    if stage >= 8:
        return ACTIONS.index("handoff_human")
    return ACTIONS.index("next_tool")


def evaluate_policy(
    policy_fn,
    episodes: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    returns: list[float] = []
    successes = 0
    lengths: list[int] = []

    for ep in range(episodes):
        env = TinyWorkflowEnv(seed=seed + ep)
        obs = env.reset()
        done = False
        total_reward = 0.0
        steps = 0
        while not done and steps < 50:
            action = policy_fn(obs, rng)
            obs, reward, done = env.step(action)
            total_reward += reward
            steps += 1
        returns.append(total_reward)
        if env.stage_id >= 10:
            successes += 1
        lengths.append(steps)

    return {
        "mean_return": round(float(np.mean(returns)), 4),
        "std_return": round(float(np.std(returns)), 4),
        "success_rate": round(successes / episodes, 4),
        "mean_length": round(float(np.mean(lengths)), 2),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evalúa política BC vs baseline heurístico.")
    p.add_argument("--model", type=Path, required=True, help="Ruta al modelo .pt")
    p.add_argument("--episodes", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    if not _TORCH:
        print("❌ PyTorch no disponible", file=sys.stderr)
        return 1

    # Load model
    import sys as _sys
    _sys.path.insert(0, str(Path(".bago/rl/training").resolve()))
    from train_offline import load_model

    model = load_model(args.model, input_dim=38, n_actions=7)
    model.eval()

    def bc_policy(obs: dict[str, Any], rng: np.random.Generator) -> int:
        x = torch.tensor([encode_obs_dict(obs)], dtype=torch.float32)
        with torch.no_grad():
            logits = model(x)
        return int(logits.argmax(dim=1).item())

    print("🔬 Evaluando BC policy...")
    bc_stats = evaluate_policy(bc_policy, episodes=args.episodes, seed=args.seed)
    print(f"   BC: {bc_stats}")

    print("🔬 Evaluando baseline heurístico...")
    heuristic_stats = evaluate_policy(heuristic_policy, episodes=args.episodes, seed=args.seed)
    print(f"   Heuristic: {heuristic_stats}")

    improvement = (
        (bc_stats["mean_return"] - heuristic_stats["mean_return"])
        / abs(heuristic_stats["mean_return"])
        * 100
    )
    print(f"📈 Mejora BC vs Heuristic: {improvement:.2f}%")

    result = {
        "bc": bc_stats,
        "heuristic": heuristic_stats,
        "improvement_pct": round(improvement, 2),
    }
    out_path = args.model.with_suffix(".eval.json")
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"💾 Resultado guardado en {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

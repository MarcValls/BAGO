"""Evaluación final de políticas MaskablePPO entrenadas en Fase 3.

Evalúa cada checkpoint en su curriculum correspondiente y reporta:
- Tasa de éxito (completar el workflow)
- Recompensa acumulada
- Longitud de episodio
- Acciones inválidas (si las hay)

Ejemplo:
    python .bago/rl/evaluation/eval_online.py \
        --model .bago/rl/checkpoints/ppo_short/final_model.zip \
        --curriculum short --episodes 500
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    from sb3_contrib.ppo_mask import MaskablePPO
    from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
    _SB3_AVAILABLE = True
except Exception:
    _SB3_AVAILABLE = False
    MaskablePPO = None  # type: ignore[misc]
    MaskableActorCriticPolicy = None  # type: ignore[misc]

# Env imports
try:
    from ..envs.bago_workflow_env import BagoWorkflowEnv
except ImportError:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "envs"))
    from bago_workflow_env import BagoWorkflowEnv

# Reutilizar wrappers del script de entrenamiento
import gymnasium as gym


class DictFlattenWrapper(gym.ObservationWrapper):
    """Aplana Dict observation space a Box para SB3."""

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        total_dim = 0
        for key, space in env.observation_space.spaces.items():
            if isinstance(space, gym.spaces.Discrete):
                total_dim += space.n
            elif isinstance(space, gym.spaces.Box):
                total_dim += np.prod(space.shape)
            elif isinstance(space, gym.spaces.MultiBinary):
                total_dim += space.n
            else:
                raise ValueError(f"Espacio no soportado: {type(space)}")
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(total_dim,), dtype=np.float32
        )
        self._keys = list(env.observation_space.spaces.keys())

    def observation(self, obs: dict[str, Any]) -> np.ndarray:
        flat: list[float] = []
        for key in self._keys:
            val = obs[key]
            if isinstance(val, (int, np.integer)):
                space = self.env.observation_space.spaces[key]
                if isinstance(space, gym.spaces.Discrete):
                    one_hot = np.zeros(space.n, dtype=np.float32)
                    idx = min(int(val), space.n - 1)
                    one_hot[idx] = 1.0
                    flat.extend(one_hot.tolist())
                else:
                    flat.append(float(val))
            elif isinstance(val, np.ndarray):
                flat.extend(val.flatten().tolist())
            else:
                flat.append(float(val))
        return np.array(flat, dtype=np.float32)


class BagoActionMaskWrapper(gym.Wrapper):
    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)

    def action_masks(self) -> np.ndarray:
        if hasattr(self.env, "available_actions_mask"):
            return self.env.available_actions_mask()
        if hasattr(self.env, "env") and hasattr(self.env.env, "available_actions_mask"):
            return self.env.env.available_actions_mask()
        raise AttributeError("Env subyacente no tiene available_actions_mask()")


def evaluate(
    model_path: Path,
    curriculum: str,
    episodes: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    if not _SB3_AVAILABLE:
        raise RuntimeError("sb3-contrib no está instalado.")

    env = BagoActionMaskWrapper(DictFlattenWrapper(BagoWorkflowEnv(curriculum=curriculum, seed=seed)))

    model = MaskablePPO.load(model_path, env=env)

    episode_rewards: list[float] = []
    episode_lengths: list[int] = []
    successes = 0
    invalid_actions = 0
    total_actions = 0

    for ep in range(episodes):
        obs, _ = env.reset(seed=seed + ep)
        done = False
        total_reward = 0.0
        steps = 0
        while not done and steps < 100:
            mask = env.action_masks()
            action, _ = model.predict(obs, action_masks=mask, deterministic=True)
            action = int(action)
            total_actions += 1
            if not mask[action]:
                invalid_actions += 1
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            done = terminated or truncated
            steps += 1
        episode_rewards.append(total_reward)
        episode_lengths.append(steps)
        # Success = completed all stages (stage_id >= max_stages)
        if hasattr(env.env, "env") and hasattr(env.env.env, "_stage_id"):
            final_stage = env.env.env._stage_id
            max_stages = env.env.env._max_stages
        elif hasattr(env.env, "_stage_id"):
            final_stage = env.env._stage_id
            max_stages = env.env._max_stages
        else:
            final_stage = 0
            max_stages = 1
        if final_stage >= max_stages:
            successes += 1

    return {
        "curriculum": curriculum,
        "model": str(model_path),
        "episodes": episodes,
        "mean_reward": round(float(np.mean(episode_rewards)), 4),
        "std_reward": round(float(np.std(episode_rewards)), 4),
        "mean_length": round(float(np.mean(episode_lengths)), 2),
        "success_rate": round(successes / episodes, 4),
        "invalid_actions": invalid_actions,
        "invalid_pct": round((invalid_actions / max(total_actions, 1)) * 100, 4),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evalúa política MaskablePPO entrenada.")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--curriculum", type=str, default="short", choices=["short", "medium", "full"])
    p.add_argument("--episodes", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args(argv)

    print(f"🔬 Evaluando {args.model} en curriculum={args.curriculum}...")
    stats = evaluate(args.model, args.curriculum, args.episodes, args.seed)
    print(json.dumps(stats, indent=2))

    out_path = args.output or args.model.with_suffix(".eval.json")
    out_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"💾 Resultado guardado en {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

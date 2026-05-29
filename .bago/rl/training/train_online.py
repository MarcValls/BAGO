"""Entrenamiento Online RL para BAGO (Fase 3).

Entrena MaskablePPO en BagoWorkflowEnv con curriculum learning.
Soporta action masking y guarda checkpoints con métricas.

Ejemplo:
    python .bago/rl/training/train_online.py \
        --curriculum short --total-timesteps 100_000 \
        --save-path .bago/rl/checkpoints/ppo_short
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Lazy import SB3 Contrib para evitar crash si no está instalado
try:
    from sb3_contrib.ppo_mask import MaskablePPO
    from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
    from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
    _SB3_AVAILABLE = True
except Exception:  # pragma: no cover
    _SB3_AVAILABLE = False
    MaskablePPO = None  # type: ignore[misc]
    MaskableActorCriticPolicy = None  # type: ignore[misc]
    MaskableEvalCallback = None  # type: ignore[misc]

# Env import
try:
    from ..envs.bago_workflow_env import BagoWorkflowEnv
except ImportError:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "envs"))
    from bago_workflow_env import BagoWorkflowEnv


import gymnasium as gym

class DictFlattenWrapper(gym.ObservationWrapper):
    """Aplana Dict observation space a Box para SB3."""

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        # Calcular dimensiones totales
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
        self._total_dim = total_dim

    def observation(self, obs: dict[str, Any]) -> np.ndarray:
        flat: list[float] = []
        for key in self._keys:
            val = obs[key]
            if isinstance(val, (int, np.integer)):
                # One-hot para Discrete
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
    """Wrapper que expone action_masks para MaskablePPO."""

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)

    def action_masks(self) -> np.ndarray:
        # El env subyacente debe ser BagoWorkflowEnv
        if hasattr(self.env, "available_actions_mask"):
            return self.env.available_actions_mask()
        if hasattr(self.env, "env") and hasattr(self.env.env, "available_actions_mask"):
            return self.env.env.available_actions_mask()
        raise AttributeError("Env subyacente no tiene available_actions_mask()")


def train(
    curriculum: str = "short",
    total_timesteps: int = 100_000,
    save_path: Path | None = None,
    seed: int = 42,
    verbose: int = 1,
    warm_start: Path | None = None,
) -> dict[str, Any]:
    """Entrena MaskablePPO en BagoWorkflowEnv."""

    if not _SB3_AVAILABLE:
        raise RuntimeError("sb3-contrib no está instalado. Ejecuta: pip install sb3-contrib")

    env = BagoActionMaskWrapper(DictFlattenWrapper(BagoWorkflowEnv(curriculum=curriculum, seed=seed)))
    eval_env = BagoActionMaskWrapper(DictFlattenWrapper(BagoWorkflowEnv(curriculum=curriculum, seed=seed + 1)))

    save_path = save_path or Path(f".bago/rl/checkpoints/ppo_{curriculum}")
    save_path.mkdir(parents=True, exist_ok=True)

    if warm_start and warm_start.exists():
        print(f"🔄 Warm-start desde {warm_start}")
        model = MaskablePPO.load(warm_start, env=env)
    else:
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            env,
            verbose=verbose,
            seed=seed,
            tensorboard_log=str(save_path / "tensorboard"),
        )

    eval_callback = MaskableEvalCallback(
        eval_env,
        best_model_save_path=str(save_path / "best_model"),
        log_path=str(save_path / "eval_logs"),
        eval_freq=10_000,
        deterministic=True,
        render=False,
    )

    model.learn(total_timesteps=total_timesteps, callback=eval_callback)

    final_path = save_path / "final_model.zip"
    model.save(final_path)

    # Evaluación final
    mean_reward, std_reward = evaluate_policy(model, eval_env, n_eval_episodes=100)

    stats = {
        "curriculum": curriculum,
        "total_timesteps": total_timesteps,
        "mean_reward": round(float(mean_reward), 4),
        "std_reward": round(float(std_reward), 4),
        "save_path": str(save_path),
        "seed": seed,
    }
    (save_path / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def evaluate_policy(model, env, n_eval_episodes: int = 100) -> tuple[float, float]:
    """Evalúa la política entrenada."""
    episode_rewards: list[float] = []
    for _ in range(n_eval_episodes):
        obs, _ = env.reset()
        done = False
        total_reward = 0.0
        while not done:
            action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
            obs, reward, terminated, truncated, _ = env.step(int(action))
            total_reward += reward
            done = terminated or truncated
        episode_rewards.append(total_reward)
    return float(np.mean(episode_rewards)), float(np.std(episode_rewards))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Entrena MaskablePPO en BagoWorkflowEnv.")
    p.add_argument("--curriculum", type=str, default="short", choices=["short", "medium", "full"])
    p.add_argument("--total-timesteps", type=int, default=100_000)
    p.add_argument("--save-path", type=Path, default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--verbose", type=int, default=1)
    p.add_argument("--warm-start", type=Path, default=None, help="Ruta a modelo previo para warm-start.")
    args = p.parse_args(argv)

    print(f"🚀 Entrenando MaskablePPO — curriculum={args.curriculum}, timesteps={args.total_timesteps}")
    stats = train(
        curriculum=args.curriculum,
        total_timesteps=args.total_timesteps,
        save_path=args.save_path,
        seed=args.seed,
        verbose=args.verbose,
        warm_start=args.warm_start,
    )
    print(f"✅ Entrenamiento finalizado — mean_reward={stats['mean_reward']}, std={stats['std_reward']}")
    print(f"💾 Guardado en {stats['save_path']}")
    return 0


def _self_test() -> int:
    print("[train_online] Self-test starting...")

    if not _SB3_AVAILABLE:
        print("   ⚠️  sb3-contrib no disponible — salteando test.")
        return 0

    stats = train(
        curriculum="short",
        total_timesteps=5_000,
        save_path=Path(".bago/rl/checkpoints/ppo_selftest"),
        seed=42,
        verbose=0,
    )
    assert stats["mean_reward"] is not None
    assert stats["save_path"]
    print(f"   ✓ Train OK — mean_reward={stats['mean_reward']}")
    print("[train_online] Self-test PASSED (1/1)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.exit(_self_test())
    sys.exit(main())

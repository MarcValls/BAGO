"""BagoWorkflowEnv — Sandbox MDP para orquestación de workflows (Fase 3).

Espacio de observación tipo Dict con estado del orquestador.
Espacio de acción discreto con 7 acciones semánticas.
Soporte para action masking y curriculum learning.

Ejemplo:
    env = BagoWorkflowEnv(curriculum="short")
    obs, info = env.reset()
    action = env.action_space.sample(mask=env.available_actions_mask())
    obs, reward, terminated, truncated, info = env.step(action)
"""

from __future__ import annotations

import random
import sys
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces


class BagoWorkflowEnv(gym.Env):
    """MDP para orquestación de workflows en BAGO.

    Curriculum stages:
        - "short":   3-step workflows (Semanas 10-12)
        - "medium":  6-step workflows (Semanas 13-14)
        - "full":    10+ step workflows (Semanas 15-16)
    """

    metadata = {"render_modes": ["human"]}

    ACTIONS = [
        "next_tool",
        "retry",
        "skip",
        "request_validation",
        "handoff_human",
        "abort",
        "change_strategy",
    ]

    def __init__(
        self,
        curriculum: str = "short",
        render_mode: str | None = None,
        seed: int | None = None,
    ) -> None:
        super().__init__()
        self.render_mode = render_mode
        self.curriculum = curriculum

        # Stage lengths per curriculum
        self._stage_lengths = {
            "short": 3,
            "medium": 6,
            "full": 10,
        }
        self._max_stages = self._stage_lengths.get(curriculum, 3)

        # Observation space
        self.observation_space = spaces.Dict(
            {
                "stage_id": spaces.Discrete(16),
                "retry_count": spaces.Discrete(8),
                "queue_pressure": spaces.Box(0.0, 1.0, (1,), dtype=np.float32),
                "budget_left": spaces.Box(0.0, 1.0, (1,), dtype=np.float32),
                "last_validator_score": spaces.Box(0.0, 1.0, (1,), dtype=np.float32),
                "last_error_code": spaces.Discrete(32),
                "tools_available": spaces.MultiBinary(32),
            }
        )

        # Action space
        self.action_space = spaces.Discrete(len(self.ACTIONS))

        # Internal state
        self._stage_id = 0
        self._retry_count = 0
        self._queue_pressure = 0.0
        self._budget = 1.0
        self._validator_score = 1.0
        self._last_error_code = 0
        self._tools_available: np.ndarray | None = None
        self._episode_steps = 0
        self._total_reward = 0.0

        self.np_random = np.random.default_rng(seed)

    def _get_obs(self) -> dict[str, Any]:
        return {
            "stage_id": self._stage_id,
            "retry_count": self._retry_count,
            "queue_pressure": np.array([self._queue_pressure], dtype=np.float32),
            "budget_left": np.array([self._budget], dtype=np.float32),
            "last_validator_score": np.array([self._validator_score], dtype=np.float32),
            "last_error_code": self._last_error_code,
            "tools_available": self._tools_available.copy(),
        }

    def _get_info(self) -> dict[str, Any]:
        return {
            "episode_steps": self._episode_steps,
            "total_reward": self._total_reward,
            "curriculum": self.curriculum,
        }

    def available_actions_mask(self) -> np.ndarray:
        """Máscara booleana de acciones válidas en el estado actual.

        Returns:
            np.ndarray: shape (n_actions,) dtype bool
        """
        mask = np.ones(len(self.ACTIONS), dtype=bool)
        # Cannot retry if no retries left
        if self._retry_count >= 3:
            mask[self.ACTIONS.index("retry")] = False
        # Cannot request validation if budget depleted
        if self._budget < 0.1:
            mask[self.ACTIONS.index("request_validation")] = False
        # Cannot change strategy if no tools available
        if self._tools_available is not None and not self._tools_available.any():
            mask[self.ACTIONS.index("change_strategy")] = False
        return mask

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if seed is not None:
            self.np_random = np.random.default_rng(seed)
        super().reset(seed=seed)

        options = options or {}
        self._stage_id = options.get("stage_id", 0)
        self._retry_count = 0
        self._queue_pressure = self.np_random.random()
        self._budget = 1.0
        self._validator_score = 1.0
        self._last_error_code = 0
        self._tools_available = self.np_random.integers(0, 2, size=32).astype(np.int8)
        self._episode_steps = 0
        self._total_reward = 0.0

        if options.get("curriculum"):
            self.curriculum = options["curriculum"]
            self._max_stages = self._stage_lengths.get(self.curriculum, 3)

        return self._get_obs(), self._get_info()

    def step(self, action: int) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        assert self.action_space.contains(action)

        self._episode_steps += 1
        action_name = self.ACTIONS[action]

        # Simulate tool execution outcome
        success = self.np_random.random() > 0.15  # 85% éxito simulado (aumentado para curriculum)
        latency = self.np_random.exponential(1.5)  # latencia reducida
        cost = 0.03 + self.np_random.random() * 0.07  # costo reducido

        # Base reward
        reward = 0.0
        if success:
            reward += 1.0
        else:
            reward -= 0.3  # penalización reducida
            self._retry_count += 1
            self._last_error_code = int(self.np_random.integers(1, 32))

        reward -= latency * 0.03  # peso de latencia reducido
        reward -= cost * 0.3  # peso de costo reducido

        # Curriculum progression
        if action_name == "next_tool" and success:
            self._stage_id += 1
            self._retry_count = 0
            self._last_error_code = 0

        # Budget consumption
        self._budget = max(0.0, self._budget - cost)

        # Validator score decay/recovery
        if action_name == "request_validation":
            self._validator_score = min(1.0, self._validator_score + 0.2)
        else:
            self._validator_score = max(0.0, self._validator_score - 0.05)

        # Queue pressure dynamics
        self._queue_pressure = min(1.0, self._queue_pressure + self.np_random.random() * 0.1)
        if action_name == "handoff_human":
            self._queue_pressure = max(0.0, self._queue_pressure - 0.3)

        # Termination conditions
        terminated = False
        truncated = False

        if self._stage_id >= self._max_stages:
            terminated = True
            reward += 5.0  # completion bonus aumentado
        elif self._budget <= 0.0:
            terminated = True
            reward -= 5.0  # budget exhaustion penalty
        elif action_name == "abort":
            terminated = True
            reward -= 1.0
        elif self._episode_steps >= self._max_stages * 3:
            truncated = True

        self._total_reward += reward
        return self._get_obs(), float(reward), terminated, truncated, self._get_info()

    def render(self) -> None:
        if self.render_mode == "human":
            print(
                f"[BagoWorkflowEnv] step={self._episode_steps} "
                f"stage={self._stage_id}/{self._max_stages} "
                f"budget={self._budget:.2f} "
                f"reward={self._total_reward:.2f}"
            )

    @classmethod
    def _self_test(cls) -> int:
        print("[BagoWorkflowEnv] Self-test starting...")

        # 1. Reset
        env = cls(curriculum="short", seed=42)
        obs, info = env.reset()
        assert obs["stage_id"] == 0
        print("   ✓ Reset OK")

        # 2. Step
        mask = env.available_actions_mask()
        valid_actions = np.where(mask)[0]
        action = int(valid_actions[0])
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(reward, float)
        print(f"   ✓ Step OK (reward={reward:.2f}, terminated={terminated})")

        # 3. Action masking
        mask = env.available_actions_mask()
        assert mask.dtype == bool
        assert mask.sum() > 0
        print(f"   ✓ Action mask OK ({mask.sum()}/{len(mask)} actions valid)")

        # 4. Invalid action still accepted by step (env does not enforce mask)
        #    but mask gives info to the agent
        obs, reward, terminated, truncated, info = env.step(0)
        print("   ✓ Step with arbitrary action OK")

        # 5. Curriculum lengths
        for cur, expected in env._stage_lengths.items():
            env2 = cls(curriculum=cur, seed=42)
            env2.reset()
            assert env2._max_stages == expected
        print("   ✓ Curriculum lengths OK")

        # 6. Episode completion
        env3 = cls(curriculum="short", seed=42)
        env3.reset()
        done = False
        total_reward = 0.0
        steps = 0
        while not done and steps < 50:
            mask = env3.available_actions_mask()
            valid = np.where(mask)[0]
            action = int(valid[0]) if len(valid) > 0 else 0
            obs, reward, terminated, truncated, info = env3.step(action)
            total_reward += reward
            done = terminated or truncated
            steps += 1
        assert done
        print(f"   ✓ Episode complete ({steps} steps, reward={total_reward:.2f})")

        print("[BagoWorkflowEnv] Self-test PASSED (6/6)")
        return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.exit(BagoWorkflowEnv._self_test())
    # Quick demo
    env = BagoWorkflowEnv(curriculum="short", seed=42)
    obs, info = env.reset()
    env.render()
    for _ in range(5):
        mask = env.available_actions_mask()
        valid = np.where(mask)[0]
        action = int(valid[0]) if len(valid) > 0 else 0
        obs, reward, terminated, truncated, info = env.step(action)
        env.render()
        if terminated or truncated:
            break

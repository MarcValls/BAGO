"""Action Masker para BagoWorkflowEnv.

Proporciona máscaras de acciones inválidas para algoritmos que
soportan action masking (MaskablePPO, MaskableDQN de sb3-contrib).

Ejemplo:
    from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
    from sb3_contrib.ppo_mask import MaskablePPO
    from action_masker import BagoActionMasker

    env = BagoWorkflowEnv()
    model = MaskablePPO(
        MaskableActorCriticPolicy,
        env,
        verbose=1,
    )
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

# Allow running as script
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from envs.bago_workflow_env import BagoWorkflowEnv
else:
    from ..envs.bago_workflow_env import BagoWorkflowEnv


class BagoActionMasker:
    """Wrapper opcional para exponer action_mask a SB3 Contrib."""

    def __init__(self, env: BagoWorkflowEnv) -> None:
        self.env = env

    def reset(self, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
        return self.env.reset(**kwargs)

    def step(self, action: int) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        return self.env.step(action)

    @property
    def action_space(self) -> Any:
        return self.env.action_space

    @property
    def observation_space(self) -> Any:
        return self.env.observation_space

    def action_masks(self) -> np.ndarray:
        """Retorna máscara compatible con SB3 Contrib MaskablePPO."""
        return self.env.available_actions_mask()

    def render(self) -> None:
        self.env.render()


if __name__ == "__main__":
    import sys

    env = BagoWorkflowEnv(seed=42)
    masker = BagoActionMasker(env)
    obs, info = masker.reset()
    mask = masker.action_masks()
    assert mask.dtype == bool
    assert mask.sum() > 0
    print(f"Action masker OK — {mask.sum()}/{len(mask)} valid actions")

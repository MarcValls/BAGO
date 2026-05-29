#!/usr/bin/env python3
"""bago_bandit_env.py — Contextual Bandit environment for BAGO tool routing.

Fase 1 del plan de integración de RL.
El agente recibe un contexto de tarea y debe elegir la mejor herramienta.
La recompensa llega inmediatamente (éxito/fallo + latencia).

Uso:
    from bago_bandit_env import BagoBanditEnv
    env = BagoBanditEnv()
    obs, info = env.reset()
    obs, reward, terminated, truncated, info = env.step(action_index)

Códigos: RL-B001 (OK), RL-B002 (acción inválida), RL-B003 (contexto vacío)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

BAGO_RL_DIR = Path(__file__).resolve().parent.parent
BAGO_ROOT = BAGO_RL_DIR.parent
TOOLS_DIR = BAGO_ROOT / "tools"

# Cargar dominios desde neural_toolbox si existe
try:
    spec = __import__("importlib.util").util.spec_from_file_location(
        "_neural_toolbox", str(TOOLS_DIR / "neural_toolbox.py")
    )
    _ntb_mod = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(_ntb_mod)
    DOMAINS = getattr(_ntb_mod, "DOMAINS", ())
except Exception:
    DOMAINS = (
        "security", "quality", "testing", "structure", "workflow",
        "database", "communication", "performance", "debug", "documentation",
    )

# Acciones: herramientas disponibles en BAGO (subset representativo)
# En producción, se cargarían dinámicamente desde tools.manifest.json
DEFAULT_ACTIONS = [
    "lint", "secret-scan", "type-check", "dep-audit", "complexity",
    "dead-code", "naming-check", "doc-coverage", "ci-report", "tool-guardian",
    "pre-push", "doctor", "metrics", "backup", "restore", "health-check",
    "bago_advisor", "bago_update", "validate", "audit_v2",
]

NUM_DOMAINS = len(DOMAINS)
NUM_ACTIONS = len(DEFAULT_ACTIONS)


class BagoBanditEnv(gym.Env):
    """Entorno contextual bandit para selección de herramienta en BAGO.

    Observación:
      - embedding de dominios del contexto (float vector, len=NUM_DOMAINS)
      - retry_count (int)
      - stage_id (int)
      - last_error_code (int)

    Acción:
      - índice discreto en [0, NUM_ACTIONS)

    Recompensa:
      - compuesta: éxito + latencia + coste
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        actions: list[str] | None = None,
        domains: tuple[str, ...] = DOMAINS,
        max_retries: int = 4,
        max_stages: int = 8,
        render_mode: str | None = None,
    ):
        super().__init__()
        self.actions = actions or DEFAULT_ACTIONS.copy()
        self.domains = domains
        self.max_retries = max_retries
        self.max_stages = max_stages
        self.render_mode = render_mode

        self.action_space = spaces.Discrete(len(self.actions))
        self.observation_space = spaces.Dict({
            "domain_signal": spaces.Box(
                low=-1.0, high=1.0, shape=(len(self.domains),), dtype=np.float32
            ),
            "retry_count": spaces.Discrete(self.max_retries + 1),
            "stage_id": spaces.Discrete(self.max_stages),
            "last_error_code": spaces.Discrete(16),
            "budget_left": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32),
        })

        self._current_context: str = ""
        self._retry_count: int = 0
        self._stage_id: int = 0
        self._last_error_code: int = 0
        self._budget: float = 1.0
        self._episode_id: str = ""

    def _encode_context(self, text: str) -> np.ndarray:
        """Codifica texto de contexto a señal de dominio.

        Fallback simple basado en keywords si no carga neural_toolbox.
        """
        text_lower = text.lower()
        signal = np.zeros(len(self.domains), dtype=np.float32)

        keyword_map = {
            "security": ["secret", "password", "token", "vulnerab", "cve", "inject", "seguridad"],
            "quality": ["lint", "style", "format", "calidad", "naming", "duplicate"],
            "testing": ["test", "coverage", "pytest", "ci", "check"],
            "structure": ["refactor", "complexity", "arch", "depend", "structure"],
            "workflow": ["workflow", "pipeline", "task", "session", "sprint"],
            "database": ["db", "state", "json", "backup", "restore"],
            "communication": ["notify", "message", "telegram", "whatsapp", "email"],
            "performance": ["speed", "perf", "latency", "metric", "benchmark"],
            "debug": ["debug", "error", "bug", "fix", "crash", "dead-code"],
            "documentation": ["doc", "readme", "docstring", "changelog", "comment"],
        }

        for i, domain in enumerate(self.domains):
            keywords = keyword_map.get(domain, [domain])
            score = 0.0
            for kw in keywords:
                if kw in text_lower:
                    score += 1.0
            signal[i] = min(score / max(len(keywords), 1), 1.0)
        return signal

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        options = options or {}
        self._current_context = options.get("context", "default task")
        self._retry_count = options.get("retry_count", 0)
        self._stage_id = options.get("stage_id", 0)
        self._last_error_code = options.get("last_error_code", 0)
        self._budget = options.get("budget", 1.0)
        self._episode_id = options.get("episode_id", "ep-" + str(np.random.randint(1_000_000)))

        obs = {
            "domain_signal": self._encode_context(self._current_context),
            "retry_count": self._retry_count,
            "stage_id": self._stage_id,
            "last_error_code": self._last_error_code,
            "budget_left": np.array([self._budget], dtype=np.float32),
        }
        info = {
            "episode_id": self._episode_id,
            "context": self._current_context,
        }
        return obs, info

    def step(self, action: int):
        if action < 0 or action >= len(self.actions):
            obs, _ = self.reset()
            reward = -1.0
            terminated = True
            truncated = False
            info = {"error": "invalid_action", "action": action}
            return obs, reward, terminated, truncated, info

        action_name = self.actions[action]

        # Simular resultado de la herramienta
        # En producción, esto vendría de la ejecución real en sandbox
        success = self.np_random.random() > 0.3  # 70% éxito simulado
        latency = self.np_random.exponential(2.0)  # segundos
        cost = 0.05 + self.np_random.random() * 0.1

        # Recompensa compuesta
        reward = 0.0
        if success:
            reward += 1.0
        else:
            reward += 0.0
            self._retry_count += 1
            self._last_error_code = int(self.np_random.integers(1, 16))
        reward -= 0.1 * min(latency / 10.0, 1.0)
        reward -= 0.05 * min(cost / 1.0, 1.0)
        self._budget -= cost

        terminated = not success or self._budget <= 0.0
        truncated = self._retry_count >= self.max_retries

        obs = {
            "domain_signal": self._encode_context(self._current_context),
            "retry_count": self._retry_count,
            "stage_id": self._stage_id,
            "last_error_code": self._last_error_code,
            "budget_left": np.array([max(self._budget, 0.0)], dtype=np.float32),
        }
        info = {
            "action_name": action_name,
            "success": success,
            "latency": latency,
            "cost": cost,
            "episode_id": self._episode_id,
        }
        return obs, reward, terminated, truncated, info

    def render(self):
        if self.render_mode == "human":
            print(f"[BagoBandit] context='{self._current_context[:40]}' "
                  f"retry={self._retry_count} stage={self._stage_id} budget={self._budget:.2f}")

    @classmethod
    def from_tools_manifest(cls, manifest_path: Path | None = None) -> "BagoBanditEnv":
        """Crea el entorno cargando las acciones reales desde tools.manifest.json."""
        if manifest_path is None:
            manifest_path = BAGO_ROOT / "tools.manifest.json"
        actions = DEFAULT_ACTIONS.copy()
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                actions = list(data.keys()) if isinstance(data, dict) else actions
            except Exception:
                pass
        return cls(actions=actions)


def main() -> int:
    print("[BagoBanditEnv] Self-test starting...")
    env = BagoBanditEnv()

    # Test 1: reset
    obs, info = env.reset(options={"context": "check security vulnerabilities"})
    assert "domain_signal" in obs, "obs must contain domain_signal"
    assert obs["domain_signal"].shape == (len(DOMAINS),), "domain_signal shape mismatch"
    print("  ✓ Reset OK")

    # Test 2: step con acción válida
    obs, reward, terminated, truncated, info = env.step(0)
    assert isinstance(reward, float), "reward must be float"
    assert isinstance(terminated, bool), "terminated must be bool"
    print(f"  ✓ Step OK (reward={reward:.2f}, terminated={terminated})")

    # Test 3: step con acción inválida
    obs, reward, terminated, truncated, info = env.step(999)
    assert reward == -1.0, "invalid action reward should be -1.0"
    assert info.get("error") == "invalid_action", "invalid action info"
    print("  ✓ Invalid action handled")

    # Test 4: render
    env.render()
    print("  ✓ Render OK")

    # Test 5: episodio completo
    obs, info = env.reset(options={"context": "lint and format code", "budget": 0.5})
    total_reward = 0.0
    for _ in range(10):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated or truncated:
            break
    print(f"  ✓ Episode complete (total_reward={total_reward:.2f})")

    # Test 6: carga desde manifest
    env2 = BagoBanditEnv.from_tools_manifest()
    assert len(env2.actions) > 0, "from_tools_manifest should return actions"
    print("  ✓ from_tools_manifest OK")

    print("[BagoBanditEnv] Self-test PASSED (6/6)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

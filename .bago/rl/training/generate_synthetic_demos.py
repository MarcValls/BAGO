"""Generador de demostraciones expertas sintéticas para Fase 2.

Simula un agente experto que resuelve workflows de BAGO de forma óptima,
generando transiciones JSONL listas para entrenar BC.

Ejemplo:
    python .bago/rl/training/generate_synthetic_demos.py \
        --episodes 1000 --output .bago/logs/synthetic_demos.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Env reference (standalone to avoid import issues)
# ---------------------------------------------------------------------------
ACTIONS = [
    "next_tool", "retry", "skip", "request_validation",
    "handoff_human", "abort", "change_strategy",
]


def encode_obs(obs: dict) -> list[float]:
    """Plana un obs dict a vector float."""
    flat: list[float] = []
    flat.append(float(obs["stage_id"]))
    flat.append(float(obs["retry_count"]))
    flat.extend(obs["queue_pressure"].tolist())
    flat.extend(obs["budget_left"].tolist())
    flat.extend(obs["last_validator_score"].tolist())
    flat.append(float(obs["last_error_code"]))
    flat.extend(obs["tools_available"].tolist())
    return flat


def expert_policy(obs: dict, rng: np.random.Generator) -> int:
    """Política heurística experta: prioriza éxito y seguridad."""
    stage = int(obs["stage_id"])
    retry = int(obs["retry_count"])
    budget = float(obs["budget_left"][0])
    score = float(obs["last_validator_score"][0])
    error = int(obs["last_error_code"])

    # Reglas expertas
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
    if rng.random() > 0.9:
        return ACTIONS.index("change_strategy")
    return ACTIONS.index("next_tool")


def generate_episode(
    max_steps: int = 20,
    rng: np.random.Generator | None = None,
) -> list[dict]:
    """Genera un episodio completo con política experta."""
    rng = rng or np.random.default_rng()
    transitions: list[dict] = []

    # Initial state
    stage_id = 0
    retry_count = 0
    queue_pressure = rng.random()
    budget = 1.0
    validator_score = 1.0
    last_error_code = 0
    tools_available = rng.integers(0, 2, size=32).astype(np.int8)

    for step in range(max_steps):
        obs = {
            "stage_id": stage_id,
            "retry_count": retry_count,
            "queue_pressure": np.array([queue_pressure], dtype=np.float32),
            "budget_left": np.array([budget], dtype=np.float32),
            "last_validator_score": np.array([validator_score], dtype=np.float32),
            "last_error_code": last_error_code,
            "tools_available": tools_available.copy(),
        }
        action = expert_policy(obs, rng)
        action_name = ACTIONS[action]

        # Simulate outcome (expert succeeds 85% of the time)
        success = rng.random() > 0.15
        latency = rng.exponential(1.5) if success else rng.exponential(4.0)
        cost = 0.03 + rng.random() * 0.07

        reward = 1.0 if success else -0.5
        reward -= latency * 0.03
        reward -= cost * 0.3

        if action_name == "next_tool" and success:
            stage_id += 1
            retry_count = 0
            last_error_code = 0
        elif action_name == "retry":
            retry_count += 1
            if not success:
                last_error_code = int(rng.integers(1, 32))
        elif action_name == "request_validation":
            validator_score = min(1.0, validator_score + 0.3)
        elif action_name == "handoff_human":
            queue_pressure = max(0.0, queue_pressure - 0.4)
            reward += 0.5
        elif action_name == "abort":
            reward -= 2.0

        budget = max(0.0, budget - cost)
        queue_pressure = min(1.0, queue_pressure + rng.random() * 0.05)
        validator_score = max(0.0, validator_score - 0.03)

        next_obs = {
            "stage_id": stage_id,
            "retry_count": retry_count,
            "queue_pressure": np.array([queue_pressure], dtype=np.float32),
            "budget_left": np.array([budget], dtype=np.float32),
            "last_validator_score": np.array([validator_score], dtype=np.float32),
            "last_error_code": last_error_code,
            "tools_available": tools_available.copy(),
        }

        transitions.append({
            "state": encode_obs(obs),
            "action": action,
            "reward": round(reward, 4),
            "next_state": encode_obs(next_obs),
            "done": action_name in ("abort",) or stage_id >= 10 or budget <= 0.0,
        })

        if action_name == "abort" or stage_id >= 10 or budget <= 0.0:
            break

    return transitions


def generate_dataset(
    episodes: int = 1000,
    output: Path | None = None,
    seed: int = 42,
) -> Path:
    """Genera un dataset JSONL de demostraciones expertas."""
    rng = np.random.default_rng(seed)
    output = output or Path(".bago/logs/synthetic_demos.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with output.open("w", encoding="utf-8") as fh:
        for _ in range(episodes):
            ep = generate_episode(rng=rng)
            for t in ep:
                fh.write(json.dumps(t) + "\n")
                total += 1

    print(f"[SyntheticDemos] Generadas {total} transiciones en {output}")
    return output


def _self_test() -> int:
    print("[SyntheticDemos] Self-test starting...")
    import tempfile

    tmpdir = Path(tempfile.mkdtemp(prefix="bago_synth_test_"))
    path = generate_dataset(episodes=50, output=tmpdir / "demo.jsonl", seed=123)

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) > 0
    data = json.loads(lines[0])
    assert "state" in data
    assert "action" in data
    assert "reward" in data
    assert "next_state" in data
    assert "done" in data
    print(f"   ✓ Dataset valid — {len(lines)} transitions")

    # Coverage check
    actions = [json.loads(l)["action"] for l in lines]
    unique = len(set(actions))
    assert unique >= 2, f"Expected ≥2 unique actions, got {unique}"
    print(f"   ✓ Action coverage — {unique}/{len(ACTIONS)} unique actions")

    # Cleanup
    path.unlink()
    tmpdir.rmdir()
    print("[SyntheticDemos] Self-test PASSED (2/2)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Genera demostraciones expertas sintéticas.")
    p.add_argument("--episodes", type=int, default=1000, help="Número de episodios.")
    p.add_argument("--output", type=Path, default=Path(".bago/logs/synthetic_demos.jsonl"))
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    generate_dataset(episodes=args.episodes, output=args.output, seed=args.seed)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.exit(_self_test())
    sys.exit(main())

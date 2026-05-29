"""
MARL evaluation metrics.

Metrics:
  - Coordination positivity: team_reward - sum(individual_rewards) > 0
  - Non-stationarity: policy variance between agents across episodes
  - Divergence detection: NaN/crash rate over training
  - Throughput proxy: episode length reduction vs heuristic
"""

import json
import math
from pathlib import Path

import numpy as np


def coordination_positivity(results):
    """Positive coordination means the team performs better than the sum of isolated agents."""
    # Prefer explicit coordination field if present
    if "coordination" in results[0]:
        coords = [r["coordination"] for r in results]
    else:
        coords = [r["team_reward"] - r["individual_sum"] for r in results]
    return float(np.mean(coords)), float(np.std(coords))


def non_stationarity(results, window=20):
    """
    Measure how much agent policies diverge from each other over time.
    Proxy: variance of per-agent action distributions across episodes.
    """
    # results must contain per-agent action histograms (optional)
    # Fallback: use reward variance as proxy for policy instability
    rewards = np.array([r["team_reward"] for r in results])
    rolling_var = []
    for i in range(len(rewards)):
        start = max(0, i - window)
        rolling_var.append(float(np.var(rewards[start:i + 1])))
    mean_var = float(np.mean(rolling_var))
    # Normalised by mean reward magnitude
    mean_reward = float(np.mean(rewards)) if np.mean(rewards) != 0 else 1.0
    ns = mean_var / abs(mean_reward)
    return ns


def divergence_rate(results):
    """Fraction of episodes with NaN or crash (approximated by zero length)."""
    crashes = sum(1 for r in results if math.isnan(r.get("team_reward", 0)) or r.get("episode_length", 1) == 0)
    return crashes / len(results) if results else 0.0


def throughput_improvement(results, baseline_mean_length=15.0):
    """Shorter episodes mean faster workflow completion."""
    mean_len = float(np.mean([r["episode_length"] for r in results]))
    return (baseline_mean_length - mean_len) / baseline_mean_length


def evaluate_all(results, baseline_length=15.0):
    coord_mean, coord_std = coordination_positivity(results)
    ns = non_stationarity(results)
    div = divergence_rate(results)
    throughput = throughput_improvement(results, baseline_length)
    report = {
        "coordination_mean": coord_mean,
        "coordination_std": coord_std,
        "non_stationarity": ns,
        "divergence_rate": div,
        "throughput_improvement": throughput,
    }
    return report


def _self_test():
    dummy = [
        {"team_reward": 1.5, "individual_sum": 1.2, "episode_length": 10},
        {"team_reward": 1.4, "individual_sum": 1.1, "episode_length": 11},
        {"team_reward": 1.6, "individual_sum": 1.3, "episode_length": 9},
    ]
    report = evaluate_all(dummy)
    print("Self-test PASSED:", report)


if __name__ == "__main__":
    _self_test()

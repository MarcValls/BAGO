from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / ".bago" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from rl_engine import FeedbackCollector, PreferenceModel, RLPolicy, RewardStore


def test_reward_store_persists_append_only_through_gateway(tmp_path) -> None:
    state_root = tmp_path / "isolated" / "state"
    store = RewardStore(state_root=state_root)

    store.append("s1", "ollama-local", "llama3.2:3b", 0.8, "hola_10")
    store.append("s1", "ollama-local", "llama3.2:1b", 0.4, "hola_10")

    rewards = store.read_all()
    assert len(rewards) == 2
    assert rewards[0]["reward"] == 0.8
    assert store._file.is_file()


def test_preference_cache_policy_and_feedback(tmp_path) -> None:
    state_root = tmp_path / "state"
    pm = PreferenceModel(state_root=state_root)
    pm.add_reward("s1", "ollama-local", "llama3.2:3b", 0.8, "hola_10")
    pm.add_reward("s1", "ollama-local", "llama3.2:3b", 0.9, "hola_10")
    pm.add_reward("s1", "ollama-local", "llama3.2:1b", 0.3, "hola_10")

    cold = PreferenceModel(state_root=state_root)
    assert abs(cold.score("ollama-local", "llama3.2:3b", "hola_10") - 0.85) < 0.01
    assert abs(cold.score("ollama-local", "llama3.2:3b") - 0.85) < 0.01
    assert cold.best("", [("ollama-local", "llama3.2:3b"), ("ollama-local", "llama3.2:1b")]) == ("ollama-local", "llama3.2:3b")
    assert cold.best("", [("openrouter", "nous/hermes-3")]) is None
    assert cold.best("hola_10", [("ollama-local", "llama3.2:3b"), ("ollama-local", "llama3.2:1b")]) == ("ollama-local", "llama3.2:3b")

    policy = RLPolicy(cold, epsilon=0.0, ucb_c=1.414)
    assert policy.select([("ollama-local", "llama3.2:3b"), ("ollama-local", "llama3.2:1b")], "hola_10") == ("ollama-local", "llama3.2:3b")

    feedback = FeedbackCollector(cold)
    reward = feedback.implicit("s2", "ollama-local", "llama3.2:3b", "hola", "OK todo bien", 1500, 42)
    assert isinstance(reward, float) and -1.0 <= reward <= 1.0
    feedback.explicit("s2", "ollama-local", "llama3.2:3b", "hola", 1.0)
    assert cold.score("ollama-local", "llama3.2:3b", "hola_4") >= 0.0

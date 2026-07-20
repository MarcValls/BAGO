from __future__ import annotations

import json

import pytest


def test_rl_bridge_defaults_to_shadow_and_never_executes(tmp_path):
    from bago_core.rl_bridge import RLBridge

    bridge = RLBridge(tmp_path)
    status = bridge.status()
    assert status["mode"] == "shadow"
    assert status["can_execute"] is False
    assert status["rules"]["allowed_modes"] == ["off", "shadow"]


def test_control_shadow_rejects_promotion_without_gate(tmp_path):
    from control_shadow import ControlShadow

    shadow = ControlShadow(state_root=str(tmp_path))
    with pytest.raises(ValueError, match="gate de promoción"):
        shadow.configure(mode="canary")
    with pytest.raises(ValueError, match="gate de promoción"):
        shadow.configure(mode="full")
    assert shadow.status()["mode"] == "shadow"
    assert shadow.status()["authority"] == "observer-only"


def test_bc_training_and_evaluation_remain_non_executing(tmp_path, monkeypatch):
    from bago_core import rl_policies

    monkeypatch.setattr(rl_policies, "state_root", lambda: tmp_path)
    events = [
        {"features": [1.0, 0.0, 0.0, 0.0], "action": 0, "reward": 1.0},
        {"features": [0.0, 1.0, 0.0, 0.0], "action": 1, "reward": 1.0},
    ]
    transition_log = tmp_path / "rl_transitions.jsonl"
    transition_log.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    trained = rl_policies.train_bc_policy(tmp_path, n_actions=4, n_features=4)
    evaluated = rl_policies.eval_bc_policy(tmp_path, n_features=4)

    assert trained["status"] == "trained"
    assert trained["samples"] == 2
    assert trained["can_execute"] is False
    assert evaluated["status"] == "ok"
    assert evaluated["can_execute"] is False

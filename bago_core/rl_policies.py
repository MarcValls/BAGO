from __future__ import annotations

import json
from pathlib import Path
from typing import Any


try:
    import numpy as np
except Exception:
    np = None  # type: ignore[assignment]


def numpy_available() -> bool:
    return np is not None


def _require_numpy() -> Any:
    if np is None:
        raise RuntimeError("numpy not installed; RL policy layer disabled")
    return np


class LinUCBPolicy:
    def __init__(self, n_actions: int, n_features: int, alpha: float = 1.0):
        npx = _require_numpy()
        self.n_actions = n_actions
        self.n_features = n_features
        self.alpha = alpha
        self.A = [npx.eye(n_features) for _ in range(n_actions)]
        self.b = [npx.zeros(n_features) for _ in range(n_actions)]
        self.thetas = [npx.zeros(n_features) for _ in range(n_actions)]
        self._update_all()

    def _update_all(self) -> None:
        npx = _require_numpy()
        for action in range(self.n_actions):
            try:
                self.thetas[action] = npx.linalg.solve(self.A[action], self.b[action])
            except npx.linalg.LinAlgError:
                self.thetas[action] = npx.zeros(self.n_features)

    def select(self, features: Any) -> int:
        npx = _require_numpy()
        x = npx.asarray(features, dtype=float)
        scores = []
        for action in range(self.n_actions):
            theta = self.thetas[action]
            inv_a = npx.linalg.inv(self.A[action])
            score = theta @ x + self.alpha * npx.sqrt(x @ inv_a @ x)
            scores.append(score)
        return int(npx.argmax(scores))

    def update(self, action: int, features: Any, reward: float) -> None:
        npx = _require_numpy()
        x = npx.asarray(features, dtype=float)
        self.A[action] += npx.outer(x, x)
        self.b[action] += float(reward) * x
        self._update_all()


class BCPolicy:
    def __init__(self, n_actions: int, n_features: int, lr: float = 0.01):
        npx = _require_numpy()
        self.n_actions = n_actions
        self.n_features = n_features
        self.lr = lr
        self.W = npx.zeros((n_actions, n_features))
        self.bias = npx.zeros(n_actions)

    def _softmax(self, values: Any) -> Any:
        npx = _require_numpy()
        arr = npx.asarray(values, dtype=float)
        e = npx.exp(arr - npx.max(arr))
        return e / e.sum()

    def predict(self, features: Any) -> int:
        npx = _require_numpy()
        x = npx.asarray(features, dtype=float)
        logits = self.W @ x + self.bias
        probs = self._softmax(logits)
        return int(npx.argmax(probs))

    def train_step(self, features: Any, action: int, reward: float) -> float:
        npx = _require_numpy()
        x = npx.asarray(features, dtype=float)
        logits = self.W @ x + self.bias
        probs = self._softmax(logits)
        target = npx.zeros(self.n_actions)
        target[action] = 1.0
        grad = (probs - target) * float(reward)
        self.W -= self.lr * npx.outer(grad, x)
        self.bias -= self.lr * grad
        return float(-npx.log(max(probs[action], 1e-8)) * float(reward))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "n_actions": self.n_actions,
            "n_features": self.n_features,
            "lr": self.lr,
            "W": self.W.tolist(),
            "bias": self.bias.tolist(),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BCPolicy":
        npx = _require_numpy()
        data = json.loads(path.read_text(encoding="utf-8"))
        policy = cls(data["n_actions"], data["n_features"], data.get("lr", 0.01))
        policy.W = npx.asarray(data["W"], dtype=float)
        policy.bias = npx.asarray(data["bias"], dtype=float)
        return policy


def policy_dir(base_path: str | Path) -> Path:
    return Path(base_path) / ".bago" / "state" / "rl_policies"


def bc_policy_path(base_path: str | Path) -> Path:
    return policy_dir(base_path) / "bc_policy.json"


def _transition_log(base_path: str | Path) -> Path:
    return Path(base_path) / ".bago" / "state" / "rl_transitions.jsonl"


def load_transition_samples(base_path: str | Path, n_features: int) -> list[tuple[list[float], int, float]]:
    path = _transition_log(base_path)
    if not path.exists():
        return []
    samples: list[tuple[list[float], int, float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        features = event.get("features")
        action = event.get("action")
        reward = event.get("reward", 1.0)
        if not isinstance(features, list) or len(features) != n_features:
            continue
        if not isinstance(action, int):
            continue
        try:
            samples.append(([float(v) for v in features], action, float(reward)))
        except Exception:
            continue
    return samples


def train_bc_policy(base_path: str | Path, n_actions: int, n_features: int) -> dict[str, Any]:
    if not numpy_available():
        return {"status": "disabled", "reason": "numpy not installed", "can_execute": False}
    samples = load_transition_samples(base_path, n_features)
    if not samples:
        return {
            "status": "no_samples",
            "samples": 0,
            "policy_file": str(bc_policy_path(base_path)),
            "can_execute": False,
        }
    policy = BCPolicy(n_actions, n_features)
    losses = []
    for features, action, reward in samples:
        if 0 <= action < n_actions:
            losses.append(policy.train_step(features, action, reward))
    policy.save(bc_policy_path(base_path))
    return {
        "status": "trained",
        "samples": len(losses),
        "loss": float(sum(losses) / len(losses)) if losses else 0.0,
        "policy_file": str(bc_policy_path(base_path)),
        "can_execute": False,
    }


def eval_bc_policy(base_path: str | Path, n_features: int) -> dict[str, Any]:
    if not numpy_available():
        return {"status": "disabled", "reason": "numpy not installed", "can_execute": False}
    path = bc_policy_path(base_path)
    if not path.exists():
        return {"status": "no_policy", "policy_file": str(path), "can_execute": False}
    policy = BCPolicy.load(path)
    prediction = policy.predict([0.0 for _ in range(n_features)])
    return {
        "status": "ok",
        "policy_file": str(path),
        "prediction_for_zero_vector": prediction,
        "can_execute": False,
    }


def render_policy_report(report: dict[str, Any], title: str) -> str:
    lines = [title, "-" * 40]
    for key, value in report.items():
        lines.append(f"{key:12}: {value}")
    lines.append("rule        : policy layer never executes actions directly")
    return "\n".join(lines)

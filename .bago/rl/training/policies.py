# -*- coding: utf-8 -*-
"""policies.py — Políticas RL para selección de herramientas BAGO: LinUCB y BC."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class LinUCBPolicy:
    """Política LinUCB para selección de herramientas BAGO."""

    def __init__(self, n_actions: int, n_features: int, alpha: float = 1.0):
        self.n_actions = n_actions
        self.n_features = n_features
        self.alpha = alpha
        self.A = [np.eye(n_features) for _ in range(n_actions)]
        self.b = [np.zeros(n_features) for _ in range(n_actions)]
        self.thetas = [np.zeros(n_features) for _ in range(n_actions)]
        self._update_all()

    def _update_all(self) -> None:
        for a in range(self.n_actions):
            try:
                self.thetas[a] = np.linalg.solve(self.A[a], self.b[a])
            except np.linalg.LinAlgError:
                self.thetas[a] = np.zeros(self.n_features)

    def select(self, x: np.ndarray) -> int:
        scores = []
        for a in range(self.n_actions):
            theta = self.thetas[a]
            inv_A = np.linalg.inv(self.A[a])
            p = theta @ x + self.alpha * np.sqrt(x @ inv_A @ x)
            scores.append(p)
        return int(np.argmax(scores))

    def update(self, action: int, x: np.ndarray, reward: float) -> None:
        self.A[action] += np.outer(x, x)
        self.b[action] += reward * x
        self._update_all()

    def save(self, path: Path) -> None:
        data = {
            "n_actions": self.n_actions,
            "n_features": self.n_features,
            "alpha": float(self.alpha),
            "A": [a.tolist() for a in self.A],
            "b": [b.tolist() for b in self.b],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "LinUCBPolicy":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pol = cls(data["n_actions"], data["n_features"], data["alpha"])
        pol.A = [np.array(a) for a in data["A"]]
        pol.b = [np.array(b) for b in data["b"]]
        pol._update_all()
        return pol


class BCPolicy:
    """Política simple de clasificación lineal para Behavioral Cloning."""

    def __init__(self, n_actions: int, n_features: int, lr: float = 0.01):
        self.n_actions = n_actions
        self.n_features = n_features
        self.lr = lr
        self.W = np.zeros((n_actions, n_features))
        self.bias = np.zeros(n_actions)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()

    def predict(self, x: np.ndarray) -> int:
        logits = self.W @ x + self.bias
        probs = self._softmax(logits)
        return int(np.argmax(probs))

    def train_step(self, x: np.ndarray, action: int, reward: float) -> float:
        logits = self.W @ x + self.bias
        probs = self._softmax(logits)
        target = np.zeros(self.n_actions)
        target[action] = 1.0
        grad = (probs - target) * reward
        self.W -= self.lr * np.outer(grad, x)
        self.bias -= self.lr * grad
        loss = -np.log(max(probs[action], 1e-8)) * reward
        return float(loss)

    def save(self, path: Path) -> None:
        data = {
            "n_actions": self.n_actions,
            "n_features": self.n_features,
            "W": self.W.tolist(),
            "bias": self.bias.tolist(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "BCPolicy":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pol = cls(data["n_actions"], data["n_features"])
        pol.W = np.array(data["W"])
        pol.bias = np.array(data["bias"])
        return pol

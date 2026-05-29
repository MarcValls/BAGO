#!/usr/bin/env python3
"""train_bc.py — Entrenamiento Behavioral Cloning desde transiciones JSONL.

Uso:
    python train_bc.py --input .bago/logs/rl_transitions.jsonl --epochs 20

El modelo aprende a predecir la acción a partir de la observación,
imitando el comportamiento capturado por los hooks.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Permitir importar desde el directorio raíz de RL
RL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RL_ROOT))


def _flatten_obs(obs: dict[str, Any]) -> np.ndarray:
    """Aplana un dict de observación a un vector numérico."""
    values = []
    for v in obs.values():
        if isinstance(v, (int, float)):
            values.append(float(v))
        elif isinstance(v, bool):
            values.append(1.0 if v else 0.0)
        elif isinstance(v, str):
            # Hash simple para strings
            values.append(float(hash(v) % 10000) / 10000.0)
        elif isinstance(v, list):
            values.extend(float(x) for x in v)
        else:
            values.append(0.0)
    return np.array(values, dtype=np.float32)


def load_transitions(jsonl_path: Path):
    """Carga transiciones desde JSONL."""
    transitions = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                transitions.append(data)
            except json.JSONDecodeError:
                continue
    return transitions


def build_dataset(transitions: list[dict[str, Any]]):
    """Construye X (obs) e y (action) desde transiciones."""
    X_list, y_list, rewards = [], [], []
    action_to_idx: dict[str, int] = {}
    idx_counter = 0

    for t in transitions:
        obs = t.get("observation", {})
        action = t.get("action", 0)
        reward = t.get("reward", 0.0)

        # Si reward es dict, tomar valor agregado
        if isinstance(reward, dict):
            reward = sum(reward.values())

        # Vectorizar observación
        x = _flatten_obs(obs)
        X_list.append(x)

        # Codificar acción: mapear strings/int únicos a índices consecutivos
        action_key = str(action)
        if action_key not in action_to_idx:
            action_to_idx[action_key] = idx_counter
            idx_counter += 1
        y_list.append(action_to_idx[action_key])

        rewards.append(float(reward))

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    rewards = np.array(rewards, dtype=np.float32)
    return X, y, rewards, action_to_idx


class BCSimpleNN:
    """Red neuronal simple para BC."""

    def __init__(self, input_dim: int, num_actions: int, hidden: int = 64):
        self.input_dim = input_dim
        self.num_actions = num_actions
        self.hidden = hidden

        # Inicialización Xavier
        scale1 = np.sqrt(2.0 / input_dim)
        scale2 = np.sqrt(2.0 / hidden)
        self.W1 = np.random.randn(input_dim, hidden).astype(np.float32) * scale1
        self.b1 = np.zeros(hidden, dtype=np.float32)
        self.W2 = np.random.randn(hidden, hidden).astype(np.float32) * scale2
        self.b2 = np.zeros(hidden, dtype=np.float32)
        self.W3 = np.random.randn(hidden, num_actions).astype(np.float32) * scale2
        self.b3 = np.zeros(num_actions, dtype=np.float32)

        self._cache = {}

    def forward(self, X: np.ndarray, training: bool = False) -> np.ndarray:
        """Forward pass. Retorna logits."""
        z1 = X @ self.W1 + self.b1
        a1 = np.maximum(z1, 0)  # ReLU
        z2 = a1 @ self.W2 + self.b2
        a2 = np.maximum(z2, 0)  # ReLU
        logits = a2 @ self.W3 + self.b3

        if training:
            self._cache = {"X": X, "z1": z1, "a1": a1, "z2": z2, "a2": a2, "logits": logits}
        return logits

    def backward(self, grad_logits: np.ndarray, lr: float = 0.01) -> None:
        """Backward pass + SGD."""
        cache = self._cache
        X, z1, a1, z2, a2 = cache["X"], cache["z1"], cache["a1"], cache["z2"], cache["a2"]
        m = X.shape[0]

        # Capa 3
        dW3 = (a2.T @ grad_logits) / m
        db3 = grad_logits.mean(axis=0)
        da2 = grad_logits @ self.W3.T
        dz2 = da2 * (z2 > 0).astype(np.float32)

        # Capa 2
        dW2 = (a1.T @ dz2) / m
        db2 = dz2.mean(axis=0)
        da1 = dz2 @ self.W2.T
        dz1 = da1 * (z1 > 0).astype(np.float32)

        # Capa 1
        dW1 = (X.T @ dz1) / m
        db1 = dz1.mean(axis=0)

        # Update
        self.W3 -= lr * dW3
        self.b3 -= lr * db3
        self.W2 -= lr * dW2
        self.b2 -= lr * db2
        self.W1 -= lr * dW1
        self.b1 -= lr * db1

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predice acciones (índices)."""
        logits = self.forward(X)
        return logits.argmax(axis=1)

    def save(self, path: Path, action_to_idx: dict[str, int] | None = None) -> None:
        """Guarda pesos, metadata y mapeo de acciones."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "W1": self.W1, "b1": self.b1,
            "W2": self.W2, "b2": self.b2,
            "W3": self.W3, "b3": self.b3,
            "input_dim": self.input_dim,
            "num_actions": self.num_actions,
            "hidden": self.hidden,
            "action_to_idx": action_to_idx or {},
        }
        with path.open("wb") as f:
            pickle.dump(data, f)
        print(f"[BC] Checkpoint guardado: {path}")

    @classmethod
    def load(cls, path: Path) -> "BCSimpleNN":
        with path.open("rb") as f:
            data = pickle.load(f)
        net = cls(data["input_dim"], data["num_actions"], data["hidden"])
        net.W1, net.b1 = data["W1"], data["b1"]
        net.W2, net.b2 = data["W2"], data["b2"]
        net.W3, net.b3 = data["W3"], data["b3"]
        # Guardar el mapeo de acciones como atributo de la red
        net.action_to_idx = data.get("action_to_idx", {})
        return net


def train_bc(X: np.ndarray, y: np.ndarray, epochs: int = 20, lr: float = 0.01, batch_size: int = 32):
    """Entrena BC con cross-entropy."""
    num_samples, input_dim = X.shape
    num_actions = int(y.max()) + 1

    print(f"[BC] Dataset: {num_samples} muestras, {input_dim} features, {num_actions} acciones")

    net = BCSimpleNN(input_dim, num_actions)

    for epoch in range(1, epochs + 1):
        # Shuffle
        indices = np.random.permutation(num_samples)
        X_shuf, y_shuf = X[indices], y[indices]

        total_loss = 0.0
        correct = 0
        num_batches = 0

        for i in range(0, num_samples, batch_size):
            X_batch = X_shuf[i:i + batch_size]
            y_batch = y_shuf[i:i + batch_size]
            m = X_batch.shape[0]

            logits = net.forward(X_batch, training=True)
            # Softmax
            exp_logits = np.exp(logits - logits.max(axis=1, keepdims=True))
            probs = exp_logits / exp_logits.sum(axis=1, keepdims=True)

            # Cross-entropy
            log_probs = np.log(probs[np.arange(m), y_batch] + 1e-8)
            loss = -log_probs.mean()
            total_loss += loss

            # Accuracy
            pred = logits.argmax(axis=1)
            correct += (pred == y_batch).sum()
            num_batches += 1

            # Gradients
            grad = probs.copy()
            grad[np.arange(m), y_batch] -= 1
            grad /= m
            net.backward(grad, lr=lr)

        acc = correct / num_samples
        avg_loss = total_loss / max(num_batches, 1)
        print(f"[BC] Epoch {epoch:3d}/{epochs} | loss={avg_loss:.4f} | acc={acc:.2%}")

    return net, acc


def main() -> int:
    parser = argparse.ArgumentParser(description="Entrenar Behavioral Cloning desde JSONL")
    parser.add_argument("--input", type=Path, required=True, help="Ruta al JSONL de transiciones")
    parser.add_argument("--epochs", type=int, default=20, help="Épocas de entrenamiento")
    parser.add_argument("--lr", type=float, default=0.01, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=32, help="Tamaño de batch")
    parser.add_argument("--output-dir", type=Path, default=Path(".bago/rl/checkpoints/bc"), help="Directorio de salida")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[BC] ERROR: No existe {args.input}")
        return 1

    transitions = load_transitions(args.input)
    if len(transitions) < 5:
        print(f"[BC] ERROR: Solo {len(transitions)} transiciones. Necesitas al menos 5.")
        return 1

    print(f"[BC] Cargadas {len(transitions)} transiciones desde {args.input}")
    X, y, rewards, action_to_idx = build_dataset(transitions)

    # Filtrar transiciones con reward negativo (errores) para imitar solo éxitos
    positive_mask = rewards >= 0
    if positive_mask.sum() >= 5:
        print(f"[BC] Filtrando {positive_mask.sum()}/{len(transitions)} transiciones con reward >= 0")
        X = X[positive_mask]
        y = y[positive_mask]

    net, acc = train_bc(X, y, epochs=args.epochs, lr=args.lr, batch_size=args.batch_size)

    # Guardar
    ckpt = args.output_dir / "bc_model.pkl"
    net.save(ckpt, action_to_idx=action_to_idx)

    # Guardar metadata
    meta = {
        "num_samples": len(transitions),
        "input_dim": net.input_dim,
        "num_actions": net.num_actions,
        "final_accuracy": float(acc),
        "epochs": args.epochs,
    }
    meta_path = args.output_dir / "bc_meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[BC] Metadata guardada: {meta_path}")

    print(f"\n✅ [BC] Entrenamiento completado. Acc final: {acc:.2%}")
    print(f"   Checkpoint: {ckpt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

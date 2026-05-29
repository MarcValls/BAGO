"""Entrenamiento Offline RL para BAGO (Fase 2).

Convierte logs JSONL en un replay buffer y entrena una política conservadora
usando Behavioral Cloning (BC) como primer paso.  Los algoritmos BCQ / CQL
se añadirán cuando Tianshou esté disponible.

Ejemplo:
    python .bago/rl/training/train_offline.py \
        --logs .bago/logs/transitions.jsonl \
        --output .bago/rl/policies/offline_bc.pt \
        --epochs 10 --batch-size 256
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Dependencias opcionales
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_AVAILABLE = True
except Exception:  # pragma: no cover
    _TORCH_AVAILABLE = False
    torch = None  # type: ignore[misc]
    nn = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Transition:
    """Una transición S-A-R-S' (optionally truncated/terminated)."""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    info: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Dataset reader
# ---------------------------------------------------------------------------
class JSONLReplayBuffer:
    """Buffer en memoria construido desde JSONL de transiciones."""

    def __init__(self, max_size: int = 1_000_000) -> None:
        self.max_size = max_size
        self._transitions: list[Transition] = []

    @classmethod
    def from_jsonl(cls, path: Path, max_size: int = 1_000_000) -> "JSONLReplayBuffer":
        buf = cls(max_size=max_size)
        if not path.exists():
            return buf
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    state = np.array(data["state"], dtype=np.float32)
                    action = int(data["action"])
                    reward = float(data["reward"])
                    next_state = np.array(data["next_state"], dtype=np.float32)
                    done = bool(data["done"])
                    info = data.get("info")
                    buf.add(Transition(state, action, reward, next_state, done, info))
                except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
                    warnings.warn(f"Línea descartada: {exc}")
                    continue
        return buf

    def add(self, transition: Transition) -> None:
        self._transitions.append(transition)
        if len(self._transitions) > self.max_size:
            self._transitions.pop(0)

    def __len__(self) -> int:
        return len(self._transitions)

    def sample(self, batch_size: int) -> list[Transition]:
        if batch_size >= len(self._transitions):
            return self._transitions
        return random.sample(self._transitions, batch_size)

    def states(self) -> np.ndarray:
        return np.array([t.state for t in self._transitions], dtype=np.float32)

    def actions(self) -> np.ndarray:
        return np.array([t.action for t in self._transitions], dtype=np.int64)

    def coverage_report(self, n_actions: int | None = None) -> dict[str, Any]:
        """Métricas rápidas de cobertura del dataset."""
        total = len(self._transitions)
        if total == 0:
            return {"total": 0, "unique_actions": 0, "coverage_pct": 0.0}
        acts = self.actions()
        unique = int(len(set(int(a) for a in acts)))
        coverage = 100.0
        if n_actions:
            coverage = (unique / n_actions) * 100.0
        return {
            "total": total,
            "unique_actions": unique,
            "coverage_pct": round(coverage, 2),
            "mean_reward": round(float(np.mean([t.reward for t in self._transitions])), 4),
            "std_reward": round(float(np.std([t.reward for t in self._transitions])), 4),
        }


# ---------------------------------------------------------------------------
# Modelo BC (mínimo viable, torch)
# ---------------------------------------------------------------------------
if _TORCH_AVAILABLE:
    class BCNet(nn.Module):  # type: ignore[misc]
        """Red neuronal simple para Behavioral Cloning.

        Estrategia de *feature whitening* (estandarización) incluida.
        """

        def __init__(
            self,
            input_dim: int,
            n_actions: int,
            hidden_dims: tuple[int, ...] = (128, 128),
        ) -> None:
            super().__init__()
            layers: list[nn.Module] = []
            prev = input_dim
            for h in hidden_dims:
                layers.append(nn.Linear(prev, h))
                layers.append(nn.ReLU())
                prev = h
            layers.append(nn.Linear(prev, n_actions))
            self.net = nn.Sequential(*layers)
            self.register_buffer("mean", torch.zeros(input_dim))
            self.register_buffer("std", torch.ones(input_dim))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = (x - self.mean) / (self.std + 1e-6)
            return self.net(x)

        def set_stats(self, states: np.ndarray) -> None:
            """Calcula mean/std del dataset para normalización."""
            self.mean = torch.from_numpy(states.mean(axis=0)).float()
            self.std = torch.from_numpy(states.std(axis=0)).float()
else:
    class BCNet:  # type: ignore[no-redef]
        """Stub cuando PyTorch no está instalado."""
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyTorch no está disponible; instálalo para usar BCNet.")


# ---------------------------------------------------------------------------
# Entrenamiento BC mínimo
# ---------------------------------------------------------------------------
def train_bc(
    buffer: JSONLReplayBuffer,
    n_actions: int,
    epochs: int = 10,
    batch_size: int = 256,
    lr: float = 1e-3,
    device: str = "cpu",
    seed: int = 42,
) -> dict[str, Any]:
    """Entrena Behavioral Cloning sobre un replay buffer en memoria."""

    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch no está disponible; instálalo para entrenar BC.")

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)  # type: ignore[union-attr]

    if len(buffer) == 0:
        raise ValueError("Buffer vacío — no hay transiciones para entrenar.")

    states = buffer.states()
    actions = buffer.actions()
    input_dim = states.shape[1]

    model = BCNet(input_dim, n_actions).to(device)
    model.set_stats(states)
    model.train()

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    ce = nn.CrossEntropyLoss()

    stats: dict[str, Any] = {"epochs": {}, "final_loss": None, "accuracy": None}
    best_loss = float("inf")
    best_state = None

    for epoch in range(1, epochs + 1):
        batch = buffer.sample(batch_size)
        s = torch.from_numpy(np.array([t.state for t in batch])).float().to(device)
        a = torch.from_numpy(np.array([t.action for t in batch])).long().to(device)

        logits = model(s)
        loss = ce(logits, a)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        with torch.no_grad():
            pred = logits.argmax(dim=1)
            acc = (pred == a).float().mean().item()

        epoch_loss = loss.item()
        stats["epochs"][epoch] = {"loss": round(epoch_loss, 6), "accuracy": round(acc, 4)}
        if epoch_loss < best_loss:
            best_loss = epoch_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    stats["final_loss"] = round(epoch_loss, 6)
    stats["accuracy"] = round(acc, 4)
    stats["best_loss"] = round(best_loss, 6)

    # Restaurar mejor estado
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    stats["model"] = model
    return stats


# ---------------------------------------------------------------------------
# Guardar / Cargar
# ---------------------------------------------------------------------------
def save_model(model, path: Path) -> None:
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch no está disponible; no se puede guardar el modelo.")
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "arch": type(model).__name__}, path)


def load_model(path: Path, input_dim: int, n_actions: int):
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch no está disponible; no se puede cargar el modelo.")
    checkpoint = torch.load(path, map_location="cpu")  # type: ignore[union-attr]
    model = BCNet(input_dim, n_actions)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Entrena política offline (BC) desde logs JSONL.")
    p.add_argument("--logs", type=Path, required=True, help="Ruta al archivo JSONL de transiciones.")
    p.add_argument("--output", type=Path, required=True, help="Ruta para guardar el modelo (.pt).")
    p.add_argument("--n-actions", type=int, default=20, help="Número de acciones posibles.")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"])
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # 1. Cargar buffer
    buffer = JSONLReplayBuffer.from_jsonl(args.logs)
    report = buffer.coverage_report(n_actions=args.n_actions)
    print(f"📊 Dataset cargado: {report}")

    if len(buffer) == 0:
        print("❌ No hay datos. Genera transiciones con bago_rl_logger.py primero.", file=sys.stderr)
        return 1

    # 2. Entrenar
    stats = train_bc(
        buffer,
        n_actions=args.n_actions,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device=args.device,
        seed=args.seed,
    )
    print(f"✅ Entrenamiento BC finalizado — accuracy: {stats['accuracy']}, loss: {stats['final_loss']}")

    # 3. Guardar
    model = stats["model"]
    save_model(model, args.output)
    print(f"💾 Modelo guardado en {args.output}")
    return 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def _self_test() -> int:
    """Valida todo el pipeline sin dependencias de Tianshou."""
    import tempfile

    # 1. Crear dataset sintético
    tmpdir = Path(tempfile.mkdtemp(prefix="bago_offline_test_"))
    jsonl_path = tmpdir / "fake_transitions.jsonl"
    rng = np.random.default_rng(42)
    n_actions = 5
    state_dim = 8

    lines = []
    for _ in range(200):
        state = rng.random(state_dim).tolist()
        action = int(rng.integers(0, n_actions))
        reward = float(rng.random() * 2 - 1)
        next_state = rng.random(state_dim).tolist()
        done = bool(rng.random() > 0.9)
        lines.append(
            json.dumps({
                "state": state,
                "action": action,
                "reward": reward,
                "next_state": next_state,
                "done": done,
            })
        )
    jsonl_path.write_text("\n".join(lines), encoding="utf-8")

    # 2. Cargar buffer
    buf = JSONLReplayBuffer.from_jsonl(jsonl_path, max_size=500)
    assert len(buf) == 200, f"Esperado 200, obtenido {len(buf)}"
    report = buf.coverage_report(n_actions=n_actions)
    assert report["total"] == 200
    assert report["coverage_pct"] > 0
    print(f"   Buffer OK — {report}")

    # 3. Sample / stats
    batch = buf.sample(64)
    assert len(batch) == 64
    print(f"   Sample OK — batch de {len(batch)}")

    # 4. BC training (si torch existe)
    if _TORCH_AVAILABLE:
        stats = train_bc(buf, n_actions=n_actions, epochs=5, batch_size=32, seed=42)
        assert stats["accuracy"] > 0.0
        print(f"   BC train OK — accuracy={stats['accuracy']}, loss={stats['final_loss']}")

        model_path = tmpdir / "bc.pt"
        save_model(stats["model"], model_path)
        loaded = load_model(model_path, state_dim, n_actions)
        assert loaded is not None
        print(f"   Save/Load OK")
    else:
        print("   ⚠️  PyTorch no disponible — salteando BC train.")

    # 5. Limpieza
    for f in tmpdir.iterdir():
        f.unlink()
    tmpdir.rmdir()
    print("   Cleanup OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.exit(_self_test())
    sys.exit(main())

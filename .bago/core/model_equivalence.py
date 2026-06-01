#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
model_equivalence.py — BAGO 4.1.5 Model Equivalence Map

Define equivalencias entre modelos para decidir si el contexto es
transferible sin pérdida al cambiar de provider.

Un modelo "equivalente" es aquel con capacidad cognitiva comparable:
- Context window similar (±25%)
- Capacidad de razonamiento similar (según benchmarks)
- Capacidad de código similar

Clases de equivalencia:
  TIER_1: Frontier — razonamiento profundo, edición multi-file
  TIER_2: Everyday — código, resúmenes, tareas generales
  TIER_3: Fast — confirmaciones, clasificación, tareas ligeras
  TIER_4: Local ultra-light — edge, offline básico

Uso:
    from model_equivalence import EquivalenceMap
    eq = EquivalenceMap.load()
    eq.can_transfer("gpt-5.4", "claude-sonnet-4.6")  # True (mismo tier)
    eq.can_transfer("gpt-5.4", "llama3.2:1b")       # False (tiers distintos)
    eq.find_equivalents("gpt-5.4")                    # ["claude-sonnet-4.6", "gpt-5.4-mini", ...]
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from enum import Enum, auto

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass(frozen=True)
class ModelSpec:
    """Especificación de un modelo para equivalencia."""
    model_id: str
    wire_name: str
    provider: str
    tier: str
    context_tokens: int
    reasoning: str  # low | medium | high | xhigh
    coding: str     # low | medium | high | xhigh
    best_for: str
    aliases: tuple[str, ...] = ()


class TransferVerdict(Enum):
    EQUIVALENT = auto()
    DOWNGRADE = auto()
    UPGRADE = auto()
    NOT_RECOMMENDED = auto()


class TransferStrategy(Enum):
    DIRECT = auto()
    COMPRESS = auto()
    REHYDRATE = auto()
    RESET = auto()

    @classmethod
    def recommended(cls, verdict: TransferVerdict) -> "TransferStrategy":
        if verdict == TransferVerdict.EQUIVALENT:
            return cls.DIRECT
        elif verdict == TransferVerdict.DOWNGRADE:
            return cls.COMPRESS
        elif verdict == TransferVerdict.UPGRADE:
            return cls.REHYDRATE
        else:
            return cls.RESET


# ── Equivalence Map Hardcoded (puede sobreescribirse con JSON) ───────────────

_DEFAULT_MAP: dict[str, dict] = {
    "tier_1_frontier": {
        "description": "Modelos frontier: razonamiento profundo, contexto largo, edición compleja",
        "models": {
            "gpt-5.5": {"wire": "gpt-5.5", "provider": "copilot", "context": 128000, "reasoning": "xhigh", "coding": "xhigh", "best_for": "frontier"},
            "claude-opus-4.7": {"wire": "claude-opus-4.7", "provider": "copilot", "context": 200000, "reasoning": "xhigh", "coding": "xhigh", "best_for": "complex_reasoning"},
            "gpt-5.4": {"wire": "gpt-5.4", "provider": "copilot", "context": 128000, "reasoning": "high", "coding": "high", "best_for": "everyday"},
            "claude-sonnet-4.6": {"wire": "claude-sonnet-4.6", "provider": "copilot", "context": 200000, "reasoning": "high", "coding": "high", "best_for": "code_review"},
            "kimi-k2-1t": {"wire": "kimi-k2:1t", "provider": "ollama-cloud", "context": 1000000, "reasoning": "high", "coding": "high", "best_for": "long_context"},
            "deepseek-v3-671b": {"wire": "deepseek-v3.1:671b", "provider": "ollama-cloud", "context": 64000, "reasoning": "xhigh", "coding": "xhigh", "best_for": "reasoning"},
        }
    },
    "tier_2_everyday": {
        "description": "Modelos everyday: código, resúmenes, tareas generales",
        "models": {
            "gpt-5.4-mini": {"wire": "gpt-5.4-mini", "provider": "copilot", "context": 128000, "reasoning": "medium", "coding": "high", "best_for": "fast_coding"},
            "gpt-5.3-codex": {"wire": "gpt-5.3-codex", "provider": "copilot", "context": 128000, "reasoning": "medium", "coding": "xhigh", "best_for": "coding"},
            "gpt-5.2": {"wire": "gpt-5.2", "provider": "copilot", "context": 128000, "reasoning": "medium", "coding": "medium", "best_for": "long_agents"},
            "qwen25-coder": {"wire": "qwen2.5-coder:7b", "provider": "ollama-local", "context": 32768, "reasoning": "medium", "coding": "high", "best_for": "code_python"},
            "llama32": {"wire": "llama3.2:3b", "provider": "ollama-local", "context": 128000, "reasoning": "medium", "coding": "medium", "best_for": "general"},
            "devstral-2": {"wire": "devstral-2:123b", "provider": "ollama-cloud", "context": 128000, "reasoning": "high", "coding": "xhigh", "best_for": "code"},
            "qwen3-coder-480b": {"wire": "qwen3-coder:480b", "provider": "ollama-cloud", "context": 256000, "reasoning": "high", "coding": "xhigh", "best_for": "code"},
        }
    },
    "tier_3_fast": {
        "description": "Modelos rápidos: confirmaciones, clasificación, tareas ligeras",
        "models": {
            "llama32-1b": {"wire": "llama3.2:1b", "provider": "ollama-local", "context": 128000, "reasoning": "low", "coding": "low", "best_for": "classification"},
            "qwen25-mini": {"wire": "qwen2.5:0.5b", "provider": "ollama-local", "context": 32000, "reasoning": "low", "coding": "low", "best_for": "fast_confirmations"},
            "qwen25-1_5b": {"wire": "qwen2.5:1.5b", "provider": "ollama-local", "context": 32000, "reasoning": "low", "coding": "low", "best_for": "fast_confirmations"},
            "granite32-8b": {"wire": "granite3.2:8b", "provider": "ollama-local", "context": 128000, "reasoning": "medium", "coding": "medium", "best_for": "general"},
        }
    },
    "tier_4_ultra_light": {
        "description": "Modelos ultra-ligeros: edge, offline básico",
        "models": {
            "qwen25-mini": {"wire": "qwen2.5:0.5b", "provider": "ollama-local", "context": 32000, "reasoning": "low", "coding": "low", "best_for": "fast_confirmations"},
            "smollm2": {"wire": "smollm2:1.7b", "provider": "ollama-local", "context": 32000, "reasoning": "low", "coding": "low", "best_for": "edge"},
        }
    }
}


class EquivalenceMap:
    """Mapa de equivalencia de modelos."""

    def __init__(self, data: dict | None = None):
        self._data = data or self._build_default()
        self._model_to_tier: dict[str, str] = {}
        self._model_to_spec: dict[str, ModelSpec] = {}
        self._index()

    def _build_default(self) -> dict:
        return _DEFAULT_MAP

    def _index(self) -> None:
        for tier_name, tier_data in self._data.items():
            for model_id, info in tier_data.get("models", {}).items():
                self._model_to_tier[model_id] = tier_name
                self._model_to_spec[model_id] = ModelSpec(
                    model_id=model_id,
                    wire_name=info["wire"],
                    provider=info["provider"],
                    tier=tier_name,
                    context_tokens=info["context"],
                    reasoning=info["reasoning"],
                    coding=info["coding"],
                    best_for=info["best_for"],
                )

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_tier(self, model_id: str) -> str | None:
        return self._model_to_tier.get(model_id)

    def get_spec(self, model_id: str) -> ModelSpec | None:
        return self._model_to_spec.get(model_id)

    def transfer_verdict(self, from_model: str, to_model: str) -> TransferVerdict:
        """Devuelve veredicto de transferencia entre dos modelos."""
        from_tier = self.get_tier(from_model)
        to_tier = self.get_tier(to_model)
        if not from_tier or not to_tier:
            return TransferVerdict.NOT_RECOMMENDED
        if from_tier == to_tier:
            return TransferVerdict.EQUIVALENT
        tier_order = ["tier_4_ultra_light", "tier_3_fast", "tier_2_everyday", "tier_1_frontier"]
        try:
            from_idx = tier_order.index(from_tier)
            to_idx = tier_order.index(to_tier)
        except ValueError:
            return TransferVerdict.NOT_RECOMMENDED
        if from_idx > to_idx:
            return TransferVerdict.DOWNGRADE
        else:
            return TransferVerdict.UPGRADE

    def can_transfer(self, from_model: str, to_model: str, *, strict: bool = False) -> bool:
        """
        Decide si el contexto es transferible de from_model a to_model.

        strict=False: permite transferir dentro del mismo tier o de tier superior a inferior.
        strict=True: solo si son el mismo tier.
        """
        from_tier = self.get_tier(from_model)
        to_tier = self.get_tier(to_model)
        if not from_tier or not to_tier:
            return False
        if from_tier == to_tier:
            return True
        if strict:
            return False
        # Allow downgrade (frontier -> everyday -> fast) but not upgrade
        tier_order = ["tier_4_ultra_light", "tier_3_fast", "tier_2_everyday", "tier_1_frontier"]
        try:
            return tier_order.index(from_tier) >= tier_order.index(to_tier)
        except ValueError:
            return False

    def find_equivalents(self, model_id: str, *, same_provider: bool = False) -> list[str]:
        """Devuelve modelos equivalentes (mismo tier)."""
        tier = self.get_tier(model_id)
        if not tier:
            return []
        results = []
        spec = self.get_spec(model_id)
        for mid, mspec in self._model_to_spec.items():
            if mid == model_id:
                continue
            if mspec.tier == tier:
                if same_provider and spec and mspec.provider != spec.provider:
                    continue
                results.append(mid)
        return results

    def find_upgrades(self, model_id: str) -> list[str]:
        """Devuelve modelos de tier superior."""
        tier = self.get_tier(model_id)
        if not tier:
            return []
        tier_order = ["tier_4_ultra_light", "tier_3_fast", "tier_2_everyday", "tier_1_frontier"]
        try:
            my_idx = tier_order.index(tier)
        except ValueError:
            return []
        results = []
        for mid, mspec in self._model_to_spec.items():
            if mspec.tier == tier:
                continue
            try:
                t_idx = tier_order.index(mspec.tier)
            except ValueError:
                continue
            if t_idx > my_idx:
                results.append(mid)
        return results

    def suggest_for_task(self, task_description: str, available_models: list[str]) -> str | None:
        """Sugiere el mejor modelo de la lista disponible para una tarea."""
        td = task_description.lower()
        # Simple keyword heuristics
        if any(k in td for k in ("debug", "traceback", "error", "bug", "arregla", "fix")):
            # coding tasks
            candidates = [m for m in available_models if self.get_spec(m) and self.get_spec(m).coding in ("high", "xhigh")]
        elif any(k in td for k in ("resume", "summarize", "explica", "explain", "resumen")):
            candidates = [m for m in available_models if self.get_spec(m) and self.get_spec(m).reasoning in ("medium", "high", "xhigh")]
        elif any(k in td for k in ("audit", "security", "seguridad", "review", "code review")):
            candidates = [m for m in available_models if self.get_spec(m) and self.get_spec(m).reasoning in ("high", "xhigh")]
        else:
            candidates = available_models

        if not candidates:
            return None
        # Prefer higher tier
        tier_scores = {"tier_1_frontier": 4, "tier_2_everyday": 3, "tier_3_fast": 2, "tier_4_ultra_light": 1}
        scored = [(m, tier_scores.get(self.get_tier(m) or "", 0)) for m in candidates]
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[0][0] if scored else None

    def get_all_models(self) -> list[str]:
        return list(self._model_to_spec.keys())

    def get_providers_for_model(self, model_id: str) -> list[str]:
        spec = self.get_spec(model_id)
        return [spec.provider] if spec else []

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> EquivalenceMap:
        if path and path.exists():
            return cls(json.loads(path.read_text(encoding="utf-8")))
        return cls()

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def describe_transfer(self, from_model: str, to_model: str) -> dict:
        """Devuelve un dict descriptivo sobre la transferencia propuesta."""
        from_spec = self.get_spec(from_model)
        to_spec = self.get_spec(to_model)
        transferable = self.can_transfer(from_model, to_model)
        return {
            "from": from_model,
            "to": to_model,
            "transferable": transferable,
            "from_tier": self.get_tier(from_model),
            "to_tier": self.get_tier(to_model),
            "context_delta": (to_spec.context_tokens - from_spec.context_tokens) if from_spec and to_spec else None,
            "risk": "none" if transferable else "context_loss",
            "recommendation": "safe" if transferable else "compress_context",
        }


def _run_tests() -> int:
    eq = EquivalenceMap()
    assert eq.get_tier("gpt-5.4") == "tier_1_frontier"
    assert eq.get_tier("qwen25-coder") == "tier_2_everyday"
    assert eq.can_transfer("gpt-5.4", "claude-sonnet-4.6")
    assert eq.can_transfer("gpt-5.4", "qwen25-coder", strict=False)
    assert not eq.can_transfer("gpt-5.4", "qwen25-coder", strict=True)
    assert not eq.can_transfer("qwen25-mini", "gpt-5.4")
    assert "llama32" in eq.find_equivalents("qwen25-coder")
    assert eq.suggest_for_task("debug this python", ["gpt-5.4", "qwen25-mini", "llama32"]) == "gpt-5.4"
    print("model_equivalence.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

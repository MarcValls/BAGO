"""Versioned, provenance-aware model routing policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from bago_core.providers.contracts import ModelIdentity, ObservedCapabilities, RoutingPolicy


DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "contracts" / "model_routing_policy.v1.json"


@dataclass(frozen=True)
class ModelSpec:
    identity: ModelIdentity
    capabilities: ObservedCapabilities
    policy: RoutingPolicy
    best_for: str
    aliases: tuple[str, ...] = ()

    @property
    def model_id(self) -> str:
        return self.identity.model_id

    @property
    def wire_name(self) -> str:
        return self.identity.wire_name

    @property
    def provider(self) -> str:
        return self.identity.provider

    @property
    def tier(self) -> str | None:
        return self.policy.tier

    @property
    def context_tokens(self) -> int | None:
        return self.capabilities.context_tokens

    @property
    def reasoning(self) -> str | None:
        return self.policy.reasoning

    @property
    def coding(self) -> str | None:
        return self.policy.coding


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
        return {
            TransferVerdict.EQUIVALENT: cls.DIRECT,
            TransferVerdict.DOWNGRADE: cls.COMPRESS,
            TransferVerdict.UPGRADE: cls.REHYDRATE,
        }.get(verdict, cls.RESET)


class EquivalenceMap:
    """Compatibility API backed by an explicit routing policy."""

    def __init__(self, data: dict | None = None):
        raw = data if data is not None else self._read_policy(DEFAULT_POLICY_PATH)
        if raw.get("contract") != "bago.model-routing-policy.v1":
            raise ValueError("Contrato de routing no soportado")
        self._data = raw
        self.policy_version = str(self._data.get("version", "unknown"))
        self.policy_source = str(self._data.get("source", "legacy-inline"))
        self.tier_order = list(self._data.get("tier_order") or [
            "tier_4_ultra_light", "tier_3_fast", "tier_2_everyday", "tier_1_frontier"
        ])
        self._specs: dict[tuple[str, str], ModelSpec] = {}
        self._by_model: dict[str, list[ModelSpec]] = {}
        self._index()

    @staticmethod
    def _read_policy(path: Path) -> dict:
        if not path.is_file():
            return {"contract": "bago.model-routing-policy.v1", "version": "missing", "tiers": {}}
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("contract") != "bago.model-routing-policy.v1":
            raise ValueError("Contrato de routing no soportado")
        return data

    def _index(self) -> None:
        tiers = self._data.get("tiers")
        if not isinstance(tiers, dict):
            tiers = self._data
        for tier, tier_data in tiers.items():
            raw_models = tier_data.get("models", []) if isinstance(tier_data, dict) else []
            items = raw_models.items() if isinstance(raw_models, dict) else ((item.get("model_id"), item) for item in raw_models)
            for model_id, raw in items:
                if not model_id or not isinstance(raw, dict):
                    continue
                provider = str(raw.get("provider") or "")
                if not provider:
                    continue
                spec = ModelSpec(
                    identity=ModelIdentity(provider, str(model_id), str(raw.get("wire_name") or raw.get("wire") or model_id)),
                    capabilities=ObservedCapabilities(
                        context_tokens=raw.get("context_tokens", raw.get("context")),
                        best_for=raw.get("best_for"),
                        available=False,
                        source=self.policy_source,
                    ),
                    policy=RoutingPolicy(
                        tier=tier,
                        reasoning=raw.get("reasoning"),
                        coding=raw.get("coding"),
                        source=self.policy_source,
                        version=self.policy_version,
                    ),
                    best_for=str(raw.get("best_for") or ""),
                    aliases=tuple(raw.get("aliases") or ()),
                )
                self._specs[spec.identity.key] = spec
                self._by_model.setdefault(spec.model_id, []).append(spec)

    def get_spec(self, model_id: str, provider: str | None = None) -> ModelSpec | None:
        if provider is not None:
            return self._specs.get((provider, model_id))
        matches = self._by_model.get(model_id, [])
        return sorted(matches, key=lambda item: item.provider)[0] if matches else None

    def get_tier(self, model_id: str, provider: str | None = None) -> str | None:
        spec = self.get_spec(model_id, provider)
        return spec.tier if spec else None

    def tier_distance(self, left: str, right: str) -> int | None:
        try:
            return abs(self.tier_order.index(left) - self.tier_order.index(right))
        except ValueError:
            return None

    def transfer_verdict(self, from_model: str, to_model: str) -> TransferVerdict:
        source = self.get_tier(from_model)
        target = self.get_tier(to_model)
        if not source or not target:
            return TransferVerdict.NOT_RECOMMENDED
        if source == target:
            return TransferVerdict.EQUIVALENT
        try:
            return TransferVerdict.DOWNGRADE if self.tier_order.index(source) > self.tier_order.index(target) else TransferVerdict.UPGRADE
        except ValueError:
            return TransferVerdict.NOT_RECOMMENDED

    def can_transfer(self, from_model: str, to_model: str, *, strict: bool = False) -> bool:
        verdict = self.transfer_verdict(from_model, to_model)
        return verdict is TransferVerdict.EQUIVALENT or (not strict and verdict is TransferVerdict.DOWNGRADE)

    def find_equivalents(self, model_id: str, *, same_provider: bool = False) -> list[str]:
        spec = self.get_spec(model_id)
        if not spec:
            return []
        return sorted({item.model_id for item in self._specs.values() if item.model_id != model_id and item.tier == spec.tier and (not same_provider or item.provider == spec.provider)})

    def find_upgrades(self, model_id: str) -> list[str]:
        tier = self.get_tier(model_id)
        if not tier:
            return []
        try:
            current = self.tier_order.index(tier)
        except ValueError:
            return []
        return sorted({spec.model_id for spec in self._specs.values() if spec.tier in self.tier_order and self.tier_order.index(spec.tier) > current})

    def suggest_for_task(self, task_description: str, available_models: list[str]) -> str | None:
        text = task_description.lower()
        specs = [(model, self.get_spec(model)) for model in available_models]
        if any(word in text for word in ("debug", "error", "bug", "arregla", "fix")):
            candidates = [(model, spec) for model, spec in specs if spec and spec.coding in {"high", "xhigh"}]
        elif any(word in text for word in ("audit", "security", "seguridad", "review")):
            candidates = [(model, spec) for model, spec in specs if spec and spec.reasoning in {"high", "xhigh"}]
        else:
            candidates = [(model, spec) for model, spec in specs if spec]
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-(self.tier_order.index(item[1].tier) if item[1].tier in self.tier_order else -1), item[0]))
        return candidates[0][0]

    def get_all_models(self) -> list[str]:
        return sorted(self._by_model)

    def get_providers_for_model(self, model_id: str) -> list[str]:
        return sorted(spec.provider for spec in self._by_model.get(model_id, []))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> "EquivalenceMap":
        return cls(cls._read_policy(path) if path else None)

    def describe_transfer(self, from_model: str, to_model: str) -> dict:
        source = self.get_spec(from_model)
        target = self.get_spec(to_model)
        transferable = self.can_transfer(from_model, to_model)
        context_delta = None
        if source and target and source.context_tokens is not None and target.context_tokens is not None:
            context_delta = target.context_tokens - source.context_tokens
        return {
            "from": from_model,
            "to": to_model,
            "transferable": transferable,
            "from_tier": source.tier if source else None,
            "to_tier": target.tier if target else None,
            "context_delta": context_delta,
            "risk": "none" if transferable else "context_loss",
            "recommendation": "safe" if transferable else "compress_context",
            "policy_source": self.policy_source,
            "policy_version": self.policy_version,
            "capability_source": source.capabilities.source if source else "unknown",
        }

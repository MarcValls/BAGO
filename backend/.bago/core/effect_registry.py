"""Canonical effect registry for BAGO execution governance.

The registry normalizes *what kind of effect* an operation can cause before
authorization is evaluated. It does not grant authority by itself.

Source of truth:
    backend/.bago/contracts/bago.effect-registry.v1.json
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "bago.effect-registry.v1.json"
EXPECTED_CONTRACT = "bago.effect-registry.v1"
RISK_LEVELS = ("E0", "E1", "E2", "E3", "E4", "E5", "E6")
AUTHORIZATION_MODES = frozenset({"policy", "explicit", "strong", "inherit_max_child"})


class EffectRegistryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EffectDescriptor:
    id: str
    family: str
    risk_level: str
    mutates: bool
    external: bool
    destructive: bool
    authorization_mode: str
    delegable: bool
    supports_dry_run: bool
    receipt_required: bool
    default_scope: str

    @property
    def risk_rank(self) -> int:
        return RISK_LEVELS.index(self.risk_level)

    @property
    def requires_explicit_authorization(self) -> bool:
        return self.authorization_mode in {"explicit", "strong", "inherit_max_child"}

    @property
    def requires_strong_human_proof(self) -> bool:
        return self.authorization_mode == "strong"


@dataclass(frozen=True, slots=True)
class EffectRegistry:
    contract: str
    version: str
    status: str
    effects: tuple[EffectDescriptor, ...]
    digest: str

    def get(self, effect_id: str) -> EffectDescriptor:
        target = str(effect_id or "").strip()
        for effect in self.effects:
            if effect.id == target:
                return effect
        raise EffectRegistryError(f"Unknown effect_id: {target}")

    def contains(self, effect_id: str) -> bool:
        target = str(effect_id or "").strip()
        return any(effect.id == target for effect in self.effects)

    def strongest(self, effect_ids: Iterable[str]) -> EffectDescriptor:
        items = [self.get(effect_id) for effect_id in effect_ids]
        if not items:
            raise EffectRegistryError("Cannot resolve strongest effect from an empty set")
        return max(items, key=lambda effect: effect.risk_rank)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "version": self.version,
            "status": self.status,
            "digest": self.digest,
            "effects": [
                {
                    "id": effect.id,
                    "family": effect.family,
                    "risk_level": effect.risk_level,
                    "mutates": effect.mutates,
                    "external": effect.external,
                    "destructive": effect.destructive,
                    "authorization_mode": effect.authorization_mode,
                    "delegable": effect.delegable,
                    "supports_dry_run": effect.supports_dry_run,
                    "receipt_required": effect.receipt_required,
                    "default_scope": effect.default_scope,
                }
                for effect in self.effects
            ],
        }


def _stable_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_bool(raw: dict[str, Any], key: str, effect_id: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise EffectRegistryError(f"{effect_id}.{key} must be bool")
    return value


def _parse_effect(raw: Any) -> EffectDescriptor:
    if not isinstance(raw, dict):
        raise EffectRegistryError("Each effect entry must be an object")
    effect_id = str(raw.get("id") or "").strip()
    family = str(raw.get("family") or "").strip()
    risk_level = str(raw.get("risk_level") or "").strip()
    authorization_mode = str(raw.get("authorization_mode") or "").strip()
    default_scope = str(raw.get("default_scope") or "").strip()

    if not effect_id or "." not in effect_id:
        raise EffectRegistryError(f"Invalid effect id: {effect_id!r}")
    if not family:
        raise EffectRegistryError(f"{effect_id}.family is required")
    if risk_level not in RISK_LEVELS:
        raise EffectRegistryError(f"{effect_id}.risk_level must be one of {RISK_LEVELS}")
    if authorization_mode not in AUTHORIZATION_MODES:
        raise EffectRegistryError(
            f"{effect_id}.authorization_mode must be one of {sorted(AUTHORIZATION_MODES)}"
        )
    if not default_scope:
        raise EffectRegistryError(f"{effect_id}.default_scope is required")

    destructive = _require_bool(raw, "destructive", effect_id)
    mutates = _require_bool(raw, "mutates", effect_id)
    external = _require_bool(raw, "external", effect_id)
    delegable = _require_bool(raw, "delegable", effect_id)
    supports_dry_run = _require_bool(raw, "supports_dry_run", effect_id)
    receipt_required = _require_bool(raw, "receipt_required", effect_id)

    if destructive and not mutates:
        raise EffectRegistryError(f"{effect_id}: destructive effect must mutate")
    if authorization_mode == "strong" and risk_level not in {"E5", "E6"}:
        raise EffectRegistryError(f"{effect_id}: strong authorization is reserved for E5/E6")
    if risk_level == "E6" and family != "delegation":
        raise EffectRegistryError(f"{effect_id}: E6 is reserved for persistent delegation")

    return EffectDescriptor(
        id=effect_id,
        family=family,
        risk_level=risk_level,
        mutates=mutates,
        external=external,
        destructive=destructive,
        authorization_mode=authorization_mode,
        delegable=delegable,
        supports_dry_run=supports_dry_run,
        receipt_required=receipt_required,
        default_scope=default_scope,
    )


def load_effect_registry(path: Path | str | None = None) -> EffectRegistry:
    source = Path(path).resolve() if path else CONTRACT_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EffectRegistryError(f"Cannot load effect registry: {exc}") from exc

    if not isinstance(payload, dict):
        raise EffectRegistryError("Effect registry root must be an object")
    if payload.get("contract") != EXPECTED_CONTRACT:
        raise EffectRegistryError(
            f"Unexpected contract: {payload.get('contract')!r}; expected {EXPECTED_CONTRACT!r}"
        )
    effects_raw = payload.get("effects")
    if not isinstance(effects_raw, list) or not effects_raw:
        raise EffectRegistryError("Effect registry must contain a non-empty effects list")

    effects = tuple(_parse_effect(item) for item in effects_raw)
    ids = [effect.id for effect in effects]
    duplicates = sorted({effect_id for effect_id in ids if ids.count(effect_id) > 1})
    if duplicates:
        raise EffectRegistryError(f"Duplicate effect ids: {duplicates}")

    return EffectRegistry(
        contract=EXPECTED_CONTRACT,
        version=str(payload.get("version") or ""),
        status=str(payload.get("status") or ""),
        effects=effects,
        digest=_stable_digest(payload),
    )


REGISTRY = load_effect_registry()


def get_effect(effect_id: str) -> EffectDescriptor:
    return REGISTRY.get(effect_id)


def strongest_effect(effect_ids: Iterable[str]) -> EffectDescriptor:
    return REGISTRY.strongest(effect_ids)


__all__ = [
    "AUTHORIZATION_MODES",
    "CONTRACT_PATH",
    "EffectDescriptor",
    "EffectRegistry",
    "EffectRegistryError",
    "REGISTRY",
    "RISK_LEVELS",
    "get_effect",
    "load_effect_registry",
    "strongest_effect",
]

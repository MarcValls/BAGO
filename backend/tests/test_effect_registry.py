from __future__ import annotations

import json

import pytest

import effect_registry


def test_effect_registry_loads_canonical_contract() -> None:
    registry = effect_registry.load_effect_registry()
    assert registry.contract == "bago.effect-registry.v1"
    assert registry.version == "1.23.0"
    assert registry.status == "active"
    assert len(registry.effects) >= 20
    assert len(registry.digest) == 64


def test_effect_ids_are_unique_and_risk_levels_are_valid() -> None:
    registry = effect_registry.REGISTRY
    ids = [effect.id for effect in registry.effects]
    assert len(ids) == len(set(ids))
    assert all(effect.risk_level in effect_registry.RISK_LEVELS for effect in registry.effects)


def test_strong_human_effects_are_reserved_for_e5_e6() -> None:
    registry = effect_registry.REGISTRY
    strong = [effect for effect in registry.effects if effect.requires_strong_human_proof]
    assert strong
    assert {effect.risk_level for effect in strong} <= {"E5", "E6"}
    assert registry.get("filesystem.delete").requires_strong_human_proof is True
    assert registry.get("system.update.apply").requires_strong_human_proof is True
    assert registry.get("system.install.apply").requires_strong_human_proof is True
    assert registry.get("system.install.apply").destructive is True
    assert registry.get("system.install.rollback").requires_strong_human_proof is True
    assert registry.get("system.install.rollback").destructive is True
    assert registry.get("schedule.delegate").risk_level == "E6"


def test_compound_effect_inherits_strongest_child_risk() -> None:
    strongest = effect_registry.strongest_effect(
        ["filesystem.read", "filesystem.write", "system.update.apply"]
    )
    assert strongest.id == "system.update.apply"


def test_registry_rejects_duplicate_effect_ids(tmp_path) -> None:
    source = json.loads(effect_registry.CONTRACT_PATH.read_text(encoding="utf-8"))
    source["effects"].append(dict(source["effects"][0]))
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(effect_registry.EffectRegistryError, match="Duplicate effect ids"):
        effect_registry.load_effect_registry(path)

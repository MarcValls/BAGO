"""Direct contract tests for separated model identity, capabilities and routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bago_core.providers import ModelInfo
from bago_core.providers.contracts import CONTRACT_VERSION, ModelIdentity, ObservedCapabilities, RoutingPolicy
from bago_core.providers.routing import EquivalenceMap, TransferStrategy, TransferVerdict


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "contracts" / "model_routing_policy.v1.json"


def test_policy_file_is_versioned_and_provenance_scoped() -> None:
    data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    assert data["contract"] == "bago.model-routing-policy.v1"
    assert data["version"] == "1.0.0"
    assert data["source"] == "repository-policy"
    assert data["tier_order"]
    assert all(isinstance(models, list) and models for models in (tier["models"] for tier in data["tiers"].values()))


def test_identity_observations_and_policy_are_separate_representations() -> None:
    routing = EquivalenceMap.load(POLICY_PATH)
    spec = routing.get_spec("gpt-5.4", "copilot")

    assert spec is not None
    assert spec.identity == ModelIdentity(provider="copilot", model_id="gpt-5.4", wire_name="gpt-5.4")
    assert spec.identity.key == ("copilot", "gpt-5.4")
    assert spec.capabilities.context_tokens == 128000
    assert spec.capabilities.source == "repository-policy"
    assert spec.capabilities.available is False
    assert spec.policy == RoutingPolicy(
        tier="tier_1_frontier",
        reasoning="high",
        coding="high",
        source="repository-policy",
        version="1.0.0",
    )


def test_unknown_models_receive_no_fabricated_capabilities_or_policy() -> None:
    routing = EquivalenceMap.load(POLICY_PATH)

    assert routing.get_spec("unknown-model") is None
    assert routing.get_tier("unknown-model") is None
    assert routing.find_equivalents("unknown-model") == []
    assert routing.find_upgrades("unknown-model") == []
    assert routing.suggest_for_task("debug this", ["unknown-model"]) is None
    assert routing.transfer_verdict("gpt-5.4", "unknown-model") is TransferVerdict.NOT_RECOMMENDED
    assert TransferStrategy.recommended(TransferVerdict.NOT_RECOMMENDED) is TransferStrategy.RESET

    description = routing.describe_transfer("gpt-5.4", "unknown-model")
    assert description["transferable"] is False
    assert description["to_tier"] is None
    assert description["capability_source"] == "repository-policy"


def test_missing_policy_fails_soft_without_capabilities() -> None:
    routing = EquivalenceMap.load(ROOT / "contracts" / "missing.model-routing-policy.json")

    assert routing.policy_version == "missing"
    assert routing.get_all_models() == []
    assert routing.get_spec("gpt-5.4") is None


def test_wrong_contract_is_rejected() -> None:
    with pytest.raises(ValueError, match="Contrato de routing"):
        EquivalenceMap({"contract": "other-contract", "tiers": {}})


def test_compatibility_facades_expose_the_same_versioned_slice() -> None:
    import importlib

    model_equivalence = importlib.import_module("model_equivalence")
    provider_adapter = importlib.import_module("provider_adapter")

    # The conftest path setup and module isolation can load the same source
    # file twice (once via package path, once via facade import), yielding
    # distinct class objects for the identical canonical source. Assert on
    # the durable contract: the facade re-exports the versioned module and
    # its classes carry the canonical module identity.
    assert model_equivalence.EquivalenceMap.__module__ == "bago_core.providers.routing"
    assert model_equivalence.EquivalenceMap.__name__ == "EquivalenceMap"
    assert model_equivalence.ModelSpec.__module__ == "bago_core.providers.routing"
    assert provider_adapter.ModelInfo.__module__ == "bago_core.providers.contracts"
    assert provider_adapter.ProviderAdapter.__module__ == "bago_core.providers.contracts"
    assert CONTRACT_VERSION == "bago.provider-contracts/v1"
    # Behavioral identity: facades route to the same policy file and data.
    routing = EquivalenceMap.load(POLICY_PATH)
    facade_map = model_equivalence.EquivalenceMap.load(POLICY_PATH)
    assert facade_map.policy_version == routing.policy_version
    assert facade_map.get_tier("gpt-5.4", "copilot") == routing.get_tier("gpt-5.4", "copilot")


def test_adapter_dto_exposes_separated_views_without_changing_wire_fields() -> None:
    info = ModelInfo(
        model_id="qwen25-coder",
        wire_name="qwen2.5-coder:7b",
        provider="ollama-local",
        context_tokens=32768,
        max_output_tokens=4096,
        best_for="code_python",
        cost="local",
        available=True,
        capability_source="provider-declared",
        observed_at="2026-09-04T00:00:00Z",
    )

    assert info.identity == ModelIdentity("ollama-local", "qwen25-coder", "qwen2.5-coder:7b")
    assert info.observed_capabilities == ObservedCapabilities(
        context_tokens=32768,
        max_output_tokens=4096,
        best_for="code_python",
        available=True,
        source="provider-declared",
        observed_at="2026-09-04T00:00:00Z",
    )

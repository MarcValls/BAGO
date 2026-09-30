from execution_request import ExecutionRequestError, build_execution_request
from authorization_boundary import AuthorizationBoundary
from execution_gateway import EffectAdapterRegistry
from execution_gateway import ExecutionGateway
from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from world_state_snapshot import WorldStateSnapshot, build_execution_request_with_snapshot
import pytest


class Manager:
    base_path = "C:/workspace"
    session_id = "s1"
    revision = "r1"

    def workspace_state(self):
        return {
            "project_root": self.base_path,
            "workspace_state_root": "C:/workspace/.gabo",
            "context_revision": self.revision,
        }


def _fields():
    return dict(
        effect_id="filesystem.write",
        actor_kind="user",
        principal_id="p1",
        session_id="s1",
        source_surface="test",
        target={"path": "C:/workspace/a.txt"},
        arguments={"content": "x"},
    )


def test_builder_binds_digest_to_manager_snapshot():
    request = build_execution_request_with_snapshot(Manager(), **_fields())
    assert request.world_state_digest == WorldStateSnapshot.from_request(request, Manager()).digest


def test_gateway_rejects_unspecified_material_state_before_permit():
    request = build_execution_request(**_fields())
    try:
        ExecutionGateway()._validate_world_state(request, ExecutionContext(manager=Manager()))
    except ExecutionGatewayError as exc:
        assert exc.code == "execution_world_state_required"
    else:
        raise AssertionError("unspecified material state was accepted")


def test_gateway_revalidates_snapshot_after_world_state_changes():
    manager = Manager()
    request = build_execution_request_with_snapshot(manager, **_fields())
    manager.revision = "r2"
    try:
        ExecutionGateway()._validate_world_state(request, ExecutionContext(manager=manager))
    except ExecutionGatewayError as exc:
        assert exc.code == "execution_world_state_stale"
    else:
        raise AssertionError("stale world state was accepted")


def test_gateway_revalidates_again_after_permit_consumption_before_effect(monkeypatch, tmp_path):
    monkeypatch.setattr("authorization_boundary.state_root", lambda: tmp_path)
    manager = Manager()
    request = build_execution_request(**_fields(), world_state_authority=manager)
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id="world-state-double-check")
    approved = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"], interaction_id="world-state-double-check",
        session_id=request.session_id, channel="ui-react",
    )

    class RecordingAdapter:
        effect_ids = frozenset({"filesystem.write"})

        def __init__(self):
            self.calls = 0

        def execute(self, _request, _context):
            self.calls += 1
            return {"ok": True}

    adapter = RecordingAdapter()
    registry = EffectAdapterRegistry()
    registry.register(adapter)
    consume = boundary.consume_permit

    def consume_then_change_world(*, permit_token, request):
        result = consume(permit_token=permit_token, request=request)
        manager.revision = "r-after-consume"
        return result

    monkeypatch.setattr(boundary, "consume_permit", consume_then_change_world)
    gateway = ExecutionGateway(boundary=boundary, adapters=registry)
    try:
        gateway.execute(
            permit_token=approved["permit"]["token"], request=request,
            context=ExecutionContext(manager=manager),
        )
    except ExecutionGatewayError as exc:
        assert exc.code == "execution_world_state_stale"
    else:
        raise AssertionError("world drift after Permit consumption reached the adapter")
    assert adapter.calls == 0


def test_mutating_request_rejects_caller_supplied_snapshot_payload():
    for fields in (
        {"world_state": {"revision": "caller-selected"}},
        {"world_state_digest": "0" * 64},
    ):
        try:
            build_execution_request(**_fields(), **fields)
        except ExecutionRequestError as exc:
            assert exc.code == "execution_world_state_authority_required"
        else:
            raise AssertionError("caller-supplied state was accepted for a mutating effect")


def test_mutating_request_derives_state_from_authority_only():
    request = build_execution_request(**_fields(), world_state_authority=Manager())
    assert request.world_state_digest == WorldStateSnapshot.from_request(request, Manager()).digest


def test_inventory_has_no_mutating_request_without_snapshot_authority():
    import importlib.util
    from pathlib import Path

    repo = Path(__file__).parents[2]
    scanner_path = repo / "backend/.bago/tools/world_state_snapshot_inventory.py"
    spec = importlib.util.spec_from_file_location("world_state_snapshot_inventory", scanner_path)
    assert spec and spec.loader
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    rows, unbound = scanner.scan_inventory()
    assert not unbound, "mutating request builders lack WorldStateSnapshot authority: " + ", ".join(unbound)
    assert len(rows) >= 45


def test_checked_in_snapshot_inventory_matches_current_sources_and_registry():
    import importlib.util
    from pathlib import Path

    repo = Path(__file__).parents[2]
    scanner_path = repo / "backend/.bago/tools/world_state_snapshot_inventory.py"
    spec = importlib.util.spec_from_file_location("world_state_snapshot_inventory_check", scanner_path)
    assert spec and spec.loader
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    rows, unbound = scanner.scan_inventory()
    assert scanner.OUTPUT.read_text(encoding="utf-8") == scanner.render_inventory(rows, unbound)


def test_every_registered_mutating_e5_e6_adapter_has_gateway_revalidation():
    from effect_registry import REGISTRY
    from execution_gateway import build_default_effect_adapter_registry

    adapters = build_default_effect_adapter_registry()
    strong_effects = [
        effect for effect in REGISTRY.effects
        if effect.risk_level in {"E5", "E6"} and effect.mutates
        and effect.id in adapters.registered_effects()
    ]
    assert strong_effects
    missing = [
        effect.id for effect in strong_effects
        if not callable(getattr(adapters.resolve(effect.id), "revalidate_world_state", None))
    ]
    assert not missing


def test_unadapted_strong_effects_remain_denied_by_gateway_resolution():
    from effect_registry import REGISTRY
    from execution_gateway import build_default_effect_adapter_registry

    adapters = build_default_effect_adapter_registry()
    unadapted = [
        effect for effect in REGISTRY.effects
        if effect.risk_level in {"E5", "E6"} and effect.mutates
        and effect.id not in adapters.registered_effects()
    ]
    assert {effect.id for effect in unadapted} == {
        "filesystem.delete", "github.repo.delete", "system.configuration.write",
    }
    for effect in unadapted:
        with pytest.raises(Exception, match="No EffectAdapter registered") as exc:
            adapters.resolve(effect.id)
        assert getattr(exc.value, "code", "") == "execution_adapter_missing"

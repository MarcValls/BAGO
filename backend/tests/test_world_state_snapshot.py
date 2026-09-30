from types import SimpleNamespace

import pytest

from authorization_boundary import AuthorizationBoundary
from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_gateway import EffectAdapterRegistry, ExecutionGateway
from execution_request import ExecutionRequestError, build_execution_request
from world_state_snapshot import WorldStateSnapshot, build_execution_request_with_snapshot


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
        effect_id="filesystem.write", actor_kind="user", principal_id="p1",
        session_id="s1", source_surface="test",
        target={"path": "C:/workspace/a.txt"}, arguments={"content": "x"},
    )


def test_builder_binds_digest_to_manager_snapshot():
    request = build_execution_request_with_snapshot(Manager(), **_fields())
    assert request.world_state_digest == WorldStateSnapshot.from_request(request, Manager()).digest


def test_relative_path_authority_is_canonical_across_build_and_gateway(monkeypatch, tmp_path):
    from pathlib import Path
    from execution_gateway import ExecutionGateway
    from execution_adapter_contract import ExecutionContext

    monkeypatch.chdir(tmp_path)
    fields = _fields()
    request = build_execution_request(**fields, world_state_authority=Path("."))
    ExecutionGateway._validate_world_state(
        request, ExecutionContext(world_state_authority_root=str(Path(".").resolve()))
    )


def test_gateway_rejects_unspecified_material_state_before_permit():
    request = build_execution_request(**_fields())
    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway()._validate_world_state(request, ExecutionContext(manager=Manager()))
    assert blocked.value.code == "execution_world_state_required"


def test_gateway_revalidates_snapshot_after_world_state_changes():
    manager = Manager()
    request = build_execution_request_with_snapshot(manager, **_fields())
    manager.revision = "r2"
    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway()._validate_world_state(request, ExecutionContext(manager=manager))
    assert blocked.value.code == "execution_world_state_stale"


def test_gateway_rejects_snapshot_from_different_manager_session_before_dispatch():
    request_manager = Manager()
    request = build_execution_request_with_snapshot(request_manager, **_fields())
    other_manager = Manager()
    other_manager.session_id = "session-B"

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
    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway(adapters=registry)._validate_world_state(
            request, ExecutionContext(manager=other_manager), adapter
        )
    assert blocked.value.code == "execution_world_state_authority_session_mismatch"
    assert adapter.calls == 0


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
    with pytest.raises(ExecutionGatewayError) as blocked:
        gateway.execute(
            permit_token=approved["permit"]["token"], request=request,
            context=ExecutionContext(manager=manager),
        )
    assert blocked.value.code == "execution_world_state_stale"
    assert adapter.calls == 0


def test_mutating_request_rejects_caller_supplied_snapshot_payload():
    for fields in ({"world_state": {"revision": "caller-selected"}}, {"world_state_digest": "0" * 64}):
        with pytest.raises(ExecutionRequestError) as blocked:
            build_execution_request(**_fields(), **fields)
        assert blocked.value.code == "execution_world_state_authority_required"


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
        if effect.risk_level in {"E5", "E6"} and effect.mutates and effect.id in adapters.registered_effects()
    ]
    assert strong_effects
    assert not [
        effect.id for effect in strong_effects
        if not callable(getattr(adapters.resolve(effect.id), "revalidate_world_state", None))
    ]


def test_credential_hook_blocks_secret_state_drift(monkeypatch, tmp_path):
    import secret_store as secret_store_module
    from bago_core.secrets import secret_state_digest
    from execution_adapters.credentials import CredentialWriteEffectAdapter

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    monkeypatch.setattr(secret_store_module, "_is_windows", lambda: False)
    store = secret_store_module.get_secret_store()
    path = store.path_for_key("providers/openrouter/api_key")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"before")
    target = {
        "provider": "openrouter", "key": "api_key",
        "secret_state_sha256": secret_state_digest(store, "providers/openrouter/api_key"),
    }
    request = build_execution_request(
        effect_id="credential.write", actor_kind="user", principal_id="p1", session_id="s1",
        source_surface="test", target=target, arguments={}, scope="persistent",
        world_state_authority=SimpleNamespace(session_id="s1"),
    )
    path.write_bytes(b"after")
    try:
        CredentialWriteEffectAdapter.revalidate_world_state(request, ExecutionContext(manager=SimpleNamespace(session_id="s1")))
    except Exception as blocked:
        assert getattr(blocked, "code", "") == "credential_write_secret_state_changed"
    else:
        raise AssertionError("credential drift was accepted")


def test_release_download_hook_rejects_noncanonical_cache(monkeypatch, tmp_path):
    from execution_adapters.release import ReleaseDownloadEffectAdapter

    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    monkeypatch.setattr(ReleaseDownloadEffectAdapter, "_target", classmethod(lambda cls, _filename, job_id="": (actual_root, actual_root / "bundle.zip")))
    request = build_execution_request(
        effect_id="release.download", actor_kind="server", principal_id="p1", session_id="s1",
        source_surface="test", target={"filename": "bago-v1.0.0-distribution.zip", "download_root": str(expected_root)},
        arguments={}, scope="system", world_state_authority=expected_root,
    )
    try:
        ReleaseDownloadEffectAdapter.revalidate_world_state(request, ExecutionContext(services={"_server_allowed_root": str(expected_root)}))
    except Exception as blocked:
        assert getattr(blocked, "code", "") == "release_download_world_state_stale"
    else:
        raise AssertionError("release cache drift was accepted")

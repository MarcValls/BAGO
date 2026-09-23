from __future__ import annotations

import inspect

import pytest

import authorization_boundary as auth
from execution_gateway import (
    EffectAdapterRegistry,
    ExecutionContext,
    ExecutionGateway,
    ExecutionGatewayError,
    build_default_effect_adapter_registry,
)
from execution_request import build_execution_request


class _RecordingAdapter:
    effect_ids = frozenset({"filesystem.write"})

    def __init__(self) -> None:
        self.calls = []

    def execute(self, request, context):
        self.calls.append((request, context))
        return {
            "ok": True,
            "effect_id": request.effect_id,
            "target": request.target,
            "arguments_digest": request.arguments_digest,
        }


def _request(*, value: str = "A", effect_id: str = "filesystem.write"):
    return build_execution_request(
        effect_id=effect_id,
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"path": "notes/example.txt"},
        arguments={"content": value},
    )


def _permit(boundary: auth.AuthorizationBoundary, request, interaction: str = "interaction-gw"):
    challenge = boundary.create_challenge(request, interaction_id=interaction)
    return boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id=interaction,
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]


def test_execution_request_fingerprint_is_transport_id_independent() -> None:
    a = _request()
    b = _request()
    assert a.request_id != b.request_id
    assert a.arguments_digest == b.arguments_digest
    assert a.fingerprint == b.fingerprint


def test_execution_request_detaches_mutable_caller_payload() -> None:
    arguments = {"content": {"value": "A"}}
    request = build_execution_request(
        effect_id="filesystem.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"path": "notes/example.txt"},
        arguments=arguments,
    )
    fingerprint = request.fingerprint
    arguments["content"]["value"] = "MUTATED"
    assert request.arguments["content"]["value"] == "A"
    assert request.fingerprint == fingerprint


def test_execution_request_fingerprint_changes_with_material_semantics() -> None:
    original = _request(value="A")
    changed_arguments = _request(value="B")
    changed_effect = _request(value="A", effect_id="filesystem.delete")

    assert original.fingerprint != changed_arguments.fingerprint
    assert original.fingerprint != changed_effect.fingerprint


def test_gateway_signature_has_no_caller_supplied_executor() -> None:
    parameters = inspect.signature(ExecutionGateway.execute).parameters
    assert "executor" not in parameters
    assert "request" in parameters
    assert "permit_token" in parameters


def test_gateway_dispatches_by_effect_id_after_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    request = _request()
    permit = _permit(boundary, request)

    adapter = _RecordingAdapter()
    registry = EffectAdapterRegistry()
    registry.register(adapter)
    gateway = ExecutionGateway(boundary=boundary, adapters=registry)

    result, consumed = gateway.execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(services={"test": True}),
    )

    assert result["ok"] is True
    assert result["effect_id"] == "filesystem.write"
    assert consumed["state"] == "consumed"
    assert len(adapter.calls) == 1


def test_missing_adapter_does_not_consume_valid_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    request = _request()
    permit = _permit(boundary, request, interaction="interaction-missing")

    empty = EffectAdapterRegistry()
    gateway = ExecutionGateway(boundary=boundary, adapters=empty)
    with pytest.raises(ExecutionGatewayError) as missing:
        gateway.execute(permit_token=permit["token"], request=request)
    assert missing.value.code == "execution_adapter_missing"

    adapter = _RecordingAdapter()
    empty.register(adapter)
    result, consumed = gateway.execute(permit_token=permit["token"], request=request)
    assert result["ok"] is True
    assert consumed["state"] == "consumed"


def test_registry_rejects_duplicate_effect_ownership() -> None:
    registry = EffectAdapterRegistry()
    registry.register(_RecordingAdapter())
    with pytest.raises(ExecutionGatewayError) as duplicate:
        registry.register(_RecordingAdapter())
    assert duplicate.value.code == "execution_adapter_duplicate"


def test_default_registry_owns_governed_plan_and_filesystem_adapters() -> None:
    registry = build_default_effect_adapter_registry()

    assert "filesystem.write" in registry.registered_effects()
    assert "filesystem.read" in registry.registered_effects()
    assert "plan.execute" in registry.registered_effects()
    assert "state.write" in registry.registered_effects()
    assert "config.write" in registry.registered_effects()
    assert "memory.write" in registry.registered_effects()
    assert "agent.definition.write" in registry.registered_effects()


def test_server_policy_state_write_is_materialized_by_the_gateway(tmp_path) -> None:
    from bago_core.atomic_json import write_json_atomic

    target = tmp_path / "state" / "record.json"
    write_json_atomic(target, {"ok": True, "owner": "gateway"})

    assert target.exists()
    assert '"owner": "gateway"' in target.read_text(encoding="utf-8")


def test_server_policy_state_write_blocks_root_mismatch_before_effect(tmp_path) -> None:
    request = build_execution_request(
        effect_id="state.write",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="server-state-test",
        source_surface="server.test",
        target={
            "path": str(tmp_path / "state.json"),
            "allowed_root": str(tmp_path / "other-root"),
            "operation": "replace_text",
        },
        arguments={"content": "must-not-exist"},
        scope="session",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute_server_owned(
            request=request,
            context=ExecutionContext(services={"_server_allowed_root": str(tmp_path)}),
        )

    assert blocked.value.code == "server_state_root_mismatch"
    assert not (tmp_path / "state.json").exists()


def test_server_policy_path_traversal_is_blocked_before_effect(tmp_path) -> None:
    root = tmp_path / "state"
    target = root / ".." / "outside.json"
    request = build_execution_request(
        effect_id="state.write",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="server-state-test",
        source_surface="server.test",
        target={
            "path": str(target),
            "allowed_root": str(root),
            "operation": "replace_text",
        },
        arguments={"content": "must-not-exist"},
        scope="session",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute_server_owned(
            request=request,
            context=ExecutionContext(services={"_server_allowed_root": str(root)}),
        )

    assert blocked.value.code == "server_state_path_out_of_scope"
    assert not (tmp_path / "outside.json").exists()


def test_public_gateway_cannot_consume_a_server_policy_effect(tmp_path) -> None:
    request = build_execution_request(
        effect_id="state.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"path": "state.json"},
        arguments={"content": "must-not-exist"},
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute(permit_token="unused", request=request)

    assert blocked.value.code == "execution_server_policy_only"


def test_server_policy_network_adapter_blocks_unclassified_surface(monkeypatch) -> None:
    import urllib.request

    called = False

    def _unexpected(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network effect must be blocked before urlopen")

    monkeypatch.setattr(urllib.request, "urlopen", _unexpected)
    request = build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="network-test",
        source_surface="server.network.unknown",
        target={
            "url": "https://example.invalid/blocked",
            "method": "GET",
            "network_class": "unknown",
            "timeout": 1.0,
        },
        arguments={},
        scope="external",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute_server_owned(request=request)

    assert blocked.value.code == "network_read_surface_blocked"
    assert called is False


def test_server_policy_network_adapter_returns_buffered_response(monkeypatch) -> None:
    import urllib.request

    class _Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def read(self):
            return b'{"ok":true}'

        def getcode(self):
            return 200

        def geturl(self):
            return "https://example.test/status"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: _Response())
    from bago_core.server_effects import gateway_urlopen

    with gateway_urlopen("https://example.test/status", timeout=1.0) as response:
        assert response.status == 200
        assert response.read() == b'{"ok":true}'
        assert response.headers["Content-Type"] == "application/json"


def test_filesystem_write_is_materialized_only_after_gateway_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    manager = type(
        "Manager",
        (),
        {
            "base_path": tmp_path,
            "project_root": tmp_path,
            "workspace_scope_root": tmp_path,
            "workspace_mirror_root": tmp_path,
            "session_id": "session-1",
        },
    )()
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="filesystem.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.filesystem.gateway",
        target={"path": "notes/example.txt"},
        arguments={"content": "gateway-only"},
    )
    permit = _permit(boundary, request, interaction="interaction-filesystem")

    result, authorization = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is True
    assert result["effect_id"] == "filesystem.write"
    assert result["receipt_id"].startswith("filesystem-write:sha256:")
    assert authorization["state"] == "consumed"
    assert (tmp_path / "notes" / "example.txt").read_text(encoding="utf-8") == "gateway-only"

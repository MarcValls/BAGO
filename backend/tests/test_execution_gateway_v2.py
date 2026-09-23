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

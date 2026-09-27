from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from authorization_boundary import AuthorizationBoundary
from execution_adapter_contract import ExecutionContext
from execution_adapters.repository_guard import RepositoryGuardEffectAdapter
from execution_gateway import ExecutionGateway, ExecutionGatewayError
from execution_request import build_execution_request


def _request(root: Path, *, operation: str = "write", resource: str = "config", before: bytes = b"", content: str | None = None):
    target = {
        "repository_root": str(root.resolve()),
        "resource": resource,
        "operation": operation,
        "before_sha256": hashlib.sha256(before).hexdigest() if before else "",
    }
    if content is not None:
        target["content"] = content
        target["after_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return build_execution_request(
        effect_id="repository.guard.manage",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="repository:" + hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:20],
        source_surface=f"cli.debt_guard.{resource}.{operation}",
        target=target,
        arguments={},
        scope="workspace",
    )


def _execute(request, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    boundary = AuthorizationBoundary()
    interaction_id = "cli-test-repository-guard"
    challenge = boundary.create_challenge(request, interaction_id=interaction_id)
    approval = boundary.approve_cli_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id=interaction_id,
        session_id=request.session_id,
        terminal_confirmed=True,
    )
    return ExecutionGateway(boundary).execute(
        permit_token=approval["permit"]["token"], request=request,
    )[0]


def test_authorized_config_write_is_owned_by_gateway(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    content = '{"version":"1","rules":{}}'
    receipt = _execute(_request(tmp_path, content=content), monkeypatch)

    target = tmp_path / ".bago" / "debt_guard_config.json"
    assert target.read_text(encoding="utf-8") == content
    assert receipt["effect_id"] == "repository.guard.manage"
    assert receipt["after_sha256"] == hashlib.sha256(content.encode()).hexdigest()


def test_target_drift_is_denied_before_write(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    target = tmp_path / ".bago" / "debt_guard_config.json"
    target.parent.mkdir()
    target.write_text('{"version":"old","rules":{}}', encoding="utf-8")
    request = _request(tmp_path, before=b"stale", content='{"version":"new","rules":{}}')

    with pytest.raises(ExecutionGatewayError) as error:
        _execute(request, monkeypatch)

    assert error.value.code == "repository_guard_target_drift"
    assert target.read_text(encoding="utf-8") == '{"version":"old","rules":{}}'


def test_unregistered_repository_path_is_denied(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    request = _request(tmp_path, resource="git_config", content="x")

    with pytest.raises(ExecutionGatewayError) as error:
        _execute(request, monkeypatch)

    assert error.value.code == "repository_guard_operation_invalid"
    assert not (tmp_path / ".git" / "config").exists()


def test_hook_delete_requires_bago_marker_and_consumed_authority(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    target = tmp_path / ".git" / "hooks" / "pre-commit"
    target.write_text("#!/bin/sh\necho user\n", encoding="utf-8")
    request = _request(tmp_path, operation="delete", resource="hook", before=target.read_bytes())

    with pytest.raises(ExecutionGatewayError) as error:
        _execute(request, monkeypatch)

    assert error.value.code == "repository_guard_hook_not_owned"
    assert target.exists()

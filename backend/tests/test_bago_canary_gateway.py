from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from authorization_boundary import AuthorizationBoundary
from execution_adapter_contract import ExecutionContext
from execution_adapters.canary import SecurityCanaryEffectAdapter
from execution_gateway import ExecutionGateway, ExecutionGatewayError
from execution_request import build_execution_request
import bago_canary


def _request(root: Path, operation: str, **target_fields):
    return build_execution_request(
        effect_id="security.canary.manage",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="canary:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20],
        source_surface=f"cli.security.canary.{operation}",
        target={
            "operation": operation,
            "project_root": str(root),
            "state_sha256": bago_canary._state_digest(root),
            **target_fields,
        },
        arguments={},
        scope="workspace",
    )


def _execute(request, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    boundary = AuthorizationBoundary()
    interaction_id = "cli-test-canary"
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


def test_deploy_requires_consumed_cli_permit_and_materializes_exact_plan(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    request = _request(
        root, "deploy", types=["aws_keys"], stamp="20260925_120000_000001",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    receipt = _execute(request, monkeypatch)

    assert receipt["created"] == 1
    entry = receipt["entries"][0]
    path = root / entry["path"]
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    assert bago_canary.list_tokens(root) == [entry]


def test_adapter_denies_without_consumed_authority_before_creating_state(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    request = _request(
        root, "deploy", types=["aws_keys"], stamp="20260925_120000_000004",
        created_at="2026-09-25T12:00:00+00:00",
    )

    with pytest.raises(ExecutionGatewayError) as error:
        SecurityCanaryEffectAdapter().execute(request, ExecutionContext())

    assert error.value.code == "canary_authorization_required"
    assert not (root / ".bago").exists()


def test_deploy_rejects_state_drift_before_second_materialization(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    request = _request(
        root, "deploy", types=["aws_keys"], stamp="20260925_120000_000002",
        created_at="2026-09-25T12:00:00+00:00",
    )
    state_file = bago_canary.state_file(root)
    state_file.parent.mkdir(parents=True)
    state_file.write_text('{"tokens":[]}\n', encoding="utf-8")

    with pytest.raises(ExecutionGatewayError) as error:
        _execute(request, monkeypatch)

    assert error.value.code == "canary_state_drift"
    assert not bago_canary.canary_dir(root).exists()


def test_purge_removes_only_bound_canonical_files(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    deployed = _execute(_request(
        root, "deploy", types=["aws_keys"], stamp="20260925_120000_000003",
        created_at="2026-09-25T12:00:00+00:00",
    ), monkeypatch)
    entry = deployed["entries"][0]
    path = root / entry["path"]
    request = _request(root, "purge", artifacts=[{
        "type": entry["type"], "path": entry["path"],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }])

    receipt = _execute(request, monkeypatch)

    assert receipt["removed"] == 1
    assert not path.exists()
    assert bago_canary.list_tokens(root) == []


def test_purge_rejects_noncanonical_path_without_deleting(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    request = _request(root, "purge", artifacts=[{
        "type": "aws_keys", "path": ".bago/canary/../../sentinel.txt",
        "sha256": hashlib.sha256(b"keep").hexdigest(),
    }])

    with pytest.raises(ExecutionGatewayError) as error:
        _execute(request, monkeypatch)

    assert error.value.code == "canary_path_invalid"
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_purge_rejects_file_drift_after_approval(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    deployed = _execute(_request(
        root, "deploy", types=["aws_keys"], stamp="20260925_120000_000005",
        created_at="2026-09-25T12:00:00+00:00",
    ), monkeypatch)
    entry = deployed["entries"][0]
    path = root / entry["path"]
    request = _request(root, "purge", artifacts=[{
        "type": entry["type"], "path": entry["path"],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }])
    path.write_text("changed after approval", encoding="utf-8")

    with pytest.raises(ExecutionGatewayError) as error:
        _execute(request, monkeypatch)

    assert error.value.code == "canary_target_drift"
    assert path.read_text(encoding="utf-8") == "changed after approval"


def test_cli_facade_sends_deploy_through_gateway(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    captured = []

    def execute(request, **_kwargs):
        captured.append(request)
        return _execute(request, monkeypatch), {"state": "consumed"}

    monkeypatch.setattr(bago_canary, "execute_cli_effect", execute)

    created = bago_canary.deploy(root, "aws_keys")

    assert len(created) == 1
    assert captured[0].effect_id == "security.canary.manage"
    assert captured[0].target["operation"] == "deploy"


def test_read_only_list_does_not_create_project_state(tmp_path: Path, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()

    result = bago_canary.main(["--root", str(root), "list"])

    assert result == 0
    assert "No canary tokens deployed" in capsys.readouterr().out
    assert not (root / ".bago").exists()

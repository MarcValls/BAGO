from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from authorization_boundary import AuthorizationBoundary
from execution_adapter_contract import ExecutionContext
from execution_adapters import repository_inspection
from execution_adapters.repository_inspection import RepositoryInspectionEffectAdapter
from execution_gateway import ExecutionGateway, ExecutionGatewayError
from execution_request import build_execution_request


def _request(root: Path, operation: str = "staged_files"):
    return build_execution_request(
        effect_id="repository.inspect",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="repository:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20],
        source_surface=f"cli.commit_readiness.{operation}",
        target={"operation": operation, "repository_root": str(root)},
        arguments={},
        scope="workspace",
    )


def _execute(request, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    boundary = AuthorizationBoundary()
    interaction_id = "cli-test-repository-inspection"
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


def test_gateway_runs_only_fixed_read_only_git_operation(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    observed = []
    monkeypatch.setattr(
        repository_inspection.subprocess,
        "run",
        lambda argv, **kwargs: observed.append((argv, kwargs)) or repository_inspection.subprocess.CompletedProcess(argv, 0, "src/a.py\0", ""),
    )

    receipt = _execute(_request(root), monkeypatch)

    assert receipt["stdout"] == "src/a.py\0"
    assert observed[0][0] == [
        "git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
        "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR",
        "--no-ext-diff", "--no-textconv",
    ]
    assert observed[0][1]["cwd"] == str(root)
    assert observed[0][1]["env"]["GIT_OPTIONAL_LOCKS"] == "0"


def test_adapter_denies_without_consumed_authority_before_spawn(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    monkeypatch.setattr(repository_inspection.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("spawn must not run"))

    with pytest.raises(ExecutionGatewayError) as error:
        RepositoryInspectionEffectAdapter().execute(_request(root), ExecutionContext())

    assert error.value.code == "repository_inspect_authorization_required"

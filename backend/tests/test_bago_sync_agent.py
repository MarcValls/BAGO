"""Tests unitarios del gobernador Git de BAGO.

Los tests usan repositorios temporales y nunca tocan el checkout del proyecto.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import bago_sync_agent as sync_agent  # noqa: E402


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "sync-agent@example.invalid")
    _git(root, "config", "user.name", "Sync Agent Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "base")
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    _git(root, "remote", "add", "origin", str(remote))
    _git(root, "push", "-u", "origin", "main")
    return root


def test_snapshot_reports_dirty_paths_and_remote_state(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("changed\n", encoding="utf-8")

    current = sync_agent.snapshot(root)

    assert current.branch == "main"
    assert current.dirty is True
    assert current.dirty_paths == ("README.md",)
    assert current.remote_url.endswith("remote.git")
    assert current.ahead == 0
    assert current.behind == 0


def test_plan_blocks_commit_without_explicit_scope_or_validation(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("changed\n", encoding="utf-8")
    current = sync_agent.snapshot(root)

    plan = sync_agent.build_plan(
        current,
        base="main",
        paths=(),
        commit=True,
        push=False,
        merge_pr=None,
    )

    assert plan["status"] == "BLOCKED"
    assert any("--path" in blocker for blocker in plan["blockers"])
    assert any("validadores" in blocker for blocker in plan["blockers"])


def test_plan_allows_scoped_dirty_change_with_explicit_preservation(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("changed\n", encoding="utf-8")
    (root / "notes.txt").write_text("unrelated\n", encoding="utf-8")
    current = sync_agent.snapshot(root)
    validator = sync_agent.ValidatorSpec("tests", (sys.executable, "-c", "print('ok')"))

    blocked = sync_agent.build_plan(
        current,
        base="main",
        paths=("README.md",),
        commit=True,
        push=False,
        merge_pr=None,
        validators=(validator,),
    )
    allowed = sync_agent.build_plan(
        current,
        base="main",
        paths=("README.md",),
        commit=True,
        push=False,
        merge_pr=None,
        preserve_unrelated_dirty=True,
        validators=(validator,),
    )

    assert blocked["status"] == "BLOCKED"
    assert allowed["status"] == "PREPARED"


def test_three_validators_run_without_mutating_worktree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    specs = tuple(
        sync_agent.ValidatorSpec(f"check-{index}", (sys.executable, "-c", "print('pass')"))
        for index in range(3)
    )

    results, mutated = sync_agent.run_validators(root, specs, timeout=30)

    assert mutated is False
    assert len(results) == 3
    assert all(result.passed for result in results)


def test_execute_scoped_commit_and_push_uses_temp_remote(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git(root, "checkout", "-b", "feature/sync-agent")
    (root / "README.md").write_text("feature\n", encoding="utf-8")
    args = sync_agent.build_parser().parse_args(
        [
            "execute",
            "--root",
            str(root),
            "--path",
            "README.md",
            "--message",
            "test: scoped sync",
            "--commit",
            "--push",
            "--skip-validation",
            "--json",
        ]
    )
    sync_agent._validate_arguments(args)

    code, payload = sync_agent.execute(args)

    assert code == 0
    assert payload["status"] == "EXECUTED"
    assert [item["action"] for item in payload["actions"]] == [
        "fetch",
        "external_validation",
        "stage_scoped_paths",
        "commit",
        "push",
    ]
    assert _git(root, "rev-parse", "HEAD") != _git(root, "rev-parse", "main")
    assert _git(
        tmp_path,
        "--git-dir",
        str(tmp_path / "remote.git"),
        "rev-parse",
        "refs/heads/feature/sync-agent",
    ) == _git(root, "rev-parse", "HEAD")


def test_validator_mutation_is_detected(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    code = "from pathlib import Path; Path('created-by-validator.txt').write_text('bad')"
    specs = (sync_agent.ValidatorSpec("mutating", (sys.executable, "-c", code)),)

    results, mutated = sync_agent.run_validators(root, specs, timeout=30)

    assert results[0].passed is True
    assert mutated is True


def test_receipt_does_not_store_raw_validator_command(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    secret_like = "python -c print('do-not-store-this-token')"
    spec = sync_agent.parse_validator(f"tests={secret_like}")
    receipt_path = tmp_path / "receipt.json"

    actual = sync_agent._write_receipt(
        root,
        {
            "schema": sync_agent.SCHEMA,
            "validator": sync_agent._public_validator_spec(spec),
        },
        str(receipt_path),
    )

    content = Path(actual).read_text(encoding="utf-8")
    assert secret_like not in content
    assert spec.command_sha256 in content

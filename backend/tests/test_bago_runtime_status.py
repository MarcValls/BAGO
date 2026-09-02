from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".bago" / "bin" / "bago.py"


def _module():
    spec = importlib.util.spec_from_file_location("bago_runtime_status", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_status(monkeypatch, capsys, state: dict, fingerprint: dict, verifier=None, review_verifier=None) -> str:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: state)
    monkeypatch.setattr(module, "_git_fingerprint", lambda: fingerprint)
    monkeypatch.setattr(module, "_print_file", lambda *_args: None)
    if verifier is not None:
        monkeypatch.setattr(module, "_verify_remediation_package", verifier)
    if review_verifier is not None:
        monkeypatch.setattr(module, "_verify_independent_review", review_verifier)
    assert module.cmd_status(None) == 0
    return capsys.readouterr().out


def test_verified_without_candidate_fingerprint_is_stale(monkeypatch, capsys) -> None:
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "VERIFIED", "note": "historical claim"},
        {"commit": "new", "branch": "main", "dirty": False, "worktree_sha256": "clean"},
    )
    assert "Status:     STALE" in output
    assert "missing candidate fingerprint" in output
    assert "Recorded note:" in output


def test_verified_with_different_candidate_is_stale(monkeypatch, capsys) -> None:
    current = {"commit": "new", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "VERIFIED", "fingerprint": {**current, "commit": "old"}},
        current,
    )
    assert "Status:     STALE" in output
    assert "candidate drift" in output


def test_verified_with_exact_clean_candidate_remains_unverified_without_independent_receipt(monkeypatch, capsys) -> None:
    current = {"commit": "same", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "VERIFIED", "fingerprint": current},
        current,
    )
    assert "Status:     UNVERIFIED" in output
    assert "protected state requires independent receipt verification" in output
    assert "Recorded:   VERIFIED" in output


def test_non_verified_state_does_not_require_fingerprint(monkeypatch, capsys) -> None:
    output = _run_status(
        monkeypatch,
        capsys,
        {"status": "EXECUTED"},
        {"commit": "new", "branch": "main", "dirty": False, "worktree_sha256": "clean"},
    )
    assert "Status:     EXECUTED" in output


@pytest.mark.parametrize("protected", ["VERIFIED", "VALIDATED"])
def test_manual_state_rejects_protected_evidence_states(monkeypatch, capsys, protected: str) -> None:
    module = _module()
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("protected state was persisted"))
    assert module.cmd_state(SimpleNamespace(status=protected, note="self certified")) == 2
    assert "protected evidence state" in capsys.readouterr().err


def test_manual_executed_state_is_bound_to_current_fingerprint(monkeypatch) -> None:
    module = _module()
    current = {"commit": "same", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    saved: dict = {}
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "PREPARED"})
    monkeypatch.setattr(module, "_git_fingerprint", lambda: current)
    monkeypatch.setattr(module, "_save_state", lambda state: saved.update(state))
    assert module.cmd_state(SimpleNamespace(status="executed", note="material action")) == 0
    assert saved["status"] == "EXECUTED"
    assert saved["fingerprint"] == current


def test_manual_state_rejects_unknown_label(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "PROPOSED"})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("unknown state was persisted"))
    assert module.cmd_state(SimpleNamespace(status="BANANA", note="")) == 2
    assert "unknown or non-manual" in capsys.readouterr().err


def test_manual_state_rejects_forward_jump(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "PROPOSED"})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("jump was persisted"))
    assert module.cmd_state(SimpleNamespace(status="EXECUTED", note="")) == 2
    assert "lifecycle jump" in capsys.readouterr().err


def test_manual_lifecycle_must_start_at_proposed(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "idle"})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("invalid start was persisted"))
    assert module.cmd_state(SimpleNamespace(status="PREPARED", note="")) == 2
    assert "must start at PROPOSED" in capsys.readouterr().err


@pytest.mark.parametrize("protected", ["VERIFIED", "VALIDATED"])
def test_verify_cannot_revalidate_protected_historical_state(monkeypatch, protected: str) -> None:
    module = _module()
    current = {"commit": "same", "branch": "main", "dirty": False, "worktree_sha256": "clean"}
    saved: dict = {}
    monkeypatch.setattr(module, "_load_state", lambda: {"status": protected, "note": "historical"})
    monkeypatch.setattr(module, "_git_fingerprint", lambda: current)
    monkeypatch.setattr(module, "_save_state", lambda state: saved.update(state))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="ok\n", stderr=""),
    )

    assert module.cmd_verify(SimpleNamespace(command=["python", "-c", "pass"])) == 0
    assert saved["status"] == "EXECUTED"
    assert saved["fingerprint"] == current
    assert "independent review" in saved["note"]


def _remediation_receipt_files(tmp_path: Path, candidate: str = "a" * 40) -> tuple[Path, Path]:
    package = tmp_path / "audit.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("audit/bago-provenance.json", json.dumps({"candidate_sha": candidate, "dirty": False}))
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({
        "contract": "bago.third-party-remediation-verification.v1",
        "result": "PASS",
        "package": package.name,
        "package_sha256": __import__("hashlib").sha256(package.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    return package, receipt


def _mock_recalculation(monkeypatch, module, package: Path) -> None:
    monkeypatch.setattr(module, "_verify_remediation_package", lambda _package: {
        "contract": "bago.third-party-remediation-verification.v1", "result": "PASS",
        "package": package.name, "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
    })


def _review_receipt(tmp_path: Path, package: Path, candidate: str = "a" * 40) -> Path:
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "contract": "bago.independent-review.github.v2", "result": "PASS",
        "reviewer": "independent-test-reviewer",
        "candidate_sha": candidate, "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "github": {"repository": "example/BAGO", "pull_request": 200, "review_id": 123},
    }), encoding="utf-8")
    return review


def test_consume_remediation_receipt_promotes_verified_only_when_candidate_matches(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package, receipt = _remediation_receipt_files(tmp_path)
    review = _review_receipt(tmp_path, package)
    current = {"commit": "a" * 40, "branch": "main", "remote": "https://github.com/example/BAGO.git", "dirty": False, "worktree_sha256": "clean"}
    saved: dict = {}
    monkeypatch.setattr(module, "_git_fingerprint", lambda: current)
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "EXECUTED"})
    monkeypatch.setattr(module, "_save_state", lambda state: saved.update(state))
    _mock_recalculation(monkeypatch, module, package)
    monkeypatch.setattr(module, "_verify_independent_review", lambda *_args: True)
    assert module.cmd_consume_remediation_receipt(SimpleNamespace(
        package=str(package), receipt=str(receipt), status="VERIFIED", review=str(review),
    )) == 0
    assert saved["status"] == "VERIFIED"
    assert saved["protected_receipt"]["candidate_sha"] == "a" * 40


def test_status_accepts_verified_state_with_current_external_receipt(monkeypatch, capsys, tmp_path: Path) -> None:
    package, receipt = _remediation_receipt_files(tmp_path)
    review = _review_receipt(tmp_path, package)
    current = {"commit": "a" * 40, "branch": "main", "remote": "https://github.com/example/BAGO.git", "dirty": False, "worktree_sha256": "clean"}
    state = {
        "status": "VERIFIED", "fingerprint": current,
        "protected_receipt": {
            "package": str(package), "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "receipt": str(receipt), "receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
            "candidate_sha": "a" * 40, "review": str(review), "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        },
    }
    output = _run_status(
        monkeypatch, capsys, state, current,
        lambda _package: {"contract": "bago.third-party-remediation-verification.v1", "result": "PASS", "package": package.name, "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest()},
        lambda *_args: True,
    )
    assert "Status:     VERIFIED" in output
    assert "Recorded:" not in output


def test_consume_remediation_receipt_rejects_candidate_drift(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _module()
    package, receipt = _remediation_receipt_files(tmp_path)
    _mock_recalculation(monkeypatch, module, package)
    monkeypatch.setattr(module, "_git_fingerprint", lambda: {"commit": "b" * 40, "dirty": False})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("protected state was persisted"))
    assert module.cmd_consume_remediation_receipt(SimpleNamespace(
        package=str(package), receipt=str(receipt), status="VERIFIED", review=None,
    )) == 2
    assert "does not match current HEAD" in capsys.readouterr().err


def test_consume_remediation_receipt_requires_independent_review_for_validated(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _module()
    package, receipt = _remediation_receipt_files(tmp_path)
    _mock_recalculation(monkeypatch, module, package)
    monkeypatch.setattr(module, "_git_fingerprint", lambda: {"commit": "a" * 40, "dirty": False})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("protected state was persisted"))
    assert module.cmd_consume_remediation_receipt(SimpleNamespace(
        package=str(package), receipt=str(receipt), status="VALIDATED", review=None,
    )) == 2
    assert "requires --review" in capsys.readouterr().err


def test_consume_remediation_receipt_promotes_validated_with_bound_review(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package, receipt = _remediation_receipt_files(tmp_path)
    review = _review_receipt(tmp_path, package)
    saved: dict = {}
    monkeypatch.setattr(module, "_git_fingerprint", lambda: {"commit": "a" * 40, "remote": "https://github.com/example/BAGO.git", "dirty": False})
    monkeypatch.setattr(module, "_load_state", lambda: {"status": "VERIFIED"})
    monkeypatch.setattr(module, "_save_state", lambda state: saved.update(state))
    _mock_recalculation(monkeypatch, module, package)
    monkeypatch.setattr(module, "_verify_independent_review", lambda *_args: True)
    assert module.cmd_consume_remediation_receipt(SimpleNamespace(
        package=str(package), receipt=str(receipt), status="VALIDATED", review=str(review),
    )) == 0
    assert saved["status"] == "VALIDATED"
    assert saved["protected_receipt"]["review_sha256"] == hashlib.sha256(review.read_bytes()).hexdigest()


def test_consume_remediation_receipt_rejects_self_issued_v1_review(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _module()
    package, receipt = _remediation_receipt_files(tmp_path)
    review = tmp_path / "self-issued-review.json"
    review.write_text(json.dumps({
        "contract": "bago.independent-review.v1", "result": "PASS",
        "reviewer": "attacker", "candidate_sha": "a" * 40,
        "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    _mock_recalculation(monkeypatch, module, package)
    monkeypatch.setattr(module, "_git_fingerprint", lambda: {"commit": "a" * 40, "remote": "https://github.com/example/BAGO.git", "dirty": False})
    monkeypatch.setattr(module, "_save_state", lambda _state: pytest.fail("self-issued review was persisted"))

    assert module.cmd_consume_remediation_receipt(SimpleNamespace(
        package=str(package), receipt=str(receipt), status="VERIFIED", review=str(review),
    )) == 2
    assert "GitHub-authenticated APPROVED review" in capsys.readouterr().err


def test_github_review_provenance_requires_matching_approved_review(monkeypatch) -> None:
    module = _module()
    review = {
        "contract": "bago.independent-review.github.v2", "result": "PASS",
        "reviewer": "independent-test-reviewer", "candidate_sha": "a" * 40,
        "package_sha256": "package-sha",
        "github": {"repository": "example/BAGO", "pull_request": 200, "review_id": 123},
    }
    monkeypatch.setattr(module, "_github_pull_review", lambda *_args: {
        "state": "APPROVED", "commit_id": "a" * 40,
        "user": {"login": "independent-test-reviewer"},
    })
    fingerprint = {"remote": "git@github.com:example/BAGO.git"}
    assert module._verify_independent_review(review, fingerprint, "a" * 40, "package-sha")

    monkeypatch.setattr(module, "_github_pull_review", lambda *_args: {
        "state": "APPROVED", "commit_id": "b" * 40,
        "user": {"login": "independent-test-reviewer"},
    })
    assert not module._verify_independent_review(review, fingerprint, "a" * 40, "package-sha")

    monkeypatch.setattr(module, "_github_pull_review", lambda *_args: {
        "state": "APPROVED", "commit_id": "a" * 40,
        "user": {"login": "different-github-user"},
    })
    assert not module._verify_independent_review(review, fingerprint, "a" * 40, "package-sha")


def test_github_review_provenance_fails_closed_when_api_is_unavailable(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(
        module.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr="network unavailable"),
    )
    with pytest.raises(ValueError, match="provenance is unavailable"):
        module._github_pull_review("example/BAGO", 200, 123)

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("gh")))
    with pytest.raises(ValueError, match="provenance is unavailable"):
        module._github_pull_review("example/BAGO", 200, 123)

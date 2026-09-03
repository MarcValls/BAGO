from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "generate_github_review_receipt.py"


def _module():
    spec = importlib.util.spec_from_file_location("generate_github_review_receipt", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package(tmp_path: Path, candidate: str = "a" * 40) -> Path:
    package = tmp_path / "audit.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("audit/bago-provenance.json", json.dumps({"candidate_sha": candidate, "dirty": False}))
    return package


def _approved_body(candidate: str, package_sha: str) -> str:
    return "\n".join((
        "attestation: bago.protected-remediation-attestation.v1",
        "contract: bago.independent-review.github.v2",
        "result: PASS",
        f"candidate_sha: {candidate}",
        f"package_sha256: {package_sha}",
    ))


def _mock_runtime(monkeypatch, module, *, reviewer="eligible-reviewer", pr_author="pr-author", permission="push"):
    class _Runtime:
        _AUTHORIZED_REVIEW_PERMISSIONS = frozenset({"push", "maintain", "admin"})

        @staticmethod
        def _remediation_candidate(_package):
            return "a" * 40

        @staticmethod
        def _github_repository_from_origin(_remote):
            return "example/BAGO"

        @staticmethod
        def _git_fingerprint():
            return {"remote": "git@github.com:example/BAGO.git"}

        @staticmethod
        def _github_pull_request(_repository, _pull_request):
            return {
                "number": 204, "state": "open", "merged": False,
                "head": {"sha": "a" * 40}, "base": {"ref": "main"},
                "user": {"login": pr_author},
            }

        @staticmethod
        def _github_pull_review(_repository, _pull_request, _review_id):
            package_sha = getattr(_Runtime, "_package_sha", "package-sha")
            return {
                "state": "APPROVED", "commit_id": "a" * 40,
                "user": {"login": reviewer},
                "body": _approved_body("a" * 40, package_sha),
            }

        @staticmethod
        def _github_review_attestation_matches(remote_review, candidate, package_sha):
            body = remote_review.get("body") or ""
            return body == _approved_body(candidate, package_sha)

        @staticmethod
        def _github_requires_fresh_approval(_repository):
            return True

        @staticmethod
        def _github_collaborator_permission(_repository, _login):
            return permission

    return _Runtime


def test_build_receipt_succeeds_for_eligible_authenticated_reviewer(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)
    package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
    runtime = _mock_runtime(monkeypatch, module)
    runtime._package_sha = package_sha
    monkeypatch.setattr(module, "_current_login", lambda: "eligible-reviewer")

    receipt = module.build_receipt(runtime, "example/BAGO", 204, 123, package, None)
    assert receipt["contract"] == "bago.independent-review.github.v2"
    assert receipt["result"] == "PASS"
    assert receipt["reviewer"] == "eligible-reviewer"
    assert receipt["candidate_sha"] == "a" * 40
    assert receipt["package_sha256"] == package_sha
    assert receipt["github"] == {"repository": "example/BAGO", "pull_request": 204, "review_id": 123}


def test_build_receipt_rejects_when_authenticated_login_differs_from_reviewer(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)
    package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
    runtime = _mock_runtime(monkeypatch, module)
    runtime._package_sha = package_sha
    monkeypatch.setattr(module, "_current_login", lambda: "someone-else")

    with pytest.raises(ValueError, match="does not match the review author"):
        module.build_receipt(runtime, "example/BAGO", 204, 123, package, None)


def test_build_receipt_rejects_author_as_reviewer(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)
    package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
    runtime = _mock_runtime(monkeypatch, module, reviewer="pr-author", pr_author="pr-author")
    runtime._package_sha = package_sha
    monkeypatch.setattr(module, "_current_login", lambda: "pr-author")

    with pytest.raises(ValueError, match="self-review"):
        module.build_receipt(runtime, "example/BAGO", 204, 123, package, None)


def test_build_receipt_rejects_reviewer_without_authority(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)
    package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
    runtime = _mock_runtime(monkeypatch, module, permission="read")
    runtime._package_sha = package_sha
    monkeypatch.setattr(module, "_current_login", lambda: "eligible-reviewer")

    with pytest.raises(ValueError, match="authorized repository permission"):
        module.build_receipt(runtime, "example/BAGO", 204, 123, package, None)


def test_build_receipt_rejects_missing_live_review_protection(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)
    package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
    runtime = _mock_runtime(monkeypatch, module)
    runtime._package_sha = package_sha
    monkeypatch.setattr(runtime, "_github_requires_fresh_approval", staticmethod(lambda _repository: False))
    monkeypatch.setattr(module, "_current_login", lambda: "eligible-reviewer")

    with pytest.raises(ValueError, match="does not require a fresh approving review"):
        module.build_receipt(runtime, "example/BAGO", 204, 123, package, None)


def test_build_receipt_rejects_stale_review_commit(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)
    package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
    runtime = _mock_runtime(monkeypatch, module)
    runtime._package_sha = package_sha
    monkeypatch.setattr(module, "_current_login", lambda: "eligible-reviewer")
    original_review = runtime._github_pull_review
    monkeypatch.setattr(runtime, "_github_pull_review", staticmethod(
        lambda repository, pull_request, review_id: {**original_review(repository, pull_request, review_id), "commit_id": "b" * 40}
    ))

    with pytest.raises(ValueError, match="stale relative to the last push"):
        module.build_receipt(runtime, "example/BAGO", 204, 123, package, None)

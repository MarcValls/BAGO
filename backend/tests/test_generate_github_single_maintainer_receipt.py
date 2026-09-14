from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "generate_github_single_maintainer_receipt.py"


def _module():
    spec = importlib.util.spec_from_file_location("generate_github_single_maintainer_receipt", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package(tmp_path: Path) -> Path:
    package = tmp_path / "audit.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("audit/bago-provenance.json", json.dumps({"candidate_sha": "a" * 40, "dirty": False}))
    return package


class _Runtime:
    @staticmethod
    def _remediation_candidate(_package):
        return "a" * 40

    @staticmethod
    def _github_current_login():
        return "repository-owner"

    @staticmethod
    def _git_fingerprint():
        return {"remote": "https://github.com/example/BAGO.git"}

    @staticmethod
    def _verify_single_maintainer_receipt(receipt, _fingerprint, candidate, package_sha, target_status):
        return (
            receipt["maintainer"] == "repository-owner"
            and receipt["candidate_sha"] == candidate
            and receipt["package_sha256"] == package_sha
            and target_status == "VERIFIED"
        )


def test_build_receipt_binds_authenticated_owner_candidate_and_package(tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)
    receipt = module.build_receipt(_Runtime, "example/BAGO", 204, package, None, "VERIFIED")
    assert receipt == {
        "contract": "bago.single-maintainer.github.v1",
        "result": "PASS",
        "maintainer": "repository-owner",
        "candidate_sha": "a" * 40,
        "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "github": {"repository": "example/BAGO", "pull_request": 204},
    }


def test_build_receipt_rejects_ineligible_live_github_authority(tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)

    class IneligibleRuntime(_Runtime):
        @staticmethod
        def _verify_single_maintainer_receipt(*_args):
            return False

    with pytest.raises(ValueError, match="not eligible"):
        module.build_receipt(IneligibleRuntime, "example/BAGO", 204, package, None, "VERIFIED")


def test_build_receipt_passes_validated_status_to_runtime(tmp_path: Path) -> None:
    module = _module()
    package = _package(tmp_path)

    class ValidatedRuntime(_Runtime):
        @staticmethod
        def _verify_single_maintainer_receipt(_receipt, _fingerprint, _candidate, _package_sha, target_status):
            return target_status == "VALIDATED"

    receipt = module.build_receipt(ValidatedRuntime, "example/BAGO", 204, package, None, "VALIDATED")
    assert receipt["candidate_sha"] == "a" * 40

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts" / "verify-authenticode.ps1"
MSIX_WORKFLOW = ROOT / ".github" / "workflows" / "build-release-msix-bootstrap.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "build-release-installer.yml"


def test_verifier_is_fail_closed_and_emits_candidate_safe_evidence() -> None:
    source = VERIFY_SCRIPT.read_text(encoding="utf-8")
    for required in (
        "SignatureStatus]::Valid", "SignerCertificate", "TimeStamperCertificate",
        "1.3.6.1.5.5.7.3.3", "ExpectedPublisher", "ExpectedThumbprint",
        "signtool.exe", "verify /pa /all /v", "bago.authenticode-evidence.v1",
        "Get-FileHash", "IsNullOrWhiteSpace($ExpectedPublisher)",
        "Get-AuthenticodeSignature no est", "GetNameInfo",
    ):
        assert required in source
    assert "IndexOf($ExpectedPublisher" not in source


def test_unsigned_file_fails_closed_even_when_authenticode_is_unavailable(tmp_path: Path) -> None:
    unsigned = tmp_path / "unsigned.exe"
    unsigned.write_bytes(b"not a signed portable executable")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(VERIFY_SCRIPT),
         "-Path", str(unsigned), "-ExpectedPublisher", "BAGO-Test-Only", "-SkipSignTool"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"}, check=False,
    )
    assert completed.returncode != 0


def test_empty_expected_publisher_is_rejected_before_verification(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.exe"
    candidate.write_bytes(b"placeholder")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(VERIFY_SCRIPT),
         "-Path", str(candidate), "-ExpectedPublisher", "", "-SkipSignTool"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"}, check=False,
    )
    assert completed.returncode != 0
    assert "expectedpublisher" in (completed.stdout + completed.stderr).lower()


def test_release_routes_are_msix_and_tag_locked() -> None:
    workflow = MSIX_WORKFLOW.read_text(encoding="utf-8")
    caller = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "Checkout exact release tag", "git merge-base --is-ancestor",
        "verify_version_consistency.py --tag", "azure/artifact-signing-action@v2",
        "Sign canonical MSIX package", "Add-AppxPackage -Path",
        "CLEAN_MACHINE_INSTALL_OPEN",
    ):
        assert marker in workflow
    assert "bago-installer.nsi" not in workflow
    assert "makensis" not in workflow.lower()
    assert "build-release-msix-bootstrap.yml" in caller
    assert "secrets: inherit" in caller


def test_diagnostic_workflow_has_no_nsis_materialization() -> None:
    diagnostic = (ROOT / ".github" / "workflows" / "build-installer.yml").read_text(encoding="utf-8")
    assert "build-msix-release.ps1" in diagnostic
    assert "bago-installer.nsi" not in diagnostic
    assert "makensis" not in diagnostic.lower()

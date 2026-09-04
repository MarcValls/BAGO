from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts" / "verify-authenticode.ps1"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "build-release-installer.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "canonical-ci.yml"
DIAGNOSTIC_WORKFLOW = ROOT / ".github" / "workflows" / "build-installer.yml"
BUILD_SCRIPT = ROOT / "releases" / "build-installer.ps1"


def test_verifier_is_fail_closed_and_emits_candidate_safe_evidence() -> None:
    source = VERIFY_SCRIPT.read_text(encoding="utf-8")
    for required in (
        "SignatureStatus]::Valid",
        "SignerCertificate",
        "TimeStamperCertificate",
        "1.3.6.1.5.5.7.3.3",
        "ExpectedPublisher",
        "ExpectedThumbprint",
        "signtool.exe",
        "verify /pa /all /v",
        "bago.authenticode-evidence.v1",
        "Get-FileHash",
        "IsNullOrWhiteSpace($ExpectedPublisher)",
        "Get-AuthenticodeSignature no está disponible",
        "GetNameInfo",
    ):
        assert required in source
    assert "IndexOf($ExpectedPublisher" not in source


def test_unsigned_file_fails_closed_even_when_authenticode_is_unavailable(tmp_path: Path) -> None:
    unsigned = tmp_path / "unsigned.exe"
    unsigned.write_bytes(b"not a signed portable executable")
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(VERIFY_SCRIPT),
            "-Path",
            str(unsigned),
            "-ExpectedPublisher",
            "BAGO-Test-Only",
            "-SkipSignTool",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    assert completed.returncode != 0


def test_empty_expected_publisher_is_rejected_before_verification(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.exe"
    candidate.write_bytes(b"placeholder")
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(VERIFY_SCRIPT),
            "-Path",
            str(candidate),
            "-ExpectedPublisher",
            "",
            "-SkipSignTool",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    assert completed.returncode != 0
    assert "expectedpublisher" in (completed.stdout + completed.stderr).lower()


def test_release_workflow_signs_inner_exe_then_installer_before_upload() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    markers = [
        "Sign packaged BAGO executable",
        "Verify packaged BAGO signature",
        "Build canonical tag-locked installer",
        "Sign canonical NSIS installer",
        "Verify signatures and generate signed sidecar evidence",
        "Verify installer identity and lifecycle",
        "Upload installer artifact",
    ]
    positions = [workflow.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert "environment: release-signing" in workflow
    assert "id-token: write" in workflow
    assert "azure/login@v3" in workflow
    assert workflow.count("azure/artifact-signing-action@v2") == 2
    assert "-DeferSidecar" in workflow
    assert "REQUESTED_TAG: ${{ inputs.release_tag }}" in workflow
    assert '$tag = "${{ inputs.release_tag }}"' not in workflow
    assert "origin/main" in workflow
    assert "bago-${{ env.BAGO_VERSION }}-authenticode.json" in workflow


def test_sidecar_is_generated_only_after_release_signing() -> None:
    build = BUILD_SCRIPT.read_text(encoding="utf-8")
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "[switch]$DeferSidecar" in build
    assert "if (-not $DeferSidecar)" in build
    sign_pos = workflow.index("Sign canonical NSIS installer")
    sidecar_pos = workflow.index('Set-Content -LiteralPath "$setup.sha256"')
    assert sign_pos < sidecar_pos


def test_ci_blocks_moderate_or_higher_audit_and_diagnostic_artifact_is_named_unsigned() -> None:
    ci = CI_WORKFLOW.read_text(encoding="utf-8")
    diagnostic = DIAGNOSTIC_WORKFLOW.read_text(encoding="utf-8")
    assert "npm audit --audit-level=moderate" in ci
    assert "name: unsigned-ci-bago-${{ env.BAGO_VERSION }}-setup" in diagnostic
    assert "cannot be published as a release asset" in diagnostic

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "build-release-msix-bootstrap.yml"
SCRIPT = ROOT / "scripts" / "build-msix-release.ps1"


def test_msix_release_workflow_is_tag_locked_and_fail_closed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "git rev-parse HEAD",
        "git merge-base --is-ancestor",
        "verify_version_consistency.py --tag",
        "azure/artifact-signing-action@v2",
        "BAGO_EXPECTED_PUBLISHER",
        "Add-AppxPackage -Path",
        "CLEAN_MACHINE_INSTALL_OPEN",
        "actions/upload-artifact@v5",
    ):
        assert marker in workflow
    assert "bago-installer.nsi" not in workflow
    assert "makensis" not in workflow.lower()


def test_msix_release_builder_requires_canonical_version_and_exact_publisher() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "release_version.txt" in script
    assert "Publisher -notmatch '^CN='" in script
    assert "-RuntimeOnly" in script
    assert "build-msix-bootstrap.ps1" in script
    assert "NOT_SIGNED" in script
def test_installer_wrapper_signing_input_is_declared_and_fails_closed() -> None:
    wrapper = (ROOT / ".github" / "workflows" / "build-release-installer.yml").read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    call_contract = workflow.split("  workflow_call:", 1)[1].split("\npermissions:", 1)[0]
    assert "      signing_backend:" in call_contract
    assert "        default: azure" in call_contract
    assert "signing_backend: ${{ inputs.signing_backend }}" in wrapper
    assert "REQUESTED_SIGNING_BACKEND: ${{ inputs.signing_backend || 'azure' }}" in workflow
    rejection = "$env:REQUESTED_SIGNING_BACKEND -ne 'azure'"
    assert rejection in workflow
    assert workflow.index(rejection) < workflow.index("git fetch")
    assert workflow.index(rejection) < workflow.index("azure/login@v3")

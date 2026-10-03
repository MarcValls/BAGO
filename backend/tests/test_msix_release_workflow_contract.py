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

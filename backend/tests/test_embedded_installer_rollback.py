"""Safe, temporary regression tests for the embedded NSIS payload installer."""
from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "releases" / "install-embedded-payload.ps1"
NSIS = ROOT / "releases" / "bago-installer.nsi"
BUILDER = ROOT / "releases" / "build-installer.ps1"


def _payload(path: Path, *, complete: bool) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("backend/bago_core/cli.py", "print('ok')\n")
        if complete:
            archive.writestr("electron-viewer/BAGO.exe", b"MZ-test")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="ascii")
    return sidecar


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(INSTALLER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_invalid_staged_payload_preserves_existing_installation(tmp_path: Path) -> None:
    target = tmp_path / "BAGO"
    target.mkdir()
    marker = target / "original.txt"
    marker.write_text("preserve", encoding="utf-8")
    archive = tmp_path / "broken.zip"
    sidecar = _payload(archive, complete=False)

    result = _run("-RepoRoot", str(target), "-ZipPath", str(archive), "-Sha256Path", str(sidecar))

    assert result.returncode != 0
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert not (tmp_path / ".BAGO-rollback").exists()


def test_successful_swap_keeps_rollback_until_finalize(tmp_path: Path) -> None:
    target = tmp_path / "BAGO"
    target.mkdir()
    (target / "original.txt").write_text("preserve", encoding="utf-8")
    archive = tmp_path / "complete.zip"
    sidecar = _payload(archive, complete=True)

    installed = _run("-RepoRoot", str(target), "-ZipPath", str(archive), "-Sha256Path", str(sidecar))

    assert installed.returncode == 0, installed.stderr
    rollback = tmp_path / ".BAGO-rollback"
    assert (target / "backend" / "bago_core" / "cli.py").is_file()
    assert (target / "electron-viewer" / "BAGO.exe").is_file()
    assert (rollback / "original.txt").read_text(encoding="utf-8") == "preserve"

    finalized = _run("-RepoRoot", str(target), "-Finalize")
    assert finalized.returncode == 0, finalized.stderr
    assert not rollback.exists()


def test_resume_restores_backup_when_target_is_absent_before_retry(tmp_path: Path) -> None:
    target = tmp_path / "BAGO"
    rollback = tmp_path / ".BAGO-rollback"
    rollback.mkdir()
    (rollback / "original.txt").write_text("recover-me", encoding="utf-8")
    archive = tmp_path / "complete.zip"
    sidecar = _payload(archive, complete=True)

    result = _run("-RepoRoot", str(target), "-ZipPath", str(archive), "-Sha256Path", str(sidecar))

    assert result.returncode == 0, result.stderr
    assert (rollback / "original.txt").read_text(encoding="utf-8") == "recover-me"
    assert (target / "electron-viewer" / "BAGO.exe").is_file()


def test_resume_rolls_back_unfinalized_replacement_before_retry(tmp_path: Path) -> None:
    target = tmp_path / "BAGO"
    (target / "backend" / "bago_core").mkdir(parents=True)
    (target / "backend" / "bago_core" / "cli.py").write_text("replacement", encoding="utf-8")
    (target / "electron-viewer").mkdir()
    (target / "electron-viewer" / "BAGO.exe").write_bytes(b"unfinished")
    rollback = tmp_path / ".BAGO-rollback"
    rollback.mkdir()
    (rollback / "original.txt").write_text("recover-me", encoding="utf-8")
    archive = tmp_path / "complete.zip"
    sidecar = _payload(archive, complete=True)

    result = _run("-RepoRoot", str(target), "-ZipPath", str(archive), "-Sha256Path", str(sidecar))

    assert result.returncode == 0, result.stderr
    assert (rollback / "original.txt").read_text(encoding="utf-8") == "recover-me"
    assert (target / "electron-viewer" / "BAGO.exe").read_bytes() == b"MZ-test"


def test_nsis_installer_finalizes_after_verified_success() -> None:
    """Regression guard: a completed install must clean up its rollback backup.

    Without an explicit -Finalize call after verifying BAGO.exe, the
    ``.BAGO-rollback`` directory from a prior successful install lingers
    forever. On the *next* install/update, install-embedded-payload.ps1 then
    misreads that stale backup as evidence of an interrupted swap (its only
    signal is "does electron-viewer\\BAGO.exe already exist"), and restores
    the old backup before overwriting it again with the new payload -
    silently corrupting the rollback safety net on every normal update.

    -Finalize must run only after *every* installer write has succeeded
    (backend launcher script, registry entries, uninstaller, shortcuts) -
    not merely after the BAGO.exe existence check - otherwise an interruption
    between an early -Finalize call and those later writes would leave a
    half-registered install with no way back to the previous one.
    """
    nsi = NSIS.read_text(encoding="utf-8")
    verify_idx = nsi.index('MB_ICONSTOP|MB_OK "Error: BAGO.exe no se encontró tras instalar."')
    dev_ps1_idx = nsi.index('File /oname=dev.ps1')
    write_uninstaller_idx = nsi.index('WriteUninstaller "$INSTDIR\\uninstall.exe"')
    last_shortcut_idx = nsi.index('CreateShortcut "$SMPROGRAMS\\BAGO\\Desinstalar BAGO.lnk"')
    finalize_idx = nsi.index("-Finalize")

    assert finalize_idx > verify_idx, (
        "-Finalize must be invoked only after BAGO.exe existence is verified"
    )
    assert finalize_idx > dev_ps1_idx, (
        "-Finalize must run after the backend launcher script is installed"
    )
    assert finalize_idx > write_uninstaller_idx, (
        "-Finalize must run after the uninstaller is written"
    )
    assert finalize_idx > last_shortcut_idx, (
        "-Finalize must run after all shortcuts are created, i.e. at the very"
        " end of a fully successful install - not right after the BAGO.exe"
        " check, so an interruption before that point can still be recovered"
        " from the previous install's backup"
    )
    assert '-RepoRoot "$INSTDIR" -Finalize' in nsi

    # A failed cleanup must abort the installer rather than silently warn and
    # report success: a lingering backup after a "successful" install would
    # reproduce the exact stale-restore corruption this patch fixes on the
    # very next update.
    finalize_block_end = nsi.index("SectionEnd", finalize_idx)
    finalize_block = nsi[finalize_idx:finalize_block_end]
    assert "Abort" in finalize_block, (
        "a failed -Finalize call must abort the installer, not just warn"
    )


def test_builder_resolves_installer_version_from_canonical_authority() -> None:
    builder = BUILDER.read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-installer.yml").read_text(encoding="utf-8")
    msix_builder = (ROOT / "scripts/build-msix-release.ps1").read_text(encoding="utf-8")
    assert r'Join-Path $repoRoot "release_version.txt"' in builder
    assert r'backend\release_version.txt' not in builder
    assert "release_version.txt" in msix_builder
    assert "build-msix-bootstrap.ps1" in msix_builder
    assert "ref: ${{ inputs.source_ref || github.sha }}" in workflow
    assert "node-version: '22.16.0'" in workflow
    assert "python-version: '3.14'" in workflow
    assert "makensis" not in workflow.lower()


def test_official_workflows_have_no_nsis_materialization() -> None:
    for path in (
        ROOT / ".github/workflows/build-installer.yml",
        ROOT / ".github/workflows/build-release-installer.yml",
        ROOT / ".github/workflows/canonical-ci.yml",
    ):
        text = path.read_text(encoding="utf-8").lower()
        assert "resolve-nsis.ps1" not in text
        assert "makensis" not in text
        assert "bago-installer.nsi" not in text
def test_release_build_requires_explicit_identity_and_embedded_inputs() -> None:
    """No local default may mint an installer whose version or source is ambiguous."""
    nsi = NSIS.read_text(encoding="utf-8")
    payload_installer = INSTALLER.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")

    for required in ("APP_VERSION", "APP_GIT_REF", "APP_GIT_SHA", "DISTRIBUTION_ZIP_FILE", "DEV_PS1_FILE"):
        assert f'!error "{required} must be supplied by the release build"' in nsi
    assert "bago-4.9.0-distribution.zip" not in payload_installer
    assert "ZipPath es obligatorio" in payload_installer
    assert "Sha256Path es obligatorio" in payload_installer
    assert '"/DAPP_GIT_SHA=$GitSha"' in builder


def test_release_workflows_bind_checkout_tag_sha_and_msix_identity() -> None:
    manual = (ROOT / ".github/workflows/build-release-installer.yml").read_text(encoding="utf-8")
    msix = (ROOT / ".github/workflows/build-release-msix-bootstrap.yml").read_text(encoding="utf-8")
    canonical = (ROOT / ".github/workflows/canonical-ci.yml").read_text(encoding="utf-8")
    assert "build-release-msix-bootstrap.yml" in manual
    assert "ref: ${{ inputs.release_tag }}" in msix
    assert 'git rev-parse "$tag`^{commit}"' in msix
    assert "python scripts/verify_version_consistency.py --tag $tag --is-tag true" in msix
    assert "BAGO_EXPECTED_PUBLISHER" in msix
    assert "Add-AppxPackage -Path" in msix
    assert "CLEAN_MACHINE_INSTALL_OPEN" in msix
    assert "Assert disposable runner and tag-only execution" in canonical
    assert "build-msix-release.ps1" in canonical
    assert "bago-installer.nsi" not in canonical
def test_embedded_nsi_payload_includes_and_passes_distribution_hash_sidecar() -> None:
    """The embedded installer must satisfy the payload script's mandatory hash input."""
    nsi = NSIS.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")

    assert 'File /oname=bago-${APP_VERSION}-distribution.zip.sha256 "${DISTRIBUTION_ZIP_FILE}.sha256"' in nsi
    assert '-Sha256Path "$PLUGINSDIR\\bago-${APP_VERSION}-distribution.zip.sha256"' in nsi
    assert 'Set-Content -LiteralPath "$zipFile.sha256"' in builder

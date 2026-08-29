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


def test_embedded_nsi_payload_includes_and_passes_distribution_hash_sidecar() -> None:
    """The embedded installer must satisfy the payload script's mandatory hash input."""
    nsi = NSIS.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")

    assert 'File /oname=bago-${APP_VERSION}-distribution.zip.sha256 "${DISTRIBUTION_ZIP_FILE}.sha256"' in nsi
    assert '-Sha256Path "$PLUGINSDIR\\bago-${APP_VERSION}-distribution.zip.sha256"' in nsi
    assert 'Set-Content -LiteralPath "$zipFile.sha256"' in builder

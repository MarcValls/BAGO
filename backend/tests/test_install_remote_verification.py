from pathlib import Path


def test_remote_installer_requires_paired_checksum_and_verifies_bytes():
    script = (Path(__file__).resolve().parents[1] / "install-remote.ps1").read_text(encoding="utf-8")

    assert "Get-PairedBundle" in script
    assert '".sha256"' in script
    assert "Get-FileHash -LiteralPath $tempZip -Algorithm SHA256" in script
    assert "El digest publicado por GitHub no coincide" in script
    assert "Assert-ZipMagic" in script
    assert "bago_core\\launcher.py" in script
    assert "La version del bundle" in script
    assert "-not $_.prerelease" in script


def test_remote_installer_supports_explicit_signature_policy():
    script = (Path(__file__).resolve().parents[1] / "install-remote.ps1").read_text(encoding="utf-8")

    assert "[switch]$RequireSignature" in script
    assert "--batch --verify" in script
    assert "RequireSignature exige gpg.exe" in script
    assert "$PROFILE.CurrentUserAllHosts" in script
    assert "$PROFILE.CurrentUserCurrentHost" in script

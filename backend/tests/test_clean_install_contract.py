from __future__ import annotations

from pathlib import Path

from bago_core.install_roles import load_selection


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"


def test_public_bootstrap_targets_monorepo_installer() -> None:
    bootstrap = (REPOSITORY_ROOT / "install-remote.ps1").read_text(encoding="utf-8")
    assert "main/backend/install-remote.ps1" in bootstrap
    assert "GetTempPath" in bootstrap
    assert "Get-BagoManagerVersion" not in bootstrap


def test_installer_is_safe_for_clean_and_repeat_installs() -> None:
    installer = (BACKEND_ROOT / "install-v4.ps1").read_text(encoding="utf-8")
    assert "Remove-Item -LiteralPath $_.FullName" in installer
    assert "Remove-Item -LiteralPath $_ -Recurse" not in installer
    assert "Resolve-BagoPython" in installer
    assert "Python.Python.3.14" in installer
    assert "Update-InstallSelection" in installer
    assert '$roles["launch"]' in installer
    assert "-DevPath $selectionDevPath" in installer
    assert "$selectionPath -Raw -Encoding UTF8" in installer
    assert "NoShellIntegration" in installer
    assert "PreserveDevRole" in installer
    assert '$selectionDevPath = if ($PreserveDevRole) { "" } else { $sourceFull }' in installer
    assert '$explicitUserRoot = [System.Environment]::GetEnvironmentVariable("BAGO_USER_ROOT")' in installer
    assert "if ([string]::IsNullOrWhiteSpace($explicitUserRoot)) {" in installer
    assert '"install_config.json", ".bago\\config.json"' in installer
    assert "UTF8Encoding" in installer
    assert "auto_allow_tools = $false" in installer
    assert '$ok[$name] = [ordered]@{ ok = $false; detail = $_.Exception.Message }' in installer
    assert '"warn"' in installer

    launcher = (BACKEND_ROOT / "bago.ps1").read_text(encoding="utf-8")
    assert "Resolve-BagoPythonExecutable" in launcher
    assert "$selectionFile -Raw -Encoding UTF8" in launcher
    assert "& python " not in launcher
    assert "BAGO\\backend" in launcher
    assert "Join-Path $entry.path 'bago.ps1'" in installer
    assert 'Arguments @("bago_core\\cli.py", "validate")' in installer
    assert '& $pythonExe "test_security_release.py"' not in installer


def test_clean_install_smoke_is_part_of_canonical_ci() -> None:
    smoke = BACKEND_ROOT / "scripts" / "test_clean_install.ps1"
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "canonical-ci.yml").read_text(encoding="utf-8")
    assert smoke.is_file()
    assert "scripts/test_clean_install.ps1" in workflow


def test_install_selection_reader_accepts_windows_powershell_bom(tmp_path: Path) -> None:
    selection = tmp_path / "install_selection.json"
    selection.write_text('{"version":1,"roles":{"active":{"path":"C:\\\\BAGO"}}}', encoding="utf-8-sig")
    assert load_selection(selection)["roles"]["active"]["path"] == "C:\\BAGO"

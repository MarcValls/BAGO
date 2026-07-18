from pathlib import Path


def test_install_v4_creates_desktop_and_start_menu_shortcuts():
    script = (Path(__file__).resolve().parents[1] / "install-v4.ps1").read_text(encoding="utf-8")

    assert "Test-IsAdministrator" in script
    assert "Invoke-SelfElevatedInstall" in script
    assert "ResultPath" in script
    assert "ElevatedChild" in script
    assert "Verb RunAs" in script
    assert "Write-InstallResult" in script
    assert "WScript.Shell" in script
    assert "CreateShortcut" in script
    assert "Desktop" in script
    assert "Start Menu" in script
    assert "Accesos directos creados" in script
    assert "Get-BagoExplorerContextMenuCommand" in script
    assert "Directory\\shell\\BAGO" in script
    assert "Abrir con BAGO" in script
    assert "shortcuts = $shortcuts" in script
    assert "explorer_context_menu = $explorerContextMenu" in script
    assert "BEGIN BAGO MANAGED BLOCK" in script
    assert "function global:bago" in script
    assert "Microsoft.PowerShell_profile.ps1" in script


def test_install_service_reports_shortcuts_and_install_path():
    script = (Path(__file__).resolve().parents[1] / "electron" / "install-service.cjs").read_text(encoding="utf-8")

    assert "parseInstallResult" in script
    assert "buildInstallDetail" in script
    assert "Accesos directos:" in script
    assert "Ubicación:" in script
    assert "Menu contextual:" in script
    assert "PowerShell bootstrap:" in script


def test_uninstall_and_launchers_propagate_context_menu_flag():
    root = Path(__file__).resolve().parents[1]
    cli = (root / "bago_core" / "cli.py").read_text(encoding="utf-8")
    uninstall_ps1 = (root / "bago-uninstall.ps1").read_text(encoding="utf-8")
    uninstall_cmd = (root / "bago-uninstall.cmd").read_text(encoding="utf-8")
    lifecycle = (root / "bago_core" / "commands" / "cmd_lifecycle.py").read_text(encoding="utf-8")
    preload = (root / "electron" / "preload.cjs").read_text(encoding="utf-8")
    dependency = (root / "electron" / "dependency-service.cjs").read_text(encoding="utf-8")

    assert "parents[1]" in cli
    assert "Push-Location $root" in uninstall_ps1
    assert "pushd \"%BAGO_ROOT%\"" in uninstall_cmd
    assert "_remove_bago_explorer_context_menu" in lifecycle
    assert "Directory\\shell\\BAGO" in lifecycle
    assert "Directory\\Background\\shell\\BAGO" in lifecycle

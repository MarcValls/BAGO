"""Regression contracts for retained legacy manager compatibility surfaces."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installation_cards_do_not_reference_undefined_seal_badge():
    source = (ROOT / "manager" / "js" / "legacy-manager.js").read_text(encoding="utf-8")
    assert "sealBadge" not in source


def test_provider_endpoint_awaits_electron_manager_url():
    source = (ROOT / "manager" / "js" / "core.js").read_text(encoding="utf-8")
    assert "async function pmManagerBaseUrl()" in source
    assert "await api.getManagerUrl()" in source
    assert "async function pmProvidersEndpoint()" in source
    assert "await pmManagerBaseUrl()" in source
    assert "const endpoint=await pmProvidersEndpoint()" in source


def test_release_install_actions_dispatch_to_release_job_gateway():
    manager = (ROOT / "manager" / "js" / "legacy-manager.js").read_text(encoding="utf-8")
    preload = (ROOT / "electron" / "preload.cjs").read_text(encoding="utf-8")

    assert "startReleaseJob" in manager
    assert "installReleaseJob" in manager
    assert "BAGO_RELEASE_JOB:" in manager
    assert "buildInstallCommand" not in manager
    assert "install-remote.ps1" not in manager
    assert "buildInstallCommand" not in preload
    assert "onReleaseJobChanged" in preload
    assert "removeListener('bago:release-job-changed', listener)" in preload


def test_legacy_uninstall_action_uses_execution_gateway_without_shell_command():
    manager = (ROOT / "manager" / "js" / "legacy-manager.js").read_text(encoding="utf-8")
    preload = (ROOT / "electron" / "preload.cjs").read_text(encoding="utf-8")
    service = (ROOT / "electron" / "install-service.cjs").read_text(encoding="utf-8")
    dependency = (ROOT / "electron" / "dependency-service.cjs").read_text(encoding="utf-8")

    assert "BAGO_INSTALL_UNINSTALL:" in manager
    assert "api.installAction({action:'uninstall'" in manager
    assert "buildUninstallCommand" not in manager
    assert "buildUninstallCommand" not in preload
    assert "prepareSystemUninstall" in service
    assert "runUninstallScript" not in service
    assert "runUninstallScript" not in dependency

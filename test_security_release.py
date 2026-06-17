#!/usr/bin/env python3
"""Security regression checks for the BAGO v4 distribution path."""

from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "api"))

from bridge import BagoAPIHandler, BagoAPIServer
from config_manager import ConfigManager


def test_default_auto_allow_tools_is_false() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = ConfigManager(base_path=td)
        assert cfg.get("features.auto_allow_tools") is False


def test_execute_command_has_no_shell_true() -> None:
    src = (BAGO_ROOT / ".bago" / "core" / "tool_registry.py").read_text(encoding="utf-8")
    exposed = [
        line.strip()
        for line in src.splitlines()
        if "shell=True" in line and not line.strip().startswith("#")
    ]
    assert not exposed


def test_cors_does_not_allow_wildcard() -> None:
    src = (BAGO_ROOT / ".bago" / "api" / "bridge.py").read_text(encoding="utf-8")
    assert 'Access-Control-Allow-Origin", "*"' not in src
    assert "Access-Control-Allow-Origin', '*'" not in src


def test_cors_allows_only_localhost_origins() -> None:
    assert BagoAPIHandler._cors_origin_allowed("http://localhost:3000")
    assert BagoAPIHandler._cors_origin_allowed("http://127.0.0.1:8080")
    assert BagoAPIHandler._cors_origin_allowed("http://[::1]:8080")
    assert not BagoAPIHandler._cors_origin_allowed("https://example.com")
    assert not BagoAPIHandler._cors_origin_allowed("http://localhost.evil.test")


def test_non_localhost_api_requires_token() -> None:
    try:
        BagoAPIServer(object(), object(), host="0.0.0.0", token="")
    except RuntimeError:
        return
    raise AssertionError("BagoAPIServer accepted non-localhost host without token")


def test_release_package_excludes_install_config_and_includes_uninstaller() -> None:
    sys.path.insert(0, str(BAGO_ROOT / "scripts"))
    from package_v4 import build_package

    with tempfile.TemporaryDirectory() as td:
        output_dir = Path(td)
        result = build_package(BAGO_ROOT, output_dir)
        with zipfile.ZipFile(result["zip"], "r") as zf:
            names = set(zf.namelist())
        assert "package-lock.json" in names
        assert "install_config.json" not in names
        assert ".bago/credentials.json" not in names
        assert "bago-uninstall.ps1" in names
        assert "bago-uninstall.cmd" in names


def test_repair_only_skips_post_install_tests() -> None:
    script = (BAGO_ROOT / "install-v4.ps1").read_text(encoding="utf-8")

    assert "if ($RepairOnly)" in script
    assert "$SkipTests = $true" in script


def test_remote_installer_blocks_future_versions() -> None:
    script = (BAGO_ROOT / "install-remote.ps1").read_text(encoding="utf-8")

    assert "Get-ManagerVersion" in script
    assert "Test-ReleaseAllowed" in script
    assert "release compatible" in script


def test_manager_hides_future_versions() -> None:
    script = (BAGO_ROOT / "manager" / "js" / "legacy-manager.js").read_text(encoding="utf-8")

    assert "hiddenFutureReleaseCount" in script
    assert "isFutureReleaseTag" in script
    assert "release(s) compatibles" in script


def test_main_process_hides_future_versions() -> None:
    script = (BAGO_ROOT / "electron" / "main.cjs").read_text(encoding="utf-8")
    release_service = (BAGO_ROOT / "electron" / "release-service.cjs").read_text(encoding="utf-8")

    assert "createDependencyService" in script
    assert "createReleaseService" in script
    assert "fetchReleases" in release_service
    assert "currentManagerVersion" in release_service
    assert "isFutureReleaseTag" in release_service


def test_manager_surfaces_startup_dependencies_and_provider_onboarding() -> None:
    main_script = (BAGO_ROOT / "electron" / "main.cjs").read_text(encoding="utf-8")
    environment = (BAGO_ROOT / "electron" / "environment.cjs").read_text(encoding="utf-8")
    ipc_service = (BAGO_ROOT / "electron" / "ipc-service.cjs").read_text(encoding="utf-8")
    window_service = (BAGO_ROOT / "electron" / "window-service.cjs").read_text(encoding="utf-8")
    dependency_service = (BAGO_ROOT / "electron" / "dependency-service.cjs").read_text(encoding="utf-8")
    runtime_service = (BAGO_ROOT / "electron" / "runtime-service.cjs").read_text(encoding="utf-8")
    install_service = (BAGO_ROOT / "electron" / "install-service.cjs").read_text(encoding="utf-8")
    release_service = (BAGO_ROOT / "electron" / "release-service.cjs").read_text(encoding="utf-8")
    html = (BAGO_ROOT / "manager" / "index.html").read_text(encoding="utf-8")
    startup_banner = (BAGO_ROOT / "manager" / "js" / "startup-deps.js").read_text(encoding="utf-8")
    session_script = (BAGO_ROOT / "manager" / "js" / "session-manager.js").read_text(encoding="utf-8")
    ops_console = (BAGO_ROOT / "manager" / "js" / "ops-console.js").read_text(encoding="utf-8")
    patch_manager = (BAGO_ROOT / "manager" / "js" / "patch-manager.js").read_text(encoding="utf-8")
    preload = (BAGO_ROOT / "electron" / "preload.cjs").read_text(encoding="utf-8")
    release_job_manager = (BAGO_ROOT / "electron" / "release-job-manager.cjs").read_text(encoding="utf-8")
    chat_commands = (BAGO_ROOT / ".bago" / "chat" / "commands.py").read_text(encoding="utf-8")
    chat_repl = (BAGO_ROOT / ".bago" / "chat" / "repl.py").read_text(encoding="utf-8")
    intent_engine = (BAGO_ROOT / ".bago" / "core" / "intent_engine.py").read_text(encoding="utf-8")
    tool_registry = (BAGO_ROOT / ".bago" / "core" / "tool_registry.py").read_text(encoding="utf-8")
    command_intents = (BAGO_ROOT / ".bago" / "core" / "command_intents.json").read_text(encoding="utf-8")
    project_memory = (BAGO_ROOT / ".bago" / "tools" / "project_memory.py").read_text(encoding="utf-8")

    assert "createDependencyService" in main_script
    assert "createRuntimeService" in main_script
    assert "createInstallService" in main_script
    assert "createReleaseService" in main_script
    assert "require('./environment.cjs')" in main_script
    assert "require('./window-service.cjs')" in main_script
    assert "require('./ipc-service.cjs')" in main_script
    assert "registerIpcHandlers" in main_script
    assert "createManagerWindow()" in main_script
    assert "dependency-service.cjs" in main_script
    assert "ipcMain.handle" not in main_script
    assert "ROOT_DIR" in environment
    assert "MANAGER_HTML" in environment
    assert "PRELOAD_PATH" in environment
    assert "CHAT_HOST" in environment
    assert "CHAT_START_PORT" in environment
    assert "resolveBagoRuntimeRoot" in environment
    assert "resolveUiDist" in environment
    assert "resolveBundledRuntimeRoot" in environment
    assert "resolveInstalledRuntimeRoot" in environment
    assert "runVisiblePowerShell" in environment
    assert "findPackagedRuntimeRoot" in environment
    assert "registerIpcHandlers" in ipc_service
    assert "bago:dependency-action" in ipc_service
    assert "bago:node-cmd" in ipc_service
    assert "bago:release-job-start" in ipc_service
    assert "bago:release-job-delete" in ipc_service
    assert "createManagerWindow" in window_service
    assert "SMOKE_TEST" in window_service
    assert "managerHealth" in dependency_service
    assert "dependencyCatalog" in dependency_service
    assert "dependency_catalog" in dependency_service
    assert "runBagoNode" in runtime_service
    assert "ensureBagoInstalled" in install_service
    assert "ReleaseJobManager" in release_service
    assert "fetchReleases" in release_service
    assert "verify_release_463.py" in (BAGO_ROOT / "scripts" / "verify_release_463.py").read_text(encoding="utf-8")
    assert "js/startup-deps.js" in html
    assert "js/ops-console.js" in html
    assert 'data-pm-view="control"' in html
    assert 'id="pm-view-route"' in html
    assert "pm-session-provider-actions" in html
    assert "Instalar faltantes" in startup_banner
    assert "data-provider-action" in session_script
    assert "pmRenderProviderActions" in session_script
    assert "pmProviderAction" in session_script
    assert "pmRenderControl" in ops_console
    assert "pmRoutePlan" in ops_console
    assert "Entrada" in ops_console
    assert "Modelo" in ops_console
    assert "Agente" in ops_console
    assert "Tools/Skills" in ops_console
    assert "Comando" in ops_console
    assert "Salida" in ops_console
    assert "deleteReleaseJob" in preload
    assert "deleteJob" in release_job_manager
    assert "pmRenderControl" in patch_manager
    assert "\"project\"" in chat_commands
    assert "Analiza el proyecto actual" in chat_commands
    assert "Proyecto detectado" in chat_repl
    assert "_looks_like_directory_path" in chat_repl
    assert "BAGO_INTENT_EXAMPLES_PATH" in tool_registry
    assert "BAGO_INTENT_EXAMPLES_PATH" in intent_engine
    assert "\"/project\"" in command_intents
    assert "analiza el directorio" in command_intents
    assert "analyze_data" in project_memory
    assert "format_analysis" in project_memory


if __name__ == "__main__":
    tests = [
        test_default_auto_allow_tools_is_false,
        test_execute_command_has_no_shell_true,
        test_cors_does_not_allow_wildcard,
        test_cors_allows_only_localhost_origins,
        test_non_localhost_api_requires_token,
        test_release_package_excludes_install_config_and_includes_uninstaller,
        test_repair_only_skips_post_install_tests,
        test_remote_installer_blocks_future_versions,
        test_manager_hides_future_versions,
        test_main_process_hides_future_versions,
        test_manager_surfaces_startup_dependencies_and_provider_onboarding,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")

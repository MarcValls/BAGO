from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"


def test_runtime_service_is_packaged_and_layout_agnostic() -> None:
    service = BACKEND_ROOT / "scripts" / "runtime-service.ps1"
    assert service.is_file()
    text = service.read_text(encoding="utf-8")
    assert "bago_core.launcher" in text
    assert "ui-react\\dist" in text
    assert "backend\\ui-react" not in text


def test_viewer_supports_monorepo_and_flat_runtime_layouts() -> None:
    viewer = (REPOSITORY_ROOT / "electron-viewer" / "main.cjs").read_text(encoding="utf-8")
    assert "describeRuntimeRoot" in viewer
    assert "monorepoBackend" in viewer
    assert "flatBackend" in viewer
    assert "runtime-service.ps1" in viewer
    assert "runRuntimeService('backend')" in viewer
    assert "if (app.isPackaged)" in viewer
    assert "win.loadURL(UI_URL);" in viewer


def test_global_payload_validator_requires_complete_viewer() -> None:
    validator = REPOSITORY_ROOT / "scripts" / "validate_global_payload.ps1"
    assert validator.is_file()
    text = validator.read_text(encoding="utf-8")
    for required in (
        "electron-viewer\\BAGO.exe",
        "electron-viewer\\resources\\app.asar",
        "electron-viewer\\resources\\scripts\\dev.ps1",
        "electron-viewer\\locales\\en-US.pak",
        "scripts\\runtime-service.ps1",
        "scripts\\global-install-shell.ps1",
    ):
        assert required in text


def test_nsis_initializes_plugin_directory_before_extracting_payload() -> None:
    installer = REPOSITORY_ROOT / "releases" / "bago-installer.nsi"
    text = installer.read_text(encoding="utf-8")
    assert text.index("InitPluginsDir") < text.index('SetOutPath "$PLUGINSDIR"')

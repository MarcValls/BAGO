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
        assert "install_config.json" not in names
        assert ".bago/credentials.json" not in names
        assert "bago-uninstall.ps1" in names
        assert "bago-uninstall.cmd" in names


if __name__ == "__main__":
    tests = [
        test_default_auto_allow_tools_is_false,
        test_execute_command_has_no_shell_true,
        test_cors_does_not_allow_wildcard,
        test_cors_allows_only_localhost_origins,
        test_non_localhost_api_requires_token,
        test_release_package_excludes_install_config_and_includes_uninstaller,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")

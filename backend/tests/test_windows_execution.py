from __future__ import annotations

import pytest

import windows_execution


def test_trusted_powershell_uses_only_the_fixed_system_location(tmp_path, monkeypatch):
    expected = tmp_path / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"fixture")
    monkeypatch.setattr(windows_execution, "windows_system_directory", lambda: tmp_path)

    assert windows_execution.trusted_windows_powershell() == expected.resolve()


def test_windows_system_directory_fails_closed_off_windows(monkeypatch):
    monkeypatch.setattr(windows_execution.os, "name", "posix")

    with pytest.raises(OSError, match="unavailable on this platform"):
        windows_execution.trusted_windows_powershell()

from __future__ import annotations

from types import SimpleNamespace

import native_approval


def _challenge() -> dict:
    return {
        "challenge_id": "authch-1", "session_id": "session-1",
        "effect_id": "system.install.apply", "operation_fingerprint": "a" * 64,
        "request_descriptor": {"target": {"install_dir": "C:/Program Files/BAGO"}},
    }


def test_native_confirmation_denies_without_windows(monkeypatch) -> None:
    monkeypatch.setattr(native_approval, "os", SimpleNamespace(name="posix", environ={}))
    assert native_approval.confirm_strong_challenge(_challenge()) is False


def test_native_confirmation_denies_without_input_desktop(monkeypatch) -> None:
    monkeypatch.setattr(native_approval, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(native_approval.ctypes, "WinDLL", lambda _name, **_kwargs: object())
    monkeypatch.setattr(native_approval, "_interactive_desktop_available", lambda _user32, _kernel32: False)
    assert native_approval.confirm_strong_challenge(_challenge()) is False


def test_native_confirmation_denies_when_win32_fails(monkeypatch) -> None:
    monkeypatch.setattr(native_approval, "os", SimpleNamespace(name="nt", environ={}))

    def missing_dll(_name, **_kwargs):
        raise OSError("no desktop")

    monkeypatch.setattr(native_approval.ctypes, "WinDLL", missing_dll)
    assert native_approval.confirm_strong_challenge(_challenge()) is False


def test_native_confirmation_uses_no_as_default_and_shows_operation() -> None:
    assert native_approval._MESSAGE_BOX_FLAGS & 0x00000100
    assert native_approval._MESSAGE_BOX_FLAGS & 0x00000004
    assert native_approval._IDYES == 6

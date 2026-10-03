"""Server-owned Windows confirmation for strong BAGO authorization.

The HTTP channel is only a routing hint. It is never evidence that a person
approved an operation. This module has no Permit or effect authority.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from typing import Any


_UOI_FLAGS = 1
_UOI_IO = 6
_WSF_VISIBLE = 1
_IDYES = 6
_MESSAGE_BOX_FLAGS = 0x00000004 | 0x00000030 | 0x00000100 | 0x00010000 | 0x00040000
_MAX_PREVIEW_LENGTH = 5000


class _UserObjectFlags(ctypes.Structure):
    _fields_ = [
        ("fInherit", wintypes.BOOL),
        ("fReserved", wintypes.BOOL),
        ("dwFlags", wintypes.DWORD),
    ]


def _interactive_desktop_available(user32: Any, kernel32: Any) -> bool:
    user32.GetProcessWindowStation.restype = wintypes.HANDLE
    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    station = user32.GetProcessWindowStation()
    desktop = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    if not station or not desktop:
        return False
    flags = _UserObjectFlags()
    needed = wintypes.DWORD()
    if not user32.GetUserObjectInformationW(
        station, _UOI_FLAGS, ctypes.byref(flags), ctypes.sizeof(flags), ctypes.byref(needed)
    ) or not flags.dwFlags & _WSF_VISIBLE:
        return False
    receiving_input = wintypes.BOOL()
    return bool(user32.GetUserObjectInformationW(
        desktop, _UOI_IO, ctypes.byref(receiving_input),
        ctypes.sizeof(receiving_input), ctypes.byref(needed),
    ) and receiving_input.value)


def confirm_strong_challenge(challenge: dict[str, Any]) -> bool:
    """Ask on the backend's input desktop; fail closed without one."""
    if (
        os.name != "nt"
        or os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}
        or os.environ.get("BAGO_NONINTERACTIVE_APPROVAL") == "1"
    ):
        return False
    descriptor = challenge.get("request_descriptor")
    if not isinstance(descriptor, dict):
        return False
    target = json.dumps(descriptor.get("target"), ensure_ascii=False, indent=2, sort_keys=True)
    preview = (
        "BAGO solicita una autorización fuerte.\n"
        "Aprueba solo si acabas de iniciar esta operación.\n\n"
        f"Efecto: {challenge.get('effect_id', '')}\n"
        f"Sesión: {challenge.get('session_id', '')}\n"
        f"Challenge: {challenge.get('challenge_id', '')}\n"
        f"Operación SHA-256: {challenge.get('operation_fingerprint', '')}\n\n"
        f"Destino:\n{target}"
    )
    if len(preview) > _MAX_PREVIEW_LENGTH:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        if not _interactive_desktop_available(user32, kernel32):
            return False
        user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
        user32.MessageBoxW.restype = ctypes.c_int
        return user32.MessageBoxW(None, preview, "BAGO — autorización fuerte", _MESSAGE_BOX_FLAGS) == _IDYES
    except (AttributeError, OSError, TypeError, ValueError):
        return False

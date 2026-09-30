"""Resolve fixed, OS-owned executables for Windows runtime effects."""
from __future__ import annotations

import ctypes
import os
import stat
from pathlib import Path


def windows_system_directory() -> Path:
    """Ask Windows for the system directory; never trust PATH or SystemRoot."""
    if os.name != "nt":
        raise OSError("Windows system executors are unavailable on this platform")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_system_directory = kernel32.GetSystemDirectoryW
    get_system_directory.argtypes = [ctypes.POINTER(ctypes.c_wchar), ctypes.c_uint]
    get_system_directory.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    size = int(get_system_directory(buffer, len(buffer)))
    if size <= 0 or size >= len(buffer) or not buffer.value:
        raise OSError(ctypes.get_last_error(), "GetSystemDirectoryW failed")
    result = Path(buffer.value).resolve(strict=True)
    if not result.is_dir():
        raise OSError("Windows system directory is not a directory")
    return result


def trusted_windows_powershell() -> Path:
    """Return the protected inbox Windows PowerShell 5.1 executable."""
    system_directory = windows_system_directory()
    powershell = system_directory / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    try:
        for component in (powershell, powershell.parent, powershell.parent.parent):
            metadata = component.lstat()
            if component.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                raise OSError("Windows PowerShell path contains a reparse point")
        metadata = powershell.lstat()
        resolved = powershell.resolve(strict=True)
        expected_parent = (system_directory / "WindowsPowerShell" / "v1.0").resolve(strict=True)
    except OSError as exc:
        raise OSError("Trusted Windows PowerShell is unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or os.path.normcase(str(resolved.parent)) != os.path.normcase(str(expected_parent))
    ):
        raise OSError("Windows PowerShell resolved outside its fixed system location")
    return resolved


__all__ = ["trusted_windows_powershell", "windows_system_directory"]

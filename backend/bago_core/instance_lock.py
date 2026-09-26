"""Process-wide BAGO instance lock for startup coordination."""
from __future__ import annotations

import ctypes
import os
import sys
import time
from pathlib import Path

from bago_core.user_state_paths import bago_lock_file, ensure_user_roots


def _is_pid_alive_windows(pid: int) -> bool:
    process_query_limited_information = 0x1000
    still_active = 259

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    ctypes.set_last_error(0)

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        last_error = ctypes.get_last_error()
        return last_error == 5

    try:
        exit_code = ctypes.c_uint32()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return exit_code.value == still_active
        return True
    finally:
        kernel32.CloseHandle(handle)


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _is_pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_bago_lock() -> tuple[bool, Path, int | None]:
    """Claim the singleton startup lease using exclusive file creation."""
    ensure_user_roots()
    lock_path = bago_lock_file()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if lock_path.exists():
        try:
            payload = lock_path.read_text(encoding="utf-8").strip().splitlines()
            existing_pid = int(payload[0].strip()) if payload and payload[0].strip().isdigit() else None
        except Exception:
            existing_pid = None
        if existing_pid and is_pid_alive(existing_pid):
            return False, lock_path, existing_pid
        try:
            lock_path.unlink()
        except Exception:
            return False, lock_path, existing_pid
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(f"{os.getpid()}\n{time.time()}\n")
        return True, lock_path, None
    except FileExistsError:
        return False, lock_path, None


def release_bago_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


__all__ = ["acquire_bago_lock", "bago_lock_file", "is_pid_alive", "release_bago_lock"]

"""Bounded Windows rename experiment; no BAGO runtime entry point.

Only creates fresh files in a fresh directory under this script's directory.
Does not remove files, change ACLs, elevate, or touch a real repository target.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import platform
import uuid


class RenameInfo(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("RootDirectory", wintypes.HANDLE),
                ("FileNameLength", wintypes.DWORD), ("FileName", wintypes.WCHAR * 1)]


class FileIdInfo(ctypes.Structure):
    _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong),
                ("FileId", ctypes.c_ubyte * 16)]


class IoStatusBlock(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]


def main() -> None:
    if os.name != "nt":
        raise SystemExit("Windows only")
    root = Path(__file__).resolve().parent
    workspace = root.parents[1]
    if root != workspace / "artifacts" / "ieb-decisions-20261001":
        raise SystemExit("Unexpected experiment root")
    sandbox = root / ("run-" + uuid.uuid4().hex)
    sandbox.mkdir(exist_ok=False)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    nt = ctypes.WinDLL("ntdll")
    nt.NtSetInformationFile.argtypes = [wintypes.HANDLE, ctypes.POINTER(IoStatusBlock),
                                      ctypes.c_void_p, wintypes.ULONG, ctypes.c_int]
    nt.NtSetInformationFile.restype = ctypes.c_long
    nt.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
    nt.RtlNtStatusToDosError.restype = wintypes.ULONG
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    k.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                           ctypes.c_void_p, wintypes.DWORD]
    k.SetFileInformationByHandle.restype = wintypes.BOOL
    k.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                             ctypes.c_void_p, wintypes.DWORD]
    k.GetFileInformationByHandleEx.restype = wintypes.BOOL
    k.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    k.ReadFile.restype = wintypes.BOOL
    handles = []
    invalid = ctypes.c_void_p(-1).value

    def open_handle(path, access, share, flags=0x80):
        handle = k.CreateFileW(str(path), access, share, None, 3, flags, None)
        if handle == invalid:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(handle)
        return handle

    def identity(handle):
        data = FileIdInfo()
        if not k.GetFileInformationByHandleEx(handle, 18, ctypes.byref(data), ctypes.sizeof(data)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"volume": data.VolumeSerialNumber, "file_id": bytes(data.FileId).hex()}

    def rename(handle, parent, name, flags):
        encoded = name.encode("utf-16-le")
        size = RenameInfo.FileName.offset + len(encoded)
        buffer = ctypes.create_string_buffer(max(size, ctypes.sizeof(RenameInfo)))
        data = RenameInfo.from_buffer(buffer)
        data.Flags, data.RootDirectory, data.FileNameLength = flags, parent, len(encoded)
        ctypes.memmove(ctypes.addressof(buffer) + RenameInfo.FileName.offset, encoded, len(encoded))
        status_block = IoStatusBlock()
        status = nt.NtSetInformationFile(handle, ctypes.byref(status_block), buffer, size, 65)
        ok = status >= 0
        return {"ok": ok, "ntstatus": f"0x{status & 0xffffffff:08x}",
                "winerror": 0 if ok else nt.RtlNtStatusToDosError(status)}

    results = []
    try:
        for label, share, flags, competitor in [
            ("baseline_relative", None, 1, False),
            ("deny_delete_replace", 1, 1, False),
            ("deny_delete_posix", 1, 3, False),
            ("share_delete_replace", 5, 1, False),
            ("share_delete_posix", 5, 3, False),
            ("share_delete_competitor_then_commit", 5, 3, True),
        ]:
            case = sandbox / label
            case.mkdir()
            target, source, intruder = case / "target.txt", case / "staged.txt", case / "intruder.txt"
            target.write_bytes(b"authorized-before")
            source.write_bytes(b"authorized-after")
            intruder.write_bytes(b"unauthorized-object")
            start = len(handles)
            try:
                parent = open_handle(case, 0x0001 | 0x0002 | 0x0080, 7, 0x02000000)
                held = open_handle(target, 0x80000000, share) if share is not None else None
                before = identity(held) if held else None
                staged = open_handle(source, 0x00010000 | 0x0080, 7)
                attacker_result = None
                if competitor:
                    attacker = open_handle(intruder, 0x00010000 | 0x0080, 7)
                    attacker_result = rename(attacker, parent, "target.txt", 3)
                commit = rename(staged, parent, "target.txt", flags)
                visible = open_handle(target, 0x80000000, 7)
                content = ctypes.create_string_buffer(128)
                read_count = wintypes.DWORD()
                if not k.ReadFile(visible, content, 128, ctypes.byref(read_count), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                results.append({"case": label, "held_share": share, "rename_flags": flags,
                                "authorized_target_id": before,
                                "competitor": attacker_result, "commit": commit,
                                "visible_target_id": identity(visible),
                                "held_identity_after": identity(held) if held else None,
                                "visible_content_hex": content.raw[:read_count.value].hex()})
            finally:
                for handle in handles[start:][::-1]:
                    k.CloseHandle(handle)
                del handles[start:]
    finally:
        for handle in handles[::-1]:
            k.CloseHandle(handle)
    report = {"scope": "bounded native rename observation; not sandbox acceptance",
              "api": "NtSetInformationFile(FileRenameInformationEx=65); relative retained parent",
              "platform": platform.platform(), "python": platform.python_version(),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scratch": str(sandbox.relative_to(workspace)), "cases": results}
    (sandbox / "observations.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

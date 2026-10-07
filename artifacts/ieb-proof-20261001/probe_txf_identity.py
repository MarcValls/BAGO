"""Experimental TxF identity/exclusion proof, confined to freshly created scratch.

Not a BAGO adapter. TxF is deprecated; this experiment does not adopt it.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid


class FileId(ctypes.Structure):
    _fields_ = [("volume", ctypes.c_ulonglong), ("file_id", ctypes.c_ubyte * 16)]


class Rename(ctypes.Structure):
    _fields_ = [("replace", w.BOOLEAN), ("parent", w.HANDLE),
                ("length", w.ULONG), ("name", w.WCHAR * 1)]


class IoStatus(ctypes.Structure):
    _fields_ = [("status", ctypes.c_void_p), ("information", ctypes.c_size_t)]


ROOT = Path(__file__).resolve().parent
if ROOT.name != "ieb-proof-20261001" or ROOT.parent.name != "artifacts":
    raise SystemExit("Unexpected probe root")

k = ctypes.WinDLL("kernel32", use_last_error=True)
t = ctypes.WinDLL("ktmw32", use_last_error=True)
n = ctypes.WinDLL("ntdll")
INVALID = ctypes.c_void_p(-1).value
R, W, D = 0x80000000, 0x40000000, 0x10000
k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
k.CreateFileW.restype = w.HANDLE
k.CreateFileTransactedW.argtypes = k.CreateFileW.argtypes + [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p]
k.CreateFileTransactedW.restype = w.HANDLE
k.CloseHandle.argtypes = [w.HANDLE]
k.CloseHandle.restype = w.BOOL
k.GetFileInformationByHandleEx.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
k.GetFileInformationByHandleEx.restype = w.BOOL
k.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
k.ReadFile.restype = w.BOOL
k.WriteFile.argtypes = k.ReadFile.argtypes
k.WriteFile.restype = w.BOOL
k.MoveFileTransactedW.argtypes = [w.LPCWSTR, w.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, w.DWORD, w.HANDLE]
k.MoveFileTransactedW.restype = w.BOOL
t.CreateTransaction.argtypes = [ctypes.c_void_p, ctypes.c_void_p, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.LPWSTR]
t.CreateTransaction.restype = w.HANDLE
t.CommitTransaction.argtypes = t.RollbackTransaction.argtypes = [w.HANDLE]
t.CommitTransaction.restype = t.RollbackTransaction.restype = w.BOOL
n.NtSetInformationFile.argtypes = [w.HANDLE, ctypes.POINTER(IoStatus), ctypes.c_void_p, w.ULONG, ctypes.c_int]
n.NtSetInformationFile.restype = ctypes.c_long
n.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
n.RtlNtStatusToDosError.restype = w.ULONG
n.RtlSetCurrentTransaction.argtypes = [w.HANDLE]
n.RtlSetCurrentTransaction.restype = w.BOOL


def opened(path, access, tx=None, directory=False):
    args = (str(path), access, 7, None, 3, 0x02000000 if directory else 0x80, None)
    handle = k.CreateFileTransactedW(*args, tx, None, None) if tx else k.CreateFileW(*args)
    if handle == INVALID:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def identity(handle):
    data = FileId()
    if not k.GetFileInformationByHandleEx(handle, 18, ctypes.byref(data), ctypes.sizeof(data)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"volume": data.volume, "file_id": bytes(data.file_id).hex()}


def read(handle):
    buffer, size = ctypes.create_string_buffer(128), w.DWORD()
    if not k.ReadFile(handle, buffer, 128, ctypes.byref(size), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return buffer.raw[:size.value]


def rename(handle, parent, name, transaction):
    raw = name.encode("utf-16-le")
    size = Rename.name.offset + len(raw)
    buffer = ctypes.create_string_buffer(max(size, ctypes.sizeof(Rename)))
    value = Rename.from_buffer(buffer)
    value.replace, value.parent, value.length = True, parent, len(raw)
    ctypes.memmove(ctypes.addressof(buffer) + Rename.name.offset, raw, len(raw))
    if not n.RtlSetCurrentTransaction(transaction):
        raise RuntimeError("Cannot bind native namespace operation to transaction")
    try:
        status = n.NtSetInformationFile(handle, ctypes.byref(IoStatus()), buffer, size, 10)
    finally:
        n.RtlSetCurrentTransaction(None)
    return {"ok": status >= 0, "ntstatus": hex(status & 0xffffffff),
            "winerror": 0 if status >= 0 else n.RtlNtStatusToDosError(status)}


def attack(case, action):
    path = Path(case).resolve()
    path.relative_to(ROOT)
    target = path / "target.txt"
    handle = None
    try:
        if action == "write":
            handle = opened(target, W)
            count = w.DWORD()
            if not k.WriteFile(handle, b"intruder", 8, ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
        elif action == "replace":
            os.replace(path / "intruder.txt", target)
        elif action == "parent_rename":
            os.rename(path, path.with_name(path.name + "-moved"))
        else:
            raise ValueError(action)
        result = {"action": action, "ok": True, "winerror": 0}
    except OSError as exc:
        result = {"action": action, "ok": False, "winerror": exc.winerror}
    finally:
        if handle:
            k.CloseHandle(handle)
    print(json.dumps(result))


def contender(case, action):
    try:
        result = subprocess.run([sys.executable, str(__file__), "--attack", str(case), action],
                                capture_output=True, text=True, timeout=8)
        if result.returncode:
            return {"action": action, "process_error": result.returncode}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"action": action, "timed_out": True, "verdict": "INCONCLUSIVE"}


def visible(path):
    handle = opened(path, R)
    try:
        return {"identity": identity(handle), "digest": hashlib.sha256(read(handle)).hexdigest()}
    finally:
        k.CloseHandle(handle)


def main():
    run = ROOT / ("txf-" + uuid.uuid4().hex)
    run.mkdir(exist_ok=False)
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "TxF native scratch only; no production eligibility", "cases": []}
    for action in ("write", "replace", "parent_rename"):
        control = run / ("control-" + action)
        control.mkdir()
        (control / "target.txt").write_bytes(b"before")
        (control / "intruder.txt").write_bytes(b"intruder")
        report.setdefault("unlocked_controls", []).append(contender(control, action))
    for label, mismatch, rollback in [("commit", False, False), ("identity_drift", True, False),
                                      ("content_drift", False, False), ("rollback", False, True)]:
        case = run / label
        case.mkdir()
        target, staged = case / "target.txt", case / "staged.txt"
        target.write_bytes(b"before")
        staged.write_bytes(b"after")
        (case / "intruder.txt").write_bytes(b"intruder")
        expected_state = visible(target)
        expected = expected_state["identity"]
        if mismatch:
            os.replace(case / "intruder.txt", target)
            (case / "intruder.txt").write_bytes(b"intruder")
        if label == "content_drift":
            target.write_bytes(b"changed-with-same-file-id")
        tx = t.CreateTransaction(None, None, 0, 0, 0, 30000, "BAGO isolated scratch experiment")
        handles, item = [], {"case": label, "expected": expected}
        if tx == INVALID:
            item["error"] = {"stage": "CreateTransaction", "winerror": ctypes.get_last_error()}
            report["cases"].append(item)
            break
        committed = False
        try:
            parent = opened(case, R | W | D, tx, True)
            handles.append(parent)
            held = opened(target, R | W | D, tx)
            handles.append(held)
            item["actual"] = identity(held)
            item["content_digest"] = hashlib.sha256(read(held)).hexdigest()
            if item["actual"] != expected:
                item["admission"] = "DENY_IDENTITY_MISMATCH"
            elif item["content_digest"] != expected_state["digest"]:
                item["admission"] = "DENY_CONTENT_MISMATCH"
            else:
                item["admission"] = "IDENTITY_MATCH"
                item["contenders"] = [contender(case, action) for action in
                                      ("write", "replace", "parent_rename")]
                source = opened(staged, R | W | D, tx)
                handles.append(source)
                item["staged_identity"] = identity(source)
                for handle in handles[::-1]:
                    k.CloseHandle(handle)
                handles.clear()
                item["contenders_after_handle_close"] = [contender(case, action) for action in
                                                          ("write", "replace", "parent_rename")]
                ok = bool(k.MoveFileTransactedW(str(staged), str(target), None, None, 1, tx))
                item["replace"] = {"api": "MoveFileTransactedW", "ok": ok,
                                   "winerror": 0 if ok else ctypes.get_last_error()}
                if ok:
                    item["outside_before_commit"] = visible(target)
                    item["contenders_after_replace"] = [contender(case, action) for action in
                                                        ("write", "replace", "parent_rename")]
                if item["replace"]["ok"] and not rollback:
                    committed = bool(t.CommitTransaction(tx))
                    item["commit"] = {"ok": committed, "winerror": 0 if committed else ctypes.get_last_error()}
        except OSError as exc:
            item["error"] = {"stage": "native_operation", "winerror": exc.winerror}
        finally:
            if not committed:
                item["rollback_ok"] = bool(t.RollbackTransaction(tx))
            for handle in handles[::-1]:
                k.CloseHandle(handle)
            k.CloseHandle(tx)
        item["visible_content_hex"] = target.read_bytes().hex() if target.exists() else None
        if target.exists():
            item["final_state"] = visible(target)
        report["cases"].append(item)
    checks = {
        "unlocked_controls_all_succeed": all(x.get("ok") for x in report.get("unlocked_controls", [])),
        "all_four_cases_complete": len(report["cases"]) == 4,
    }
    by_case = {x["case"]: x for x in report["cases"]}
    good = by_case.get("commit", {})
    checks["positive_commit"] = good.get("commit", {}).get("ok", False) and good.get("visible_content_hex") == b"after".hex()
    checks["committed_identity_is_staged"] = good.get("final_state", {}).get("identity") == good.get("staged_identity")
    checks["old_state_visible_until_commit"] = good.get("outside_before_commit", {}).get("identity") == good.get("expected")
    checks["identity_drift_denied"] = by_case.get("identity_drift", {}).get("admission") == "DENY_IDENTITY_MISMATCH"
    checks["content_drift_denied"] = by_case.get("content_drift", {}).get("admission") == "DENY_CONTENT_MISMATCH"
    checks["rollback_preserves_target"] = by_case.get("rollback", {}).get("visible_content_hex") == b"before".hex() and by_case.get("rollback", {}).get("replace", {}).get("ok", False)
    checks["rollback_preserves_identity"] = by_case.get("rollback", {}).get("final_state", {}).get("identity") == by_case.get("rollback", {}).get("expected")
    attempts = [a for x in report["cases"] for field in ("contenders", "contenders_after_handle_close", "contenders_after_replace") for a in x.get(field, [])]
    checks["all_18_contenders_excluded"] = len(attempts) == 18 and all(a.get("ok") is False and a.get("winerror") in (32, 6800) for a in attempts)
    report["checks"] = checks
    report["verdict"] = "PASS_SCOPED_EXPERIMENT" if all(checks.values()) else "FAIL_OR_UNSUPPORTED"
    report["run"] = str(run)
    (run / "observations.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--attack":
        attack(sys.argv[2], sys.argv[3])
    else:
        main()

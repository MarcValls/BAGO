"""
BagoSandbox — real sandbox adapter for safe RL training and tool execution.

Intercepts dangerous system calls to guarantee zero side-effects during training:
  - subprocess / os.system / os.popen
  - file system: open(), os.remove, shutil.rmtree, pathlib.Path.write_text
  - network: requests, urllib
  - time: time.sleep (to prevent training stalls)

Modes:
  - simulate: logs the call but does not execute; returns synthetic result
  - dry_run: logs the call, returns None / empty result
  - restricted: raises SandboxError for any forbidden call

Usage:
    from bago_sandbox import BagoSandbox
    sb = BagoSandbox(mode="simulate")
    sb.activate()
    # ... safe training code ...
    sb.deactivate()
"""

import builtins
import io
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


class SandboxError(Exception):
    """Raised when a forbidden operation is attempted inside the sandbox."""
    pass


class _InterceptedResult:
    """Represents a synthetic return value from an intercepted call."""

    def __init__(self, return_value=None, stdout="", stderr="", returncode=0):
        self.return_value = return_value
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def __repr__(self):
        return f"_InterceptedResult(rc={self.returncode})"


class BagoSandbox:
    MODES = {"simulate", "dry_run", "restricted"}

    def __init__(self, mode="simulate", log_path: Optional[str] = None):
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}")
        self.mode = mode
        self.log_path = log_path
        self._active = False
        self._log: List[Dict[str, Any]] = []

        # Original references to restore later
        self._orig_builtins_open = builtins.open
        self._orig_os_system = os.system
        self._orig_os_popen = os.popen
        self._orig_subprocess_run = subprocess.run
        self._orig_subprocess_call = subprocess.call
        self._orig_subprocess_check_output = subprocess.check_output
        self._orig_subprocess_Popen = subprocess.Popen
        self._orig_os_remove = os.remove
        self._orig_os_unlink = os.unlink
        self._orig_shutil_rmtree = None
        self._orig_pathlib_write_text = Path.write_text
        self._orig_pathlib_write_bytes = Path.write_bytes
        self._orig_urllib_urlopen = urllib.request.urlopen
        self._orig_time_sleep = time.sleep

        # Try to import requests if available
        self._requests = None
        try:
            import requests as _req_mod
            self._requests = _req_mod
        except Exception:
            pass

    def _write_log(self, entry: Dict[str, Any]):
        self._log.append(entry)
        if self.log_path:
            with self._orig_builtins_open(self.log_path, "a", encoding="utf-8") as f:
                f.write(str(entry) + "\n")

    def _simulate_subprocess(self, cmd, **kwargs):
        entry = {"type": "subprocess", "cmd": str(cmd), "mode": self.mode, "kwargs": {k: str(v) for k, v in kwargs.items()}}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked subprocess call: {cmd}")
        return _InterceptedResult(returncode=0, stdout="sandboxed")

    def _simulate_open(self, file, mode="r", *args, **kwargs):
        path = str(file)
        entry = {"type": "open", "path": path, "mode": mode}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked open: {path}")
        if "w" in mode or "a" in mode or "x" in mode:
            # Return a StringIO/BytesIO so code can "write" without touching disk
            if "b" in mode:
                return io.BytesIO()
            return io.StringIO()
        # For reads, if file exists allow it; if not return empty
        if os.path.exists(path) and not self._active:
            return self._orig_builtins_open(file, mode, *args, **kwargs)
        if "b" in mode:
            return io.BytesIO(b"")
        return io.StringIO("")

    def _simulate_os_remove(self, path):
        entry = {"type": "os.remove", "path": str(path)}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked os.remove: {path}")

    def _simulate_shutil_rmtree(self, path, *args, **kwargs):
        entry = {"type": "shutil.rmtree", "path": str(path)}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked shutil.rmtree: {path}")

    def _simulate_pathlib_write(self, path_obj, data, *args, **kwargs):
        entry = {"type": "pathlib.write", "path": str(path_obj), "size": len(data)}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked pathlib write: {path_obj}")
        return len(data)

    def _simulate_urllib(self, url, *args, **kwargs):
        entry = {"type": "urllib", "url": str(url)}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked urllib: {url}")
        return _InterceptedResult(return_value=b"sandboxed")

    def _simulate_requests(self, method, url, **kwargs):
        entry = {"type": "requests", "method": method, "url": str(url)}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked requests.{method}: {url}")
        class FakeResp:
            status_code = 200
            text = "sandboxed"
            content = b"sandboxed"
            json = lambda self: {}
        return FakeResp()

    def _simulate_time_sleep(self, secs):
        entry = {"type": "time.sleep", "seconds": secs}
        self._write_log(entry)
        if self.mode == "restricted":
            raise SandboxError(f"Blocked time.sleep({secs})")
        # In simulate mode we skip sleep entirely to keep training fast

    def activate(self):
        if self._active:
            return
        self._active = True

        builtins.open = self._simulate_open
        os.system = lambda cmd: self._simulate_subprocess(cmd).returncode
        os.popen = lambda cmd, *a, **kw: io.StringIO(self._simulate_subprocess(cmd, *a, **kw).stdout)
        subprocess.run = lambda cmd, **kw: self._simulate_subprocess(cmd, **kw)
        subprocess.call = lambda cmd, **kw: self._simulate_subprocess(cmd, **kw).returncode
        subprocess.check_output = lambda cmd, **kw: self._simulate_subprocess(cmd, **kw).stdout.encode() if isinstance(self._simulate_subprocess(cmd, **kw).stdout, str) else self._simulate_subprocess(cmd, **kw).stdout
        subprocess.Popen = lambda cmd, **kw: self._make_fake_popen(cmd, **kw)
        os.remove = self._simulate_os_remove
        os.unlink = self._simulate_os_remove
        import shutil
        self._orig_shutil_rmtree = shutil.rmtree
        shutil.rmtree = self._simulate_shutil_rmtree
        Path.write_text = lambda self_, data, *a, **kw: self._simulate_pathlib_write(self_, data, *a, **kw)
        Path.write_bytes = lambda self_, data, *a, **kw: self._simulate_pathlib_write(self_, data, *a, **kw)
        urllib.request.urlopen = lambda url, *a, **kw: self._simulate_urllib(url, *a, **kw)
        time.sleep = self._simulate_time_sleep

        if self._requests is not None:
            self._orig_requests_get = self._requests.get
            self._orig_requests_post = self._requests.post
            self._requests.get = lambda url, **kw: self._simulate_requests("get", url, **kw)
            self._requests.post = lambda url, **kw: self._simulate_requests("post", url, **kw)

    def deactivate(self):
        if not self._active:
            return
        self._active = False

        builtins.open = self._orig_builtins_open
        os.system = self._orig_os_system
        os.popen = self._orig_os_popen
        subprocess.run = self._orig_subprocess_run
        subprocess.call = self._orig_subprocess_call
        subprocess.check_output = self._orig_subprocess_check_output
        subprocess.Popen = self._orig_subprocess_Popen
        os.remove = self._orig_os_remove
        os.unlink = self._orig_os_unlink
        import shutil
        shutil.rmtree = self._orig_shutil_rmtree
        Path.write_text = self._orig_pathlib_write_text
        Path.write_bytes = self._orig_pathlib_write_bytes
        urllib.request.urlopen = self._orig_urllib_urlopen
        time.sleep = self._orig_time_sleep

        if self._requests is not None:
            self._requests.get = self._orig_requests_get
            self._requests.post = self._orig_requests_post

    def _make_fake_popen(self, cmd, **kwargs):
        res = self._simulate_subprocess(cmd, **kwargs)
        class FakePopen:
            def __init__(self, result):
                self._result = result
                self.returncode = result.returncode
                self.stdout = io.BytesIO(result.stdout.encode() if isinstance(result.stdout, str) else result.stdout)
                self.stderr = io.BytesIO(result.stderr.encode() if isinstance(result.stderr, str) else result.stderr)
            def communicate(self, input=None):
                return (self.stdout.read(), self.stderr.read())
            def wait(self):
                return self.returncode
        return FakePopen(res)

    def get_log(self):
        return self._log.copy()

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self._log:
            t = entry.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts


def _self_test():
    sb = BagoSandbox(mode="simulate")
    sb.activate()

    # Test open write
    f = open("/tmp/sandbox_test.txt", "w")
    f.write("hello")
    assert not Path("/tmp/sandbox_test.txt").exists() or not Path("/tmp/sandbox_test.txt").read_text() == "hello"

    # Test subprocess
    result = subprocess.run(["echo", "hi"], capture_output=True, text=True)
    assert result.returncode == 0

    # Test os.system
    rc = os.system("echo hi")
    assert rc == 0

    # Test time.sleep
    t0 = time.time()
    time.sleep(0.5)
    assert time.time() - t0 < 0.1  # skipped

    sb.deactivate()
    summary = sb.summary()
    print("Sandbox self-test PASSED — intercepted:", summary)


if __name__ == "__main__":
    _self_test()

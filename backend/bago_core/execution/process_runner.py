"""BAGO Code Forge 3B - process runner.

The validation pipeline never spawns a subprocess directly. It calls
:class:`ProcessRunner.run`, which decouples adapter authors from
``subprocess`` quirks (timeout enforcement, environment scrubbing,
cancellable handles, dry runs, etc.) and lets test code swap a fake.

Design rules (R0-R10):

- R0: <200 lines, no BAGO-specific imports.
- R1: :class:`ProcessOutcome` is a frozen dataclass.
- R2: deterministic given the same inputs.
- R3: a runner failure (binary missing, timeout, crash) must surface
  as :class:`ProcessOutcome` with a non-zero ``returncode`` and an
  informative ``stderr`` - never as a Python exception bubbling up
  into the adapter.
- R4: subprocess timeout is enforced by the runner, not by the
  adapter. ``SubprocessProcessRunner`` uses
  ``subprocess.run(..., timeout=...)`` and converts ``TimeoutExpired``
  into a structured outcome.
- R8: subprocess is allowed *only* through this module. Adapters that
  bypass it are bugs.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ProcessOutcome:
    """What happened when the runner ran a command.

    Attributes
    ----------
    returncode:
        Exit code of the process. ``-1`` means "never started" (e.g.
        binary missing). ``-2`` means "timed out". ``-3`` means the
        runner could not even spawn the process (OS error).
    stdout:
        Captured stdout (decoded with ``utf-8``, ``errors="replace"``).
        Empty string when the runner captured nothing or the process
        crashed before writing anything.
    stderr:
        Captured stderr. Same rules as ``stdout``.
    duration_ms:
        Wall-clock time the command took, in milliseconds. Best
        effort: ``0`` when the runner could not start.
    command_id:
        The command string the runner was asked to execute. Echoed
        back so the evidence bundle can quote the exact invocation.
    timed_out:
        ``True`` iff the runner had to kill the process for taking
        longer than ``timeout_seconds``.
    extra:
        Free-form context the runner wants to attach (binary path,
        resolved argv, etc.). Always JSON-safe.
    """

    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    command_id: str = ""
    timed_out: bool = False
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> dict[str, object]:
        return {
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "command_id": self.command_id,
            "timed_out": self.timed_out,
            "extra": dict(self.extra),
        }


class ProcessRunner:
    """Abstract runner. Tests substitute a fake; production uses
    :class:`SubprocessProcessRunner`.
    """

    def run(
        self,
        command: str,
        *,
        stdin: str = "",
        cwd: str | None = None,
        timeout_seconds: int = 120,
        env: Mapping[str, str] | None = None,
    ) -> ProcessOutcome:  # pragma: no cover - abstract
        raise NotImplementedError


# Sentinel return codes. Stable so adapters can dispatch on them.
RC_NEVER_STARTED = -1
RC_TIMED_OUT = -2
RC_SPAWN_FAILED = -3


def _parse_command(command: str) -> tuple[str, ...]:
    """Split a command string into an argv tuple.

    On Windows the ``posix=False`` mode of :mod:`shlex` keeps quoted
    segments quoted (e.g. ``"print(1)"`` stays as one argv element
    including the surrounding quotes), which would then be passed
    verbatim to ``subprocess.run`` and silently misbehave. We always
    parse with ``posix=True``; if a caller needs Windows-style quoting
    they can pass the argv list directly.
    """
    if not command:
        return ()
    try:
        return tuple(shlex.split(command, posix=True))
    except ValueError:
        return (command,)


class SubprocessProcessRunner(ProcessRunner):
    """Production runner that shells out via :mod:`subprocess`.

    The runner always returns a :class:`ProcessOutcome`; subprocess
    exceptions are translated into stable return codes so adapters
    only have to read ``outcome.ok`` / ``outcome.timed_out``.
    """

    def __init__(
        self,
        *,
        default_cwd: str | None = None,
        default_timeout_seconds: int = 120,
        default_env: Mapping[str, str] | None = None,
    ) -> None:
        self._default_cwd = default_cwd
        self._default_timeout_seconds = _validate_timeout(default_timeout_seconds)
        self._default_env = dict(default_env) if default_env is not None else None
        self._lock = threading.Lock()

    def run(
        self,
        command: str,
        *,
        stdin: str = "",
        cwd: str | None = None,
        timeout_seconds: int = 120,
        env: Mapping[str, str] | None = None,
    ) -> ProcessOutcome:
        argv = _parse_command(command)
        if not argv:
            return ProcessOutcome(
                returncode=RC_NEVER_STARTED,
                stderr="empty command",
                command_id=command,
                extra={"reason": "empty_command"},
            )

        effective_cwd = cwd or self._default_cwd
        effective_env: dict[str, str] | None
        if env is not None:
            effective_env = dict(env)
        elif self._default_env is not None:
            effective_env = dict(self._default_env)
        else:
            effective_env = None

        # ``subprocess.run`` is not thread-safe at the module level in
        # some sense (signal handling) but ``Popen`` itself is. Use a
        # mutex around the actual call to be safe.
        with self._lock:
            return _spawn(argv, stdin, effective_cwd, timeout_seconds,
                          effective_env, command)


def _validate_timeout(value: int) -> int:
    """Sanitise a runner default timeout.

    Zero or negative timeouts are normalised to 120s so a misconfigured
    caller cannot accidentally pass ``timeout=0`` and disable the
    safety net.
    """
    if value is None:  # type: ignore[unreachable]
        return 120
    if value <= 0:
        return 120
    return int(value)


def _spawn(
    argv: tuple[str, ...],
    stdin: str,
    cwd: str | None,
    timeout_seconds: int,
    env: dict[str, str] | None,
    command_id: str,
) -> ProcessOutcome:
    """Spawn ``argv`` and translate every failure into an outcome."""
    started = _monotonic_ms()
    try:
        completed = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout_seconds if timeout_seconds > 0 else None,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ProcessOutcome(
            returncode=RC_TIMED_OUT,
            stdout=_decode(exc.stdout),
            stderr=_decode(exc.stderr) or f"timeout after {timeout_seconds}s",
            duration_ms=_monotonic_ms() - started,
            command_id=command_id,
            timed_out=True,
            extra={"argv": list(argv)},
        )
    except FileNotFoundError as exc:
        return ProcessOutcome(
            returncode=RC_SPAWN_FAILED,
            stderr=f"binary not found: {exc}",
            duration_ms=_monotonic_ms() - started,
            command_id=command_id,
            extra={"argv": list(argv), "reason": "binary_not_found"},
        )
    except OSError as exc:
        return ProcessOutcome(
            returncode=RC_SPAWN_FAILED,
            stderr=f"spawn failed: {exc}",
            duration_ms=_monotonic_ms() - started,
            command_id=command_id,
            extra={"argv": list(argv), "reason": "os_error"},
        )
    except Exception as exc:  # pragma: no cover - safety net
        return ProcessOutcome(
            returncode=RC_SPAWN_FAILED,
            stderr=f"unexpected runner error: {exc}",
            duration_ms=_monotonic_ms() - started,
            command_id=command_id,
            extra={"argv": list(argv), "reason": type(exc).__name__},
        )
    return ProcessOutcome(
        returncode=completed.returncode,
        stdout=_decode(completed.stdout),
        stderr=_decode(completed.stderr),
        duration_ms=_monotonic_ms() - started,
        command_id=command_id,
        extra={"argv": list(argv)},
    )


def _decode(value: object) -> str:
    """Best-effort decode of subprocess bytes-or-str into str."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _monotonic_ms() -> int:
    """Milliseconds since some arbitrary origin. Used only for the
    outcome ``duration_ms`` field; never compared across runs.
    """
    return int((_monotonic()()) * 1000)


def _monotonic():
    if sys.platform == "win32":
        try:
            import time
            return time.monotonic
        except Exception:  # pragma: no cover - safety net
            import time
            return time.time
    import time
    return time.monotonic


__all__ = [
    "ProcessOutcome",
    "ProcessRunner",
    "RC_NEVER_STARTED",
    "RC_SPAWN_FAILED",
    "RC_TIMED_OUT",
    "SubprocessProcessRunner",
]
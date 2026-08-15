"""Safe non-interactive helpers shared by CLI-backed provider adapters."""

from __future__ import annotations

import shutil
import subprocess
import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path


def find_cli(name: str, configured_path: str = "") -> str:
    if configured_path:
        return configured_path
    return shutil.which(name) or ""


def build_prompt(messages: list[dict], system: str = "") -> str:
    payload = {
        "instruction": (
            "Work on the final user request directly in the active workspace. "
            "When the user asks to create, modify, or validate a project, inspect and edit files "
            "and run the required checks. Keep changes inside the authorized workspace and report "
            "what was executed. For questions that do not request changes, answer directly."
        ),
        "system": system,
        "messages": [
            {"role": str(message.get("role", "user")), "content": str(message.get("content", ""))}
            for message in messages
            if message.get("content")
        ],
    }
    return "BAGO_PROVIDER_BRIDGE_JSON=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _run_cli_with_activity(
    command: list[str],
    cwd: str | Path,
    timeout: float,
    input_text: str | None,
    on_activity: Callable[[], None],
) -> subprocess.CompletedProcess[str]:
    """Run a CLI while treating ``timeout`` as an inactivity timeout."""
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if input_text is not None and process.stdin is not None:
        process.stdin.write(input_text)
        process.stdin.close()

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    activity_lock = threading.Lock()
    last_activity = time.monotonic()
    last_callback = last_activity

    def _touch() -> None:
        nonlocal last_activity, last_callback
        with activity_lock:
            last_activity = time.monotonic()
            last_callback = last_activity
        try:
            on_activity()
        except Exception:
            pass

    def _drain(stream, sink: list[str]) -> None:
        if stream is None:
            return
        notify_interval = max(min(timeout / 3.0, 1.0), 0.01) if timeout > 0 else 1.0
        last_notified = 0.0
        for character in iter(lambda: stream.read(1), ""):
            sink.append(character)
            now = time.monotonic()
            if not character.isspace() and now - last_notified >= notify_interval:
                last_notified = now
                _touch()
        stream.close()

    readers = [
        threading.Thread(target=_drain, args=(process.stdout, stdout_lines), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr_lines), daemon=True),
    ]
    for reader in readers:
        reader.start()

    started = time.monotonic()
    # Launching the authenticated CLI is itself observable progress. Codex can
    # spend minutes initializing its runtime before the first JSONL event.
    try:
        on_activity()
    except Exception:
        pass
    hard_timeout = max(timeout * 10.0, 1800.0) if timeout > 0 else 0.0
    heartbeat_interval = max(min(timeout / 3.0, 30.0), 0.01) if timeout > 0 else 30.0
    timed_out = False
    while process.poll() is None:
        now = time.monotonic()
        with activity_lock:
            idle_for = now - last_activity
            heartbeat_due = now - last_callback >= heartbeat_interval
            if heartbeat_due:
                last_callback = now
        if heartbeat_due:
            # Process liveness renews only the outer request watchdog. The
            # CLI's own output timeout below remains authoritative for a
            # genuinely stuck child.
            try:
                on_activity()
            except Exception:
                pass
        if (timeout > 0 and idle_for >= timeout) or (hard_timeout > 0 and now - started >= hard_timeout):
            timed_out = True
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            if process.poll() is None:
                process.kill()
            break
        time.sleep(0.05)

    process.wait()
    for reader in readers:
        reader.join(timeout=2)
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout)
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        "".join(stdout_lines),
        "".join(stderr_lines),
    )


def run_cli(
    command: list[str],
    cwd: str | Path,
    timeout: float = 180.0,
    input_text: str | None = None,
    on_activity: Callable[[], None] | None = None,
) -> str:
    if on_activity is None:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    else:
        result = _run_cli_with_activity(command, cwd, timeout, input_text, on_activity)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        lines = [line.strip() for line in detail.splitlines() if line.strip()]
        visible_lines = [
            line for line in lines
            if not line.startswith("BAGO_PROVIDER_BRIDGE_JSON=") and len(line) <= 1200
        ]
        decisive = [line for line in visible_lines if "error" in line.lower() or "limit" in line.lower()]
        detail = "\n".join((decisive or visible_lines[-4:] or lines[-1:])[-4:])
        raise RuntimeError(detail)
    return (result.stdout or result.stderr).strip()

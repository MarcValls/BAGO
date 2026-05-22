#!/usr/bin/env python3
"""
bago_context.py — BAGO v3.0 Shared Context Service

Singleton context object: path resolution, state management,
centralized logging, tool execution, and event bus.

This file lives at .bago/core/bago_context.py
BAGO_ROOT is resolved as: parents[0]=core  parents[1]=.bago  parents[2]=bago_root

Usage in any tool:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
    from bago_context import get_context

    ctx = get_context()
    print(ctx.version)            # "2.6-taxonomy"
    ctx.log("info", "started")
    ctx.emit("health:degraded", {"score": 75})
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ── Root resolution ────────────────────────────────────────────────────────────
_THIS_FILE   = Path(__file__).resolve()
_DEFAULT_ROOT = _THIS_FILE.parents[2]          # core → .bago → bago_root
BAGO_ROOT: Path = Path(os.environ.get("BAGO_PADRE_PATH") or _DEFAULT_ROOT)

_STATE_PATH  = BAGO_ROOT / ".bago" / "state" / "global_state.json"
_EVENTS_PATH = BAGO_ROOT / ".bago" / "state" / "events.jsonl"
_LOG_PATH    = BAGO_ROOT / ".bago" / "state" / "bago_context.log"


# ── Core class ─────────────────────────────────────────────────────────────────

class BagoContext:
    """
    Shared context for BAGO tools and launcher.

    Provides:
    - Canonical path resolution (root, tools_dir, bago_bin …)
    - Lazy state load + atomic patch writes
    - Structured log (bago_context.log)
    - Subprocess wrapper for bago sub-commands
    - In-process + file-based event bus
    """

    _write_lock = threading.Lock()

    def __init__(self) -> None:
        self.root: Path      = BAGO_ROOT
        self.state_path: Path = _STATE_PATH
        self.tools_dir: Path  = self.root / ".bago" / "tools"
        self.core_dir: Path   = self.root / ".bago" / "core"
        self.bago_bin: Path   = self.root / "bago"
        self._state: dict | None = None
        self._handlers: dict[str, list[Callable[[dict], None]]] = {}

    # ── State ──────────────────────────────────────────────────────────────────

    @property
    def state(self) -> dict:
        if self._state is None:
            self.reload_state()
        return self._state  # type: ignore[return-value]

    @property
    def version(self) -> str:
        return self.state.get("bago_version", self.state.get("version", "unknown"))

    def reload_state(self) -> dict:
        """Re-read global_state.json from disk and update internal cache."""
        try:
            self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            self._state = {}
        return self._state

    def write_state(self, patch: dict) -> None:
        """
        Merge *patch* into the persisted state (read-modify-write).
        Thread-safe. Does not clobber unrelated keys.
        """
        with self._write_lock:
            current: dict = {}
            if self.state_path.exists():
                try:
                    current = json.loads(self.state_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            current.update(patch)
            self.state_path.write_text(
                json.dumps(current, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._state = current

    # ── Logging ────────────────────────────────────────────────────────────────

    def log(self, level: str, msg: str, tool: str = "") -> None:
        """Append a structured JSON entry to bago_context.log."""
        entry = {
            "ts":    datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "tool":  tool,
            "msg":   msg,
        }
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # logging must never crash a tool

    # ── Tool execution ─────────────────────────────────────────────────────────

    def run_tool(self, cmd: str, args: list[str] = (), timeout: int = 60) -> tuple[int, str]:
        """
        Run `bago <cmd> [args]` as a subprocess.
        Returns (returncode, combined_output).
        """
        try:
            result = subprocess.run(
                [sys.executable, str(self.bago_bin), cmd, *args],
                capture_output=True, text=True, timeout=timeout,
                cwd=str(self.root), stdin=subprocess.DEVNULL,
            )
            return result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return -1, f"Timeout after {timeout}s"
        except Exception as exc:
            return -1, str(exc)

    # ── Event bus ──────────────────────────────────────────────────────────────

    def on(self, event: str, handler: Callable[[dict], None]) -> None:
        """Register an in-process handler for *event*."""
        self._handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, data: dict | None = None) -> None:
        """
        Emit *event* with optional *data*.

        - Fires all registered in-process handlers immediately.
        - Appends the event to events.jsonl for cross-process consumption.
        """
        payload: dict[str, Any] = {
            "event": event,
            "data":  data or {},
            "ts":    datetime.now(timezone.utc).isoformat(),
        }
        # In-process handlers
        for handler in self._handlers.get(event, []):
            try:
                handler(payload)
            except Exception:
                pass
        # Cross-process persistence
        try:
            _EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _EVENTS_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def flush_events(self, clear: bool = True) -> list[dict]:
        """
        Read pending events from events.jsonl, fire handlers, optionally clear.
        Called by the launcher after each tool subprocess exits.
        """
        if not _EVENTS_PATH.exists():
            return []
        events: list[dict] = []
        try:
            lines = _EVENTS_PATH.read_text(encoding="utf-8").strip().splitlines()
            for line in lines:
                try:
                    ev = json.loads(line)
                    events.append(ev)
                    for handler in self._handlers.get(ev.get("event", ""), []):
                        try:
                            handler(ev)
                        except Exception:
                            pass
                except Exception:
                    pass
            if clear and events:
                _EVENTS_PATH.unlink()
        except Exception:
            pass
        return events


# ── Singleton ──────────────────────────────────────────────────────────────────

_instance: BagoContext | None = None
_singleton_lock = threading.Lock()


def get_context() -> BagoContext:
    """Return the process-wide BagoContext singleton."""
    global _instance
    if _instance is None:
        with _singleton_lock:
            if _instance is None:
                _instance = BagoContext()
    return _instance


# ── Convenience shortcuts ──────────────────────────────────────────────────────

def get_state() -> dict:
    """Shortcut: return BAGO global state dict."""
    return get_context().state


def get_root() -> Path:
    """Shortcut: return BAGO_ROOT path."""
    return get_context().root


def get_version() -> str:
    """Shortcut: return bago_version string."""
    return get_context().version


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ctx = get_context()
    print(f"BAGO_ROOT  : {ctx.root}")
    print(f"version    : {ctx.version}")
    print(f"state_path : {ctx.state_path} (exists={ctx.state_path.exists()})")
    print(f"tools_dir  : {ctx.tools_dir} (exists={ctx.tools_dir.exists()})")
    print(f"bago_bin   : {ctx.bago_bin} (exists={ctx.bago_bin.exists()})")

    # Event bus smoke test
    received: list[dict] = []
    ctx.on("test:ping", received.append)
    ctx.emit("test:ping", {"hello": "world"})
    assert received, "In-process handler not called"
    print(f"event bus  : OK (received {len(received)} event)")

    # Singleton test
    ctx2 = get_context()
    assert ctx is ctx2, "Singleton broken"
    print("singleton  : OK")
    print("✅ bago_context self-test passed")

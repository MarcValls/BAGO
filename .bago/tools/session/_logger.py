#!/usr/bin/env python3
"""session_logger.py — Log estructurado de ejecuciones BAGO.

Registra cada invocación de `bago <cmd>` en:
    ~/.bago/sessions/YYYY-MM-DD-<uuid8>.json
    (o $XDG_DATA_HOME/bago/sessions/ si XDG_DATA_HOME está definido)

Formato del log:
    {
      "session_id":  "abc12345",
      "cmd":         "cosecha",
      "module":      "cosecha",
      "args":        ["--dry"],
      "status":      "ok" | "error" | "infra-fail" | "running",
      "exit_code":   0,
      "start_time":  "2026-04-23T14:30:00.123456",
      "end_time":    "2026-04-23T14:30:02.456789",
      "duration_s":  2.333,
      "tool_sha256": "a1b2c3d4e5f6a7b8",
      "stderr_tail": "..."
    }

Reemplaza banners estáticos con provenance real de cada ejecución.

Uso:
    python3 session_logger.py              # últimas 5 sesiones
    python3 session_logger.py --last       # últimas 5 sesiones
    python3 session_logger.py --last 10    # últimas N sesiones
    python3 session_logger.py --history    # estadísticas de todas las sesiones
    python3 session_logger.py --test       # self-tests (8/8)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent

# Detect BAGO_ROOT from tool location (repo or installed)
_BAGO_ROOT = TOOLS_DIR.parent

# Priority for session storage:
#   1. BAGO_ROOT/state/sessions  (if writable — active install)
#   2. ~/.bago/sessions          (fallback)
#   3. $XDG_DATA_HOME/bago/sessions (env override, highest priority)
_xdg = os.environ.get("XDG_DATA_HOME")
if _xdg:
    SESSION_BASE: Path = Path(_xdg) / "bago" / "sessions"
elif (_BAGO_ROOT / "state").exists():
    # Active BAGO install — try to write alongside the framework
    _candidate = _BAGO_ROOT / "state" / "sessions"
    try:
        _candidate.mkdir(parents=True, exist_ok=True)
        SESSION_BASE = _candidate
    except OSError:
        # No write permission in Program Files — fallback to home
        SESSION_BASE = Path.home() / ".bago" / "sessions"
else:
    SESSION_BASE = Path.home() / ".bago" / "sessions"


# ── Record ────────────────────────────────────────────────────────────────────

@dataclass
class _Record:
    session_id: str
    cmd: str
    module: str
    args: list[str]
    status: str = "running"
    exit_code: int | None = None
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str | None = None
    duration_s: float | None = None
    tool_sha256: str = ""
    stderr_tail: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "cmd": self.cmd,
            "module": self.module,
            "args": self.args,
            "status": self.status,
            "exit_code": self.exit_code,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_s": self.duration_s,
            "tool_sha256": self.tool_sha256,
            "stderr_tail": self.stderr_tail,
        }


# ── Logger ────────────────────────────────────────────────────────────────────

class SessionLogger:
    """Records a single bago CLI invocation to ~/.bago/sessions/."""

    def __init__(self, cmd: str, args: list[str], module: str = "") -> None:
        self._id = uuid.uuid4().hex[:8]
        self._start = time.monotonic()
        self._record = _Record(
            session_id=self._id,
            cmd=cmd,
            module=module or cmd,
            args=list(args),
            tool_sha256=self._tool_hash(module or cmd),
        )
        # Create session dir silently — never block tool execution
        try:
            SESSION_BASE.mkdir(parents=True, exist_ok=True)
            date = datetime.now().strftime("%Y-%m-%d")
            self._log_path: Path | None = SESSION_BASE / f"{date}-{self._id}.json"
            self._write()  # write "running" record immediately
        except Exception:
            self._log_path = None

    @staticmethod
    def _tool_hash(module: str) -> str:
        candidates = [TOOLS_DIR / f"{module}.py", TOOLS_DIR / module / "__main__.py"]
        for tool_path in candidates:
            if tool_path.exists():
                return hashlib.sha256(tool_path.read_bytes()).hexdigest()[:16]
        return "unknown"

    def _write(self) -> None:
        if self._log_path is None:
            return
        try:
            self._log_path.write_text(json.dumps(self._record.to_dict(), indent=2))
        except Exception:
            pass  # Never block tool execution due to logging failure

    def success(self, stderr_tail: str = "") -> None:
        """Mark the session as successfully completed."""
        self._record.status = "ok"
        self._record.exit_code = 0
        self._record.end_time = datetime.now().isoformat()
        self._record.duration_s = round(time.monotonic() - self._start, 3)
        self._record.stderr_tail = (stderr_tail or "")[-500:]
        self._write()

    def failure(self, exit_code: int = 1, stderr_tail: str = "") -> None:
        """Mark the session as failed.

        exit_code=1  → status="error"    (policy failure)
        exit_code=2  → status="infra-fail" (infrastructure failure)
        """
        self._record.status = "infra-fail" if exit_code == 2 else "error"
        self._record.exit_code = exit_code
        self._record.end_time = datetime.now().isoformat()
        self._record.duration_s = round(time.monotonic() - self._start, 3)
        self._record.stderr_tail = (stderr_tail or "")[-500:]
        self._write()

    @property
    def session_id(self) -> str:
        return self._id

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def load_recent(n: int = 5) -> list[dict]:
        """Return the last N session records, newest first."""
        if not SESSION_BASE.exists():
            return []
        logs = sorted(SESSION_BASE.glob("*.json"), reverse=True)
        results: list[dict] = []
        for log in logs:
            if len(results) >= n:
                break
            try:
                results.append(json.loads(log.read_text()))
            except Exception:
                pass
        return results

    @staticmethod
    def all_logs() -> list[Path]:
        """Return all session log paths, newest first."""
        if not SESSION_BASE.exists():
            return []
        return sorted(SESSION_BASE.glob("*.json"), reverse=True)


# ── CLI helpers ───────────────────────────────────────────────────────────────

_STATUS_ICON = {
    "ok": "✅",
    "error": "❌",
    "infra-fail": "⚠️ ",
    "running": "🔄",
}


def _cmd_last(n: int = 5) -> None:
    records = SessionLogger.load_recent(n)
    if not records:
        print(f"  No hay sesiones registradas en {SESSION_BASE}")
        return
    print(f"  Últimas {len(records)} sesiones BAGO  (log: {SESSION_BASE})")
    print(f"  {'ID':<10} {'CMD':<18} {'STATUS':<12} {'DUR':>7}  FECHA")
    print("  " + "─" * 62)
    for r in records:
        icon = _STATUS_ICON.get(r.get("status", ""), "?")
        dur = f"{r.get('duration_s','?')}s" if r.get("duration_s") is not None else "  ?"
        ts = (r.get("start_time") or "")[:19].replace("T", " ")
        print(f"  {r.get('session_id','?'):<10} {r.get('cmd','?'):<18} "
              f"{icon} {r.get('status',''):<10} {dur:>7}  {ts}")


def _cmd_history() -> None:
    logs = SessionLogger.all_logs()
    if not logs:
        print(f"  No hay sesiones registradas en {SESSION_BASE}")
        return
    stats: dict[str, int] = {}
    cmds: dict[str, int] = {}
    for log in logs:
        try:
            r = json.loads(log.read_text())
            status = r.get("status", "unknown")
            stats[status] = stats.get(status, 0) + 1
            cmd = r.get("cmd", "unknown")
            cmds[cmd] = cmds.get(cmd, 0) + 1
        except Exception:
            pass
    print(f"  Historial BAGO — {len(logs)} sesiones en {SESSION_BASE}")
    print()
    print("  Por status:")
    for status in ("ok", "error", "infra-fail", "running", "unknown"):
        count = stats.get(status, 0)
        if count:
            icon = _STATUS_ICON.get(status, "?")
            print(f"    {icon} {status:<14} {count:>4}")
    print()
    print("  Comandos más usados:")
    for cmd, count in sorted(cmds.items(), key=lambda x: -x[1])[:10]:
        print(f"    {'bago ' + cmd:<22} {count:>4}x")


# ── Self-tests ────────────────────────────────────────────────────────────────

def _self_tests() -> None:
    import tempfile
    results: list[dict] = []

    def _check(name: str, cond: bool, msg: str) -> None:
        results.append({"name": name, "passed": cond, "message": msg})
        print(f"  {'✅' if cond else '❌'} {name}: {msg}")

    import sys as _sys
    _this = _sys.modules[__name__]  # works whether run as __main__ or imported

    with tempfile.TemporaryDirectory() as tmpdir:
        orig_base = _this.SESSION_BASE
        _this.SESSION_BASE = Path(tmpdir) / "sessions"

        # T1: SessionLogger creates a log file on init
        sl = SessionLogger("test-cmd", ["--dry"], "cosecha")
        log_files = list(_this.SESSION_BASE.glob("*.json"))
        _check("T1:log-created-on-init", len(log_files) == 1,
               f"1 log file created ({len(log_files)} found)")

        # T2: initial status is "running"
        data = json.loads(log_files[0].read_text())
        _check("T2:initial-status-running", data["status"] == "running",
               f"status={data['status']}")

        # T3: success() updates status to "ok"
        sl.success()
        data = json.loads(log_files[0].read_text())
        _check("T3:success-status-ok", data["status"] == "ok",
               f"status={data['status']}")

        # T4: duration_s is set after success
        _check("T4:duration-set", data["duration_s"] is not None,
               f"duration_s={data['duration_s']}")

        # T5: failure() with exit_code=1 → status="error"
        sl2 = SessionLogger("test-fail", [], "audit_v2")
        sl2.failure(exit_code=1, stderr_tail="something broke")
        data2 = json.loads(sl2._log_path.read_text())
        _check("T5:failure-exit1-error", data2["status"] == "error",
               f"status={data2['status']}")

        # T6: stderr_tail is captured
        _check("T6:stderr-tail-captured",
               "something broke" in (data2.get("stderr_tail") or ""),
               f"stderr_tail={data2.get('stderr_tail','')[:30]!r}")

        # T7: exit_code=2 → status="infra-fail"
        sl3 = SessionLogger("test-infra", [], "ci_generator")
        sl3.failure(exit_code=2)
        data3 = json.loads(sl3._log_path.read_text())
        _check("T7:exit2-infra-fail", data3["status"] == "infra-fail",
               f"status={data3['status']}")

        # T8: load_recent returns all records (newest first)
        records = SessionLogger.load_recent(n=10)
        _check("T8:load-recent-works", len(records) >= 3,
               f"{len(records)} records loaded (expected ≥3)")

        _this.SESSION_BASE = orig_base

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n  {passed}/{total} tests pasaron")
    print(json.dumps({"tool": "session_logger", "status": "ok" if passed == total else "fail",
                      "checks": results}))
    sys.exit(0 if passed == total else 1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv=None) -> None:
    args = sys.argv[1:] if argv is None else list(argv)
    if "--test" in args:
        _self_tests()
    elif "--history" in args:
        _cmd_history()
    elif "--last" in args:
        idx = args.index("--last")
        n_str = args[idx + 1] if idx + 1 < len(args) and args[idx + 1].isdigit() else "5"
        _cmd_last(int(n_str))
    else:
        _cmd_last()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""BAGO runtime wrapper for the working tree.

Maintains durable project state under `.bago/` so that long-running work
survives between Pi/Codex sessions.  It is intentionally small: it does not
create authority, only records authority already present in the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    # The wrapper lives at <repo>/.bago/bin/bago.py
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "backend").is_dir() or (candidate / ".bago").is_dir():
        return candidate
    # Fallback to Git root if the script was moved.
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    raise RuntimeError("Cannot determine repository root")


def _bago_dir() -> Path:
    return _repo_root() / ".bago"


def _paths() -> dict[str, Path]:
    root = _bago_dir()
    return {
        "context": root / "context" / "PROJECT_CONTEXT.md",
        "state": root / "state" / "PROJECT_STATE.json",
        "handoff": root / "runtime" / "ACTIVE_HANDOFF.md",
        "decisions": root / "decisions" / "DECISIONS.md",
        "conflicts": root / "conflicts" / "CONFLICTS.md",
    }


def _ensure_dirs() -> None:
    for sub in ("bin", "context", "state/agents", "runtime", "decisions", "conflicts"):
        (_bago_dir() / sub).mkdir(parents=True, exist_ok=True)


def _git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_fingerprint() -> dict[str, Any]:
    commit = _git_text("rev-parse", "HEAD") or None
    branch = _git_text("rev-parse", "--abbrev-ref", "HEAD") or None
    remote = _git_text("remote", "get-url", "origin") or None
    upstream = _git_text("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or None
    status = _git_text("status", "--porcelain=v1", "--untracked-files=all")
    tracked = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=_repo_root(), capture_output=True, check=False
    ).stdout
    digest = hashlib.sha256(tracked + status.encode("utf-8")).hexdigest()
    return {
        "commit": commit,
        "branch": branch,
        "remote": remote,
        "upstream": upstream,
        "dirty": bool(status),
        "worktree_sha256": digest,
    }


def _load_state() -> dict[str, Any]:
    path = _paths()["state"]
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "version": "",
        "status": "idle",
        "note": "",
        "updated_at": "",
        "commit": None,
        "branch": None,
        "last_verification": None,
    }


def _save_state(state: dict[str, Any]) -> None:
    _ensure_dirs()
    _paths()["state"].write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _print_file(path: Path, label: str) -> None:
    print(f"\n=== {label}: {path} ===")
    if path.is_file():
        print(path.read_text(encoding="utf-8"))
    else:
        print("(not created)")


def cmd_status(_args: argparse.Namespace) -> int:
    state = _load_state()
    fp = _git_fingerprint()
    dirty = bool(fp.get("dirty"))
    recorded = state.get("fingerprint") or {}
    stale = bool(recorded) and recorded != fp
    claimed_status = str(state.get("status", "idle"))
    effective_status = "STALE" if claimed_status.upper() in {"VERIFIED", "VALIDATED"} and (dirty or stale) else claimed_status

    print(f"Repository: {_repo_root()}")
    print(f"Branch:     {fp.get('branch') or '?'}")
    print(f"Commit:     {fp.get('commit') or '?'}")
    print(f"Dirty:      {'yes' if dirty else 'no'}")
    print(f"Status:     {effective_status}")
    if effective_status == "STALE":
        print(f"Recorded:   {claimed_status} (invalidated by candidate drift)")
    print(f"Note:       {state.get('note', '')}")
    print(f"Updated:    {state.get('updated_at', '')}")
    if state.get("last_verification"):
        v = state["last_verification"]
        print(f"Last verify: {v.get('command')} -> rc={v.get('returncode')} at {v.get('timestamp')}")

    _print_file(_paths()["context"], "Context")
    _print_file(_paths()["handoff"], "Handoff")
    _print_file(_paths()["decisions"], "Decisions")
    _print_file(_paths()["conflicts"], "Conflicts")
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    state = _load_state()
    fp = _git_fingerprint()
    state["status"] = args.status
    state["note"] = args.note
    state["updated_at"] = _iso_now()
    state["commit"] = fp.get("commit")
    state["branch"] = fp.get("branch")
    state["fingerprint"] = fp
    _save_state(state)
    print(f"State updated: {args.status}")
    if args.note:
        print(f"Note: {args.note}")
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    path = _paths()["handoff"]
    _ensure_dirs()
    if args.message is not None:
        header = f"# Active handoff\n\nUpdated: {_iso_now()}\n\n"
        path.write_text(header + args.message + "\n", encoding="utf-8")
        print("Handoff updated")
        return 0
    _print_file(path, "Handoff")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("error: verify requires a command after '--'", file=sys.stderr)
        return 2

    print(f"verify: {' '.join(command)}")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    state = _load_state()
    fp = _git_fingerprint()
    state["last_verification"] = {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout": result.stdout[:2000] if result.stdout else "",
        "stderr": result.stderr[:2000] if result.stderr else "",
        "commit": fp.get("commit"),
        "fingerprint": fp,
        "timestamp": _iso_now(),
    }
    state["fingerprint"] = fp
    if result.returncode != 0:
        state["status"] = "EXECUTED"
        state["note"] = f"Verification failed (rc={result.returncode}); previous verification invalidated."
    elif fp.get("dirty"):
        state["status"] = "EXECUTED"
        state["note"] = "Verification command passed on a dirty candidate; global VERIFIED is not permitted."
    _save_state(state)
    return result.returncode


def cmd_init(_args: argparse.Namespace) -> int:
    _ensure_dirs()
    for label, path in _paths().items():
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            if label in ("decisions", "conflicts"):
                path.write_text(f"# {label.capitalize()}\n\n", encoding="utf-8")
            elif label == "handoff":
                path.write_text("# Active handoff\n\n", encoding="utf-8")
    print("BAGO runtime directories initialized")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bago.py",
        description="BAGO working-tree runtime wrapper.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show repository and BAGO state")

    state_parser = sub.add_parser("state", help="Update lifecycle state")
    state_parser.add_argument("status", help="Status label (e.g. PREPARED, EXECUTED)")
    state_parser.add_argument("--note", default="", help="Free-form note")

    handoff_parser = sub.add_parser("handoff", help="Read or update durable handoff")
    handoff_parser.add_argument("--set", dest="message", default=None, help="Set handoff text")

    verify_parser = sub.add_parser("verify", help="Run a verification command and record it")
    verify_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run (use -- before the command)",
    )

    sub.add_parser("init", help="Create missing .bago directories and empty files")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 2

    dispatch = {
        "status": cmd_status,
        "state": cmd_state,
        "handoff": cmd_handoff,
        "verify": cmd_verify,
        "init": cmd_init,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

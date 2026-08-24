#!/usr/bin/env python3
"""Run one gate and persist raw, candidate-bound evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout.strip() if result.returncode == 0 else ""


def fingerprint() -> dict:
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    patch = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=ROOT, capture_output=True).stdout
    return {
        "sha": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "remote": git("remote", "get-url", "origin"),
        "upstream": git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
        "dirty": bool(status),
        "worktree_sha256": hashlib.sha256(patch + status.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("command required after --")
    if os.name == "nt" and command[0].lower() in {"npm", "npx", "yarn", "pnpm"}:
        command[0] += ".cmd"
    started = datetime.now(timezone.utc).isoformat()
    before = fingerprint()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    finished = datetime.now(timezone.utc).isoformat()
    after = fingerprint()
    evidence_dir = ROOT / ".bago" / "evidence" / "remediation-gates"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in args.name)
    stdout_path = evidence_dir / f"{safe_name}.stdout.log"
    stderr_path = evidence_dir / f"{safe_name}.stderr.log"
    metadata_path = evidence_dir / f"{safe_name}.json"
    stdout_path.write_text(result.stdout, encoding="utf-8", newline="\n")
    stderr_path.write_text(result.stderr, encoding="utf-8", newline="\n")
    metadata = {
        "contract": "bago.gate-evidence.v1",
        "name": args.name,
        "command": command,
        "exit_code": result.returncode,
        "started_at": started,
        "finished_at": finished,
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "candidate_before": before,
        "candidate_after": after,
        "candidate_stable": before == after,
        "stdout": stdout_path.name,
        "stderr": stderr_path.name,
        "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    print(json.dumps({"gate": args.name, "exit_code": result.returncode, "evidence": str(metadata_path)}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

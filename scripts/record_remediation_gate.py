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


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repo.resolve().as_posix()}", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def fingerprint(repo: Path) -> dict:
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    patch = subprocess.run(
        ["git", "-c", f"safe.directory={repo.resolve().as_posix()}", "diff", "--binary", "HEAD"],
        cwd=repo,
        capture_output=True,
    ).stdout
    return {
        "path": str(repo.resolve()),
        "sha": git(repo, "rev-parse", "HEAD"),
        "branch": git(repo, "branch", "--show-current"),
        "remote": git(repo, "remote", "get-url", "origin"),
        "upstream": git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
        "dirty": bool(status),
        "worktree_sha256": hashlib.sha256(patch + status.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--extra-repo", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("command required after --")
    if os.name == "nt" and command[0].lower() in {"npm", "npx", "yarn", "pnpm"}:
        command[0] += ".cmd"
    repositories = [ROOT, *(Path(value).resolve() for value in args.extra_repo)]
    started = datetime.now(timezone.utc).isoformat()
    before_repositories = {str(repo): fingerprint(repo) for repo in repositories}
    before = before_repositories[str(ROOT)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    finished = datetime.now(timezone.utc).isoformat()
    after_repositories = {str(repo): fingerprint(repo) for repo in repositories}
    after = after_repositories[str(ROOT)]
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
        "candidate_repositories_before": before_repositories,
        "candidate_repositories_after": after_repositories,
        "candidate_stable": before_repositories == after_repositories,
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

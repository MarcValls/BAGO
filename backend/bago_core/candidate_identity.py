"""Single canonical Git fingerprint used by gates and claim verification."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from bago_core.operational_integrity import CandidateIdentity


def git(repo: Path, *args: str, allow_empty: bool = False) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repo.resolve().as_posix()}", *args],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0 and not allow_empty:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def fingerprint(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    patch = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "diff", "--binary", "HEAD"],
        cwd=root, capture_output=True, check=True,
    ).stdout
    remote = git(root, "remote", "get-url", "origin", allow_empty=True) or f"local-only:{root}"
    return {
        "path": str(root), "sha": git(root, "rev-parse", "HEAD"),
        "branch": git(root, "branch", "--show-current") or "detached", "remote": remote,
        "upstream": git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", allow_empty=True),
        "dirty": bool(status), "worktree_sha256": hashlib.sha256((patch or status.encode("utf-8")) or git(root, "rev-parse", "HEAD").encode("utf-8")).hexdigest(),
    }


def candidate_from_repo(repo: Path) -> CandidateIdentity:
    raw = fingerprint(repo)
    return CandidateIdentity(
        str(raw["sha"]), str(raw["branch"]), str(raw["remote"]), str(raw["upstream"]),
        bool(raw["dirty"]), str(raw["worktree_sha256"]),
    )

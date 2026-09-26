"""Single canonical Git fingerprint used by gates and claim verification."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from bago_core.operational_integrity import CandidateIdentity


def _safe_directory_args(repo: Path) -> list[str]:
    resolved = repo.resolve()
    safe_dirs = [resolved]
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            if candidate not in safe_dirs:
                safe_dirs.append(candidate)
            break
    return [
        item
        for safe_dir in safe_dirs
        for item in ("-c", f"safe.directory={safe_dir.as_posix()}")
    ]


def git(repo: Path, *args: str, allow_empty: bool = False) -> str:
    from bago_core.server_effects import inspect_process

    root = repo.resolve()
    manager = SimpleNamespace(
        session_id=f"candidate-identity:{root}",
        base_path=str(root),
        project_root=str(root),
    )
    result = inspect_process(
        "git",
        [*_safe_directory_args(root), *args],
        cwd=root,
        manager=manager,
    )
    if int(result.get("exit_code", 1)) != 0 and not allow_empty:
        raise ValueError(str(result.get("stderr") or "").strip() or f"git {' '.join(args)} failed")
    return str(result.get("stdout") or "").strip()


def fingerprint(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    from bago_core.server_effects import inspect_process

    manager = SimpleNamespace(
        session_id=f"candidate-identity:{root}",
        base_path=str(root),
        project_root=str(root),
    )
    patch = inspect_process(
        "git",
        ["-c", f"safe.directory={root.as_posix()}", "diff", "--binary", "HEAD"],
        cwd=root,
        manager=manager,
        output_digest="sha256",
    )
    patch_sha256 = str(patch.get("stdout") or "").removeprefix("sha256:")
    empty_patch_sha256 = hashlib.sha256(b"").hexdigest()
    remote = git(root, "remote", "get-url", "origin", allow_empty=True) or f"local-only:{root}"
    sha = git(root, "rev-parse", "HEAD")
    worktree_sha256 = (
        patch_sha256
        if patch_sha256 != empty_patch_sha256
        else hashlib.sha256(status.encode("utf-8") if status else sha.encode("utf-8")).hexdigest()
    )
    return {
        "path": str(root), "sha": sha,
        "branch": git(root, "branch", "--show-current") or "detached", "remote": remote,
        "upstream": git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", allow_empty=True),
        "dirty": bool(status), "worktree_sha256": worktree_sha256,
    }


def candidate_from_repo(repo: Path) -> CandidateIdentity:
    raw = fingerprint(repo)
    return CandidateIdentity(
        str(raw["sha"]), str(raw["branch"]), str(raw["remote"]), str(raw["upstream"]),
        bool(raw["dirty"]), str(raw["worktree_sha256"]),
    )

"""Canonical and symlink-safe paths owned by the release-job subsystem."""
from __future__ import annotations

import os
import re
from pathlib import Path


def release_jobs_root() -> Path:
    from bago_core.user_state_paths import user_root

    override = os.environ.get("BAGO_USER_ROOT", "").strip() or os.environ.get("BAGO_ROOT", "").strip()
    root = Path(override).expanduser() if override else user_root()
    # Keep the lexical state root so callers can reject links/reparse points
    # instead of resolving and silently accepting a redirected storage tree.
    return root / "manager" / "release-jobs"


def release_job_file(job_id: str, area: str, suffix: str) -> Path:
    clean = str(job_id or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,179}", clean):
        raise ValueError("Release job id is invalid")
    if area not in {"jobs", "logs"}:
        raise ValueError("Release job storage area is invalid")
    root = release_jobs_root()
    directory = root / area
    target = directory / f"{clean}{suffix}"
    current = target
    while True:
        if current.is_symlink():
            raise ValueError("Release job storage cannot traverse symlinks")
        if current == root:
            break
        current = current.parent
    return target


def release_job_archive_directory(job_id: str) -> Path:
    clean = str(job_id or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,179}", clean):
        raise ValueError("Release job id is invalid")
    root = release_jobs_root()
    target = root / "archive" / "deleted-jobs" / clean
    current = target
    while True:
        if current.is_symlink():
            raise ValueError("Release job archive cannot traverse symlinks")
        if current == root:
            break
        current = current.parent
    return target


def release_job_cache_directory(job_id: str) -> Path:
    clean = str(job_id or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,179}", clean):
        raise ValueError("Release job id is invalid")
    root = release_jobs_root()
    target = root / "cache" / clean
    current = target
    while True:
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            metadata = None
        if metadata is not None and (
            current.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
        ):
            raise ValueError("Release-job cache cannot traverse links or reparse points")
        if current == root:
            break
        current = current.parent
    return target

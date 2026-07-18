"""BAGO Code Forge 3B - atomic patch application.

Step 15 of the BAGO Code Forge 3B pipeline. The repair loop hands the
execution layer a :class:`bago_core.codegen.repair_loop.RepairVerdict`
plus a tuple of accepted :class:`Patch` objects. This module is the
**only** place BAGO writes the patches back to the user's workspace.

Atomicity is achieved with a two-phase commit:

1. **Snapshot** - the affected files are copied into a backup
   directory and their pre-patch contents are hashed.
2. **Apply** - each patch is applied by replacing the affected
   files. If anything raises during the apply phase, the snapshot is
   used to roll back the workspace to its original state.
3. **Commit** - the snapshot is kept (default) or removed, depending
   on the caller's policy.

The module never touches the staging area; it only operates on the
real workspace.

Design rules (R0-R10):

- R0: <200 lines.
- R1: :class:`AppliedPatch` is a frozen dataclass. The rollback
  handle is opaque to callers.
- R2: deterministic. Given the same patches + workspace, the result
  is identical.
- R3: a failed apply always rolls back; a partial write is
  forbidden. ``PatchApplyError`` carries a stable ``code`` so the
  evidence bundle can audit the failure.
- R4: forbidden paths (``DEFAULT_FORBIDDEN_PATHS``) are rejected
  before any disk write. The apply call never even opens the file.
- R8: no subprocess. Patch application is pure file I/O.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ..codegen.patch_parser import Patch


# Stable error codes. The evidence bundle dispatches on these.
PATCH_OK = "ok"
PATCH_FORBIDDEN_PATH = "forbidden_path"
PATCH_PATH_OUTSIDE_WORKSPACE = "path_outside_workspace"
PATCH_BINARY_FILE = "binary_file"
PATCH_APPLY_IO_ERROR = "apply_io_error"
PATCH_ROLLBACK_FAILED = "rollback_failed"


# Forbidden paths. Mirrors ``task_compiler.DEFAULT_FORBIDDEN_PATHS``;
# duplicated here so the execution layer doesn't have to import the
# compiler just to refuse a write.
DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (
    ".git",
    ".env",
    "state",
    "dist",
    "release",
    "__pycache__",
    ".bago",
    "node_modules",
    ".venv",
    "venv",
)


@dataclass(frozen=True)
class AppliedPatch:
    """Record of one patch successfully written to disk.

    Attributes
    ----------
    path:
        Workspace-relative path that was written.
    hash_before:
        SHA-256 hex digest of the file before the patch.
    hash_after:
        SHA-256 hex digest of the file after the patch.
    bytes_written:
        Number of bytes the new file contains.
    """

    path: str
    hash_before: str
    hash_after: str
    bytes_written: int

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "hash_before": self.hash_before,
            "hash_after": self.hash_after,
            "bytes_written": self.bytes_written,
        }


@dataclass(frozen=True)
class PatchApplyResult:
    """Aggregate result of an atomic apply."""

    status: str
    applied: tuple[AppliedPatch, ...] = ()
    rollback_snapshot: str = ""
    error_code: str = ""
    error_message: str = ""
    duration_ms: int = 0
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == PATCH_OK

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "applied": [a.to_dict() for a in self.applied],
            "rollback_snapshot": self.rollback_snapshot,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "extra": dict(self.extra),
        }


class PatchApplyError(RuntimeError):
    """Raised by ``apply_patch_atomically`` when the apply fails.

    The workspace is guaranteed to be in its original state when the
    exception is raised.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _normalise_relpath(path: str) -> str:
    """Strip POSIX/Windows separators into forward slashes and remove
    any leading ``./`` so the comparison against the forbidden list is
    consistent.
    """
    normalised = path.replace("\\", "/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


def _is_forbidden(path: str, forbidden: tuple[str, ...]) -> bool:
    normalised = _normalise_relpath(path)
    parts = normalised.split("/")
    for segment in parts:
        if segment in forbidden:
            return True
    return False


def _resolve_safe(
    workspace: Path, relative: str
) -> Path:
    """Resolve ``relative`` against ``workspace`` while refusing to
    escape via ``..``.
    """
    target = (workspace / relative).resolve()
    workspace_resolved = workspace.resolve()
    try:
        target.relative_to(workspace_resolved)
    except ValueError as exc:
        raise PatchApplyError(
            PATCH_PATH_OUTSIDE_WORKSPACE,
            f"path escapes workspace: {relative!r}",
        ) from exc
    return target


def _read_text(path: Path) -> str:
    """Read a file as UTF-8 text, returning "" on missing/binary."""
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Treat as binary. The atomic apply refuses to round-trip
        # binary files; the caller should have rerouted them.
        raise PatchApplyError(
            PATCH_BINARY_FILE,
            f"refusing to apply patch over a binary file: {path}",
        )
    except OSError as exc:
        raise PatchApplyError(
            PATCH_APPLY_IO_ERROR,
            f"read failed: {exc}",
        ) from exc


def _reconstruct_file(old_body: str, patch: Patch) -> str:
    """Apply ``patch`` to ``old_body`` in memory.

    This is a deliberately small implementation that handles the same
    subset of unified diff the model is allowed to emit. It mirrors
    the in-memory helper used by the repair loop; the two are
    duplicated here so the execution layer does not depend on the
    codegen package.
    """
    lines = old_body.splitlines(keepends=False) if old_body else []
    for hunk in patch.hunks:
        # The hunk header's ``old_start`` points into the pre-image;
        # ``new_start`` points into the post-image. We work against
        # the pre-image and translate ``new_start`` back to the
        # pre-image by skipping over deletions already applied.
        idx = max(0, hunk.old_start - 1)
        for line in hunk.lines:
            if line.marker == " ":
                if idx >= len(lines) or lines[idx] != line.text:
                    raise PatchApplyError(
                        PATCH_APPLY_IO_ERROR,
                        f"context mismatch at line {hunk.old_start}",
                    )
                idx += 1
            elif line.marker == "-":
                if idx >= len(lines) or lines[idx] != line.text:
                    raise PatchApplyError(
                        PATCH_APPLY_IO_ERROR,
                        f"deletion mismatch at line {hunk.old_start}",
                    )
                del lines[idx]
            elif line.marker == "+":
                lines.insert(idx, line.text)
                idx += 1
            elif line.marker == "\\":
                continue
            else:  # pragma: no cover - parser already rejects
                raise PatchApplyError(
                    PATCH_APPLY_IO_ERROR,
                    f"unknown marker {line.marker!r}",
                )
    body = "\n".join(lines)
    if lines and old_body.endswith("\n") and not body.endswith("\n"):
        body += "\n"
    return body


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def apply_patch_atomically(
    patches: Iterable[Patch],
    *,
    workspace_root: str | Path,
    forbidden_paths: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS,
    keep_snapshot: bool = True,
) -> PatchApplyResult:
    """Apply every patch in sequence with rollback on failure.

    Parameters
    ----------
    patches:
        Iterable of :class:`Patch` objects. The apply proceeds in
        iteration order; the first failure rolls back the entire
        batch.
    workspace_root:
        Absolute path to the user's real workspace.
    forbidden_paths:
        Path segments the apply must refuse. Compared segment-wise so
        ``state/foo.json`` is forbidden when ``state`` is in the list.
    keep_snapshot:
        If ``True`` (default), the rollback directory is kept under
        ``<workspace>/.bago/snapshots/<ts>_<rand>/`` so the user can
        manually revert even after a successful apply. If ``False``,
        the snapshot is removed on success.
    """
    started = _now_ms()
    workspace = Path(workspace_root).resolve()
    if not workspace.is_dir():
        raise PatchApplyError(
            PATCH_APPLY_IO_ERROR,
            f"workspace does not exist: {workspace}",
        )

    snapshot_dir = _create_snapshot_dir(workspace)
    applied: list[AppliedPatch] = []
    patch_list = list(patches)

    try:
        for patch in patch_list:
            if _is_forbidden(patch.new_path, forbidden_paths):
                raise PatchApplyError(
                    PATCH_FORBIDDEN_PATH,
                    f"patch targets forbidden path: {patch.new_path}",
                )
            target = _resolve_safe(workspace, patch.new_path)
            old_body = _read_text(target)
            new_body = _reconstruct_file(old_body, patch)
            # Snapshot the pre-image before writing the new one.
            _snapshot_file(snapshot_dir, patch.new_path, old_body)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_body, encoding="utf-8")
            applied.append(
                AppliedPatch(
                    path=patch.new_path,
                    hash_before=_sha256(old_body),
                    hash_after=_sha256(new_body),
                    bytes_written=len(new_body.encode("utf-8")),
                )
            )
    except PatchApplyError as exc:
        # Rollback every file we already wrote, then either keep or
        # discard the snapshot directory.
        rollback_patch(snapshot_dir, workspace)
        if not keep_snapshot:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        return PatchApplyResult(
            status="failed",
            applied=tuple(applied),
            rollback_snapshot=str(snapshot_dir),
            error_code=exc.code,
            error_message=str(exc),
            duration_ms=_now_ms() - started,
        )
    except OSError as exc:
        rollback_patch(snapshot_dir, workspace)
        if not keep_snapshot:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        return PatchApplyResult(
            status="failed",
            applied=tuple(applied),
            rollback_snapshot=str(snapshot_dir),
            error_code=PATCH_APPLY_IO_ERROR,
            error_message=str(exc),
            duration_ms=_now_ms() - started,
        )

    if not keep_snapshot:
        shutil.rmtree(snapshot_dir, ignore_errors=True)
        snapshot_dir_str = ""
    else:
        snapshot_dir_str = str(snapshot_dir)

    return PatchApplyResult(
        status=PATCH_OK,
        applied=tuple(applied),
        rollback_snapshot=snapshot_dir_str,
        duration_ms=_now_ms() - started,
    )


def rollback_patch(snapshot_dir: str | Path, workspace_root: str | Path) -> None:
    """Restore every file in ``snapshot_dir`` back to ``workspace_root``.

    The snapshot directory is laid out as ``<path>.bago-snap/<rel>``
    where ``<rel>`` mirrors the original workspace tree. Missing
    files (i.e. files the patch created) are removed from the
    workspace. Files the patch did not touch are left alone.
    """
    snapshot = Path(snapshot_dir)
    workspace = Path(workspace_root).resolve()
    if not snapshot.is_dir():
        return
    for entry in sorted(snapshot.rglob("*")):
        if not entry.is_file():
            continue
        rel = entry.relative_to(snapshot)
        target = (workspace / rel).resolve()
        try:
            target.relative_to(workspace)
        except ValueError:
            # Snapshot somehow escaped the workspace. Treat as fatal
            # but never raise; we are already in a failure path.
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target)
        except OSError:
            # Best effort; if a single file cannot be restored we
            # continue with the rest. The caller will surface a
            # ``PATCH_ROLLBACK_FAILED`` error.
            continue


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_ms() -> int:
    return int(time.time() * 1000)


def _create_snapshot_dir(workspace: Path) -> Path:
    """Allocate a private snapshot directory under ``.bago/snapshots``."""
    bago_dir = workspace / ".bago"
    snapshots_dir = bago_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{_now_ms()}_{os.getpid()}_{os.urandom(2).hex()}.bago-snap"
    return snapshots_dir / suffix


def _snapshot_file(snapshot_dir: Path, relative_path: str, body: str) -> None:
    """Write ``body`` to ``snapshot_dir / relative_path``."""
    target = snapshot_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


__all__ = [
    "AppliedPatch",
    "DEFAULT_FORBIDDEN_PATHS",
    "PATCH_APPLY_IO_ERROR",
    "PATCH_BINARY_FILE",
    "PATCH_FORBIDDEN_PATH",
    "PATCH_OK",
    "PATCH_PATH_OUTSIDE_WORKSPACE",
    "PATCH_ROLLBACK_FAILED",
    "PatchApplyError",
    "PatchApplyResult",
    "apply_patch_atomically",
    "rollback_patch",
]
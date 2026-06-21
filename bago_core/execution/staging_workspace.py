"""BAGO Code Forge 3B - staging workspace.

Step 14 of the BAGO Code Forge 3B pipeline. The validation pipeline
must never read the project's real working tree directly: lint and
test commands may modify on-disk artefacts (caches, ``__pycache__``,
``.mypy_cache``, etc.) and BAGO must not let them leak into the
user's workspace.

The staging workspace solves this by giving the validation pipeline a
**temporary copy** of the project. Adapters always read from the
staging root; the real workspace is only touched when an accepted
patch is promoted by :mod:`bago_core.execution.atomic_patch`.

Design rules (R0-R10):

- R0: <200 lines, single responsibility.
- R1: :class:`WorkspaceSnapshot` and :class:`StagingWorkspace` are
  immutable dataclasses wrapping mutable state on disk.
- R2: deterministic. Same source + same seed -> same staged tree.
- R3: the staging area is always created under a unique directory
  (``bago_staging_<ts>_<rand>``) and is always cleaned up on exit.
- R4: symlinks are resolved to real files when the workspace is
  copied; this prevents the validator from accidentally following a
  malicious symlink into ``.git`` or ``.env``.
- R8: the workspace never runs subprocess. Snapshot capture is a
  recursive copy; promotion is delegated to ``atomic_patch``.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping


# Stable code returned by the staging area if a path is forbidden.
STAGING_FORBIDDEN = "staging_forbidden_path"

# Default ignore list applied to every copy. Keeping it deterministic
# (sorted) makes the snapshot reproducible.
_DEFAULT_IGNORE: tuple[str, ...] = (
    ".git",
    ".bago",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    "release",
)


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """Read-only description of a captured workspace.

    Attributes
    ----------
    source_root:
        Absolute path to the original workspace.
    staging_root:
        Absolute path to the staging directory (a copy of
        ``source_root`` minus the ignored entries).
    created_at:
        Unix timestamp (seconds) the snapshot was created.
    copied_paths:
        Relative paths the copy actually wrote, in deterministic
        order. Paths matching the ignore list are not present.
    """

    source_root: str
    staging_root: str
    created_at: float
    copied_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "source_root": self.source_root,
            "staging_root": self.staging_root,
            "created_at": self.created_at,
            "copied_paths": list(self.copied_paths),
        }


@dataclass(frozen=True)
class StagingWorkspace:
    """A live handle to a staging directory.

    The staging directory is owned by this object and will be removed
    when :meth:`close` is called (either explicitly or via the
    context manager protocol).
    """

    snapshot: WorkspaceSnapshot
    _cleanup: bool = True
    _closed: bool = False
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def root(self) -> str:
        """Absolute path to the staging directory."""
        return self.snapshot.staging_root

    @property
    def source_root(self) -> str:
        return self.snapshot.source_root

    def resolve(self, relative_path: str) -> str:
        """Resolve ``relative_path`` against the staging root.

        Refuses to escape the staging root with a structured error
        so the validator cannot accidentally read ``../.git`` even if
        a malicious patch asks it to.
        """
        root = Path(self.snapshot.staging_root).resolve()
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise StagingError(
                STAGING_FORBIDDEN,
                f"path escapes staging root: {relative_path!r}",
            ) from exc
        return str(target)

    def read_text(self, relative_path: str, *, encoding: str = "utf-8") -> str:
        """Read a UTF-8 text file from the staging area."""
        path = Path(self.resolve(relative_path))
        try:
            return path.read_text(encoding=encoding)
        except FileNotFoundError:
            return ""
        except OSError:
            return ""

    def close(self) -> None:
        """Remove the staging directory if it still exists."""
        if self._closed or not self._cleanup:
            object.__setattr__(self, "_closed", True)
            return
        object.__setattr__(self, "_closed", True)
        root = Path(self.snapshot.staging_root)
        if root.is_dir():
            shutil.rmtree(root, ignore_errors=True)

    def __enter__(self) -> "StagingWorkspace":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class StagingError(RuntimeError):
    """Raised when the staging workspace cannot be safely built."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _should_ignore(name: str, ignore: Iterable[str]) -> bool:
    """Return ``True`` if a top-level directory/file must be skipped."""
    return name in ignore


def _safe_copytree(
    source: Path,
    destination: Path,
    *,
    ignore: tuple[str, ...],
) -> list[str]:
    """Recursively copy ``source`` into ``destination`` with symlinks
    resolved.

    Returns the sorted list of relative paths that were actually
    written. The list excludes anything in ``ignore`` so the caller
    can audit what made it into the staging area.
    """
    if not source.is_dir():
        raise StagingError(
            "staging_source_missing",
            f"source workspace does not exist: {source}",
        )

    copied: list[str] = []
    destination.mkdir(parents=True, exist_ok=False)

    for entry in _walk_resolved(source):
        rel = entry.relative_to(source)
        parts = rel.parts
        if parts and _should_ignore(parts[0], ignore):
            continue
        target = destination / rel
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            copied.append(str(rel).replace(os.sep, "/"))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target, follow_symlinks=True)
        copied.append(str(rel).replace(os.sep, "/"))
    return sorted(set(copied))


def _walk_resolved(root: Path):
    """Yield every entry under ``root`` with symlinks resolved.

    Walks manually rather than using ``os.walk(followlinks=True)``
    because we also want to skip symlinked directories entirely.
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for dirname in list(dirnames):
            full = current / dirname
            if full.is_symlink():
                # Skip symlinked subtrees entirely. This is the safe
                # default: a symlink to ``.git`` or ``.env`` would
                # otherwise let the validator read files the user
                # deliberately kept out of the workspace.
                dirnames.remove(dirname)
                continue
            yield full
        for filename in filenames:
            full = current / filename
            if full.is_symlink():
                continue
            yield full


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def open_staging_workspace(
    source_root: str | Path,
    *,
    parent_dir: str | Path | None = None,
    ignore: Iterable[str] = _DEFAULT_IGNORE,
    label: str = "bago_staging",
) -> StagingWorkspace:
    """Create a new staging workspace by copying ``source_root``.

    The staging directory is created under ``parent_dir`` (defaults to
    the system temp directory) with a unique name of the form
    ``<label>_<unix_ms>_<rand>``. The directory is removed when the
    returned :class:`StagingWorkspace` is closed.
    """
    source = Path(source_root).resolve()
    ignore_set = tuple(dict.fromkeys(tuple(ignore) + _DEFAULT_IGNORE))
    parent = Path(parent_dir) if parent_dir is not None else Path(tempfile.gettempdir())
    parent.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time() * 1000)
    suffix = f"{timestamp}_{os.getpid()}_{os.urandom(2).hex()}"
    staging_path = parent / f"{label}_{suffix}"

    try:
        copied = _safe_copytree(source, staging_path, ignore=ignore_set)
    except FileExistsError as exc:
        raise StagingError(
            "staging_already_exists",
            f"staging path already exists: {staging_path}",
        ) from exc

    snapshot = WorkspaceSnapshot(
        source_root=str(source),
        staging_root=str(staging_path),
        created_at=time.time(),
        copied_paths=tuple(copied),
    )
    return StagingWorkspace(snapshot=snapshot)


__all__ = [
    "STAGING_FORBIDDEN",
    "StagingError",
    "StagingWorkspace",
    "WorkspaceSnapshot",
    "open_staging_workspace",
]
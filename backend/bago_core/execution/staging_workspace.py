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
- R3: the Gateway creates a unique staging identity under the canonical
  temporary BAGO validation root and cleans it up on exit.
- R4: symlink and junction entries are skipped by the owner so validation
  cannot follow them into ``.git`` or ``.env``.
- R8: the workspace never runs subprocess. Snapshot capture is a
  recursive copy; promotion is delegated to ``atomic_patch``.
"""
from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


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
    staging_id: str = ""
    label: str = "bago_staging"

    def to_dict(self) -> dict[str, object]:
        return {
            "source_root": self.source_root,
            "staging_root": self.staging_root,
            "created_at": self.created_at,
            "copied_paths": list(self.copied_paths),
            "staging_id": self.staging_id,
            "label": self.label,
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
        from bago_core.server_effects import cleanup_validation_workspace

        cleanup_validation_workspace(self.snapshot.staging_id, label=self.snapshot.label)
        object.__setattr__(self, "_closed", True)

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

    The Gateway creates a unique directory below the canonical BAGO
    validation staging root. A noncanonical ``parent_dir`` is rejected.
    """
    from bago_core.server_effects import stage_validation_workspace

    source = Path(source_root).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    ignore_set = tuple(dict.fromkeys(tuple(ignore) + _DEFAULT_IGNORE))
    parent = Path(tempfile.gettempdir()).resolve() / "BAGO" / "validation"
    if parent_dir is not None and Path(parent_dir).expanduser().resolve() != parent:
        raise StagingError("staging_target_out_of_scope", "validation staging parent must be the canonical BAGO temp root")
    try:
        result = stage_validation_workspace(str(source), ignore=list(ignore_set), label=str(label))
    except Exception as exc:
        raise StagingError(
            str(getattr(exc, "code", "validation_staging_failed")),
            str(exc),
        ) from exc

    snapshot = WorkspaceSnapshot(
        source_root=str(source.resolve()),
        staging_root=str(result["staging_root"]),
        created_at=time.time(),
        copied_paths=tuple(result["copied_paths"]),
        staging_id=str(result["staging_id"]),
        label=str(result["label"]),
    )
    return StagingWorkspace(snapshot=snapshot)


__all__ = [
    "STAGING_FORBIDDEN",
    "StagingError",
    "StagingWorkspace",
    "WorkspaceSnapshot",
    "open_staging_workspace",
]

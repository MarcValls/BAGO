"""BAGO Code Forge 3B - execution subpackage.

The execution subpackage is the only part of BAGO that touches the
filesystem on behalf of Code Forge. Everything above (classifier,
compiler, context, repair loop, verdict) is pure data; everything
below lives here:

- :class:`ProcessRunner` and :class:`SubprocessProcessRunner` in
  :mod:`bago_core.execution.process_runner` are the seam between the
  validation pipeline and the real operating system.
- :class:`StagingWorkspace` in
  :mod:`bago_core.execution.staging_workspace` is the temporary copy
  of the project the validation pipeline reads from.
- :func:`apply_patch_atomically` and friends in
  :mod:`bago_core.execution.atomic_patch` are the seam between an
  accepted :class:`Patch` and the real workspace on disk.
"""
from __future__ import annotations

from .atomic_patch import (
    AppliedPatch,
    PatchApplyError,
    apply_patch_atomically,
    rollback_patch,
)
from .process_runner import (
    ProcessOutcome,
    ProcessRunner,
    SubprocessProcessRunner,
)
from .staging_workspace import (
    StagingWorkspace,
    WorkspaceSnapshot,
    open_staging_workspace,
)


__all__ = [
    "AppliedPatch",
    "PatchApplyError",
    "ProcessOutcome",
    "ProcessRunner",
    "StagingWorkspace",
    "SubprocessProcessRunner",
    "WorkspaceSnapshot",
    "apply_patch_atomically",
    "open_staging_workspace",
    "rollback_patch",
]
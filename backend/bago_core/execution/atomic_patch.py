"""Authorized client for applying and restoring workspace patch batches.

Patch calculation and workspace I/O belong to the registered ``project.write``
adapter. This module only constructs the canonical request and dispatches it
through ExecutionGateway; it contains no filesystem materializer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..codegen.patch_parser import Patch


PATCH_OK = "ok"
PATCH_FORBIDDEN_PATH = "workspace_patch_forbidden_path"
PATCH_PATH_OUTSIDE_WORKSPACE = "workspace_patch_out_of_scope"
PATCH_BINARY_FILE = "workspace_patch_binary_file"
PATCH_APPLY_IO_ERROR = "workspace_patch_apply_failed"
PATCH_ROLLBACK_FAILED = "workspace_patch_rollback_failed"

DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (
    ".git", ".env", "state", "dist", "release", "__pycache__", ".bago",
    "node_modules", ".venv", "venv",
)


@dataclass(frozen=True)
class AppliedPatch:
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
            "applied": [item.to_dict() for item in self.applied],
            "rollback_snapshot": self.rollback_snapshot,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "extra": dict(self.extra),
        }


class PatchApplyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _failure(exc: Exception) -> PatchApplyResult:
    code = str(getattr(exc, "code", "workspace_patch_dispatch_failed"))
    return PatchApplyResult(status="failed", error_code=code, error_message=str(exc))


def apply_patch_atomically(
    patches: Iterable[Patch],
    *,
    workspace_root: str | Path,
    manager: Any = None,
    permit_token: str = "",
    keep_snapshot: bool = True,
) -> PatchApplyResult:
    """Apply a pre-authorized batch through the shared ``project.write`` owner.

    Obtain and approve the operation-bound Permit through
    ``POST /project/patch`` before calling this client. Snapshot retention is
    mandatory so a failed validation can be explicitly rolled back later.
    """
    if not keep_snapshot:
        return PatchApplyResult(
            status="failed",
            error_code="workspace_patch_snapshot_required",
            error_message="Authorized patch batches must retain their rollback snapshot.",
        )
    if manager is None or not str(permit_token or "").strip():
        return PatchApplyResult(
            status="failed",
            error_code="workspace_patch_permit_required",
            error_message="Workspace patch requires SessionManager context and an approved Permit.",
        )
    if Path(workspace_root).expanduser().resolve() != Path(str(getattr(manager, "project_root", ""))).expanduser().resolve():
        return PatchApplyResult(
            status="failed",
            error_code="project_write_root_mismatch",
            error_message="Workspace patch root does not match the active project root.",
        )
    try:
        from execution_adapter_contract import ExecutionContext
        from execution_adapters.project import ProjectWriteEffectAdapter
        from execution_gateway import ExecutionGateway

        diffs = [patch.raw for patch in patches]
        request = ProjectWriteEffectAdapter.build_patch_request(manager, diffs)
        receipt, _authorization = ExecutionGateway().execute(
            permit_token=permit_token,
            request=request,
            context=ExecutionContext(manager=manager),
        )
        operation = dict(receipt.get("result") or {})
        applied = tuple(
            AppliedPatch(
                path=str(item.get("path") or ""),
                hash_before=str(item.get("before_sha256") or ""),
                hash_after=str(item.get("after_sha256") or ""),
                bytes_written=int(item.get("bytes_written") or 0),
            )
            for item in operation.get("applied", [])
        )
        return PatchApplyResult(
            status=PATCH_OK,
            applied=applied,
            rollback_snapshot=str(operation.get("snapshot") or ""),
            extra={"receipt_id": receipt.get("receipt_id", "")},
        )
    except Exception as exc:
        return _failure(exc)


def rollback_patch(
    snapshot_dir: str | Path,
    workspace_root: str | Path,
    *,
    manager: Any = None,
    permit_token: str = "",
) -> dict[str, Any]:
    """Restore one exact patch snapshot through the same project.write owner."""
    if manager is None or not str(permit_token or "").strip():
        raise PatchApplyError("workspace_patch_permit_required", "Patch rollback requires SessionManager context and an approved Permit.")
    if Path(workspace_root).expanduser().resolve() != Path(str(getattr(manager, "project_root", ""))).expanduser().resolve():
        raise PatchApplyError("project_write_root_mismatch", "Rollback workspace does not match the active project root.")
    from execution_adapter_contract import ExecutionContext
    from execution_adapters.project import ProjectWriteEffectAdapter
    from execution_gateway import ExecutionGateway

    request = ProjectWriteEffectAdapter.build_patch_rollback_request(manager, str(snapshot_dir))
    receipt, _authorization = ExecutionGateway().execute(
        permit_token=permit_token,
        request=request,
        context=ExecutionContext(manager=manager),
    )
    return dict(receipt.get("result") or {})


__all__ = [
    "AppliedPatch", "DEFAULT_FORBIDDEN_PATHS", "PATCH_APPLY_IO_ERROR",
    "PATCH_BINARY_FILE", "PATCH_FORBIDDEN_PATH", "PATCH_OK",
    "PATCH_PATH_OUTSIDE_WORKSPACE", "PATCH_ROLLBACK_FAILED", "PatchApplyError",
    "PatchApplyResult", "apply_patch_atomically", "rollback_patch",
]

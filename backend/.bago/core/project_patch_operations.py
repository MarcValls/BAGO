"""Request construction and dispatch helpers for project patch operations.

This module coordinates the existing ``project.write`` owner; it does not
register another effect or materialize workspace files itself.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest, build_execution_request, stable_digest


def prepare_apply(adapter: Any, manager: Any, workspace_root: str, diffs: Any) -> tuple[Path, Path, str]:
    from workspace_patch_storage import describe_patch

    root = adapter._trusted_root(manager)
    target = adapter._validate_operation_target(root, workspace_root, "patch")
    if target != root:
        raise ExecutionGatewayError("Patch workspace must match the active project root", code="project_write_root_mismatch")
    return root, target, stable_digest(describe_patch(target, diffs))


def prepare_rollback(adapter: Any, manager: Any, workspace_root: str, snapshot_path: str) -> tuple[Path, Path, str]:
    from workspace_patch_storage import describe_rollback

    root = adapter._trusted_root(manager)
    target = adapter._validate_operation_target(root, workspace_root, "patch.rollback")
    if target != root:
        raise ExecutionGatewayError("Patch workspace must match the active project root", code="project_write_root_mismatch")
    return root, target, stable_digest(describe_rollback(target, snapshot_path))


def build_apply_request(adapter: Any, manager: Any, diffs: Any) -> ExecutionRequest:
    workspace_root = str(getattr(manager, "project_root", "") or "")
    root, target, digest = prepare_apply(adapter, manager, workspace_root, diffs)
    return build_execution_request(
        effect_id="project.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=str(getattr(manager, "session_id", "") or ""),
        source_surface="api.project.patch",
        target={"path": str(target), "allowed_root": str(root), "resource": "project_operation", "operation": "patch", "root_digest": digest},
        arguments={"patches": diffs},
        scope="workspace",
    )


def build_rollback_request(adapter: Any, manager: Any, snapshot_path: str) -> ExecutionRequest:
    workspace_root = str(getattr(manager, "project_root", "") or "")
    root, target, digest = prepare_rollback(adapter, manager, workspace_root, snapshot_path)
    return build_execution_request(
        effect_id="project.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=str(getattr(manager, "session_id", "") or ""),
        source_surface="api.project.patch.rollback",
        target={"path": str(target), "allowed_root": str(root), "resource": "project_operation", "operation": "patch.rollback", "root_digest": digest},
        arguments={"snapshot": snapshot_path},
        scope="workspace",
    )


def materialize(target: Path, operation: str, arguments: dict[str, Any], request: ExecutionRequest) -> dict[str, Any]:
    from workspace_patch_storage import apply_patch, rollback_patch

    if operation == "patch":
        return apply_patch(target, arguments.get("patches"), str(request.target.get("root_digest") or ""))
    return rollback_patch(target, str(arguments.get("snapshot") or ""), str(request.target.get("root_digest") or ""))


def execute(adapter: Any, request: ExecutionRequest, context: ExecutionContext, root: Path, target: Path, resource: str, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from workspace_patch_storage import describe_patch, describe_rollback

    approved_digest = str(request.target.get("root_digest") or "").strip()
    if not approved_digest:
        raise ExecutionGatewayError("Patch operation request lacks target digest", code="project_write_digest_required")
    try:
        with adapter._root_lock(root):
            if operation == "patch":
                current_digest = stable_digest(describe_patch(target, arguments.get("patches")))
            else:
                current_digest = stable_digest(describe_rollback(target, str(arguments.get("snapshot") or "")))
            if current_digest != approved_digest:
                raise ExecutionGatewayError("Patch operation changed after authorization", code="project_write_target_changed")
            result = materialize(target, operation, arguments, request)
    except ExecutionGatewayError:
        raise
    except Exception as exc:
        error_code = str(getattr(exc, "code", "") or "")
        if error_code.startswith("workspace_patch_"):
            raise ExecutionGatewayError(str(exc), code=error_code) from exc
        raise ExecutionGatewayError(f"Project patch operation failed: {exc}", code="project_write_failed") from exc
    receipt_digest = hashlib.sha256(request.fingerprint.encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "executed": True,
        "effect_id": request.effect_id,
        "resource": resource,
        "operation": operation,
        "path": str(target),
        "project_root": str(root),
        "target_digest": approved_digest,
        "result": result,
        "evidence": [f"operation:{operation}", f"path:{target}", f"target_digest:{approved_digest}"],
        "receipt_id": f"project-write:sha256:{receipt_digest}",
    }

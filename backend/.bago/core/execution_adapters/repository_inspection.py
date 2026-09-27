"""Bounded, read-only Git inspection under direct CLI authorization."""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class RepositoryInspectionEffectAdapter:
    effect_ids = frozenset({"repository.inspect"})
    _OPERATIONS = {
        "staged_files": ["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR", "--no-ext-diff", "--no-textconv"],
        "staged_diff": ["diff", "--cached", "--no-ext-diff", "--no-textconv"],
    }

    @staticmethod
    def _is_repository_root(root: Path) -> bool:
        marker = root / ".git"
        try:
            metadata = marker.lstat()
        except OSError:
            return False
        return not marker.is_symlink() and (marker.is_dir() or marker.is_file()) and not bool(
            int(getattr(metadata, "st_file_attributes", 0) or 0)
            & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        )

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        proof = authorization.get("proof") if isinstance(authorization, dict) else None
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if (
            not isinstance(authorization, dict)
            or authorization.get("state") != "consumed"
            or authorization.get("effect_id") != request.effect_id
            or authorization.get("operation_fingerprint") != request.fingerprint
            or not isinstance(proof, dict)
            or proof.get("operation_fingerprint") != request.fingerprint
            or proof.get("effect_id") != request.effect_id
            or proof.get("authenticated_session_id") != request.session_id
            or proof.get("user_decision") != "approve"
            or not isinstance(provenance, dict)
            or provenance.get("kind") != "direct_user_interaction"
            or provenance.get("channel") != "cli"
        ):
            raise ExecutionGatewayError("Repository inspection requires its consumed CLI Permit", code="repository_inspect_authorization_required")

        target = request.target if isinstance(request.target, dict) else {}
        operation = str(target.get("operation") or "")
        args = self._OPERATIONS.get(operation)
        raw_root = str(target.get("repository_root") or "")
        allowed_surfaces = {
            f"cli.commit_readiness.{operation}",
            f"cli.debt_guard.{operation}",
        }
        if not args or request.source_surface not in allowed_surfaces:
            raise ExecutionGatewayError("Repository inspection operation is not allowed", code="repository_inspect_operation_invalid")
        lexical_root = Path(raw_root).expanduser()
        if not lexical_root.is_absolute():
            raise ExecutionGatewayError("Repository inspection root must be absolute", code="repository_inspect_root_invalid")
        try:
            root = lexical_root.resolve(strict=True)
        except OSError as exc:
            raise ExecutionGatewayError("Repository root is unavailable", code="repository_inspect_root_invalid") from exc
        session_id = "repository:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]
        if request.session_id != session_id or not root.is_dir() or not self._is_repository_root(root):
            raise ExecutionGatewayError("Repository identity changed or is not a Git worktree", code="repository_inspect_root_invalid")

        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
        environment.update({
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        })
        try:
            completed = subprocess.run(
                [
                    "git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                    *args,
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExecutionGatewayError(f"Git inspection failed: {exc}", code="repository_inspect_failed") from exc
        if len(completed.stdout.encode("utf-8", errors="replace")) > 8 * 1024 * 1024:
            raise ExecutionGatewayError("Git inspection output exceeded its limit", code="repository_inspect_output_too_large")
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "operation": operation,
            "returncode": int(completed.returncode),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "evidence": [f"repository:{root}", f"operation:{operation}"],
            "receipt_id": f"repository-inspect:{operation}:sha256:{hashlib.sha256(request.fingerprint.encode()).hexdigest()}",
        }

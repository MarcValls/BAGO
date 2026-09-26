"""Gateway owner for runtime state directory and example initialization."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class RuntimeStateBootstrapEffectAdapter:
    effect_ids = frozenset({"state.bootstrap"})
    server_policy_only = True
    _DIRECTORIES = ("sessions", "changes", "evidences")

    @staticmethod
    def _repo_root() -> Path:
        configured = str(os.environ.get("BAGO_ROOT") or "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
        return Path(__file__).resolve().parents[3]

    @classmethod
    def _state_root(cls) -> Path:
        configured = str(os.environ.get("BAGO_STATE_DIR") or "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
        return cls._repo_root() / ".bago" / "state"

    @staticmethod
    def _is_link(path: Path) -> bool:
        is_junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(is_junction and is_junction())

    @staticmethod
    def _require_policy(context: ExecutionContext) -> None:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Runtime state bootstrap requires server policy authorization",
                code="runtime_state_authorization_required",
            )

    @staticmethod
    def _validate_root(request: ExecutionRequest, context: ExecutionContext) -> Path:
        target = request.target if isinstance(request.target, dict) else {}
        raw_root = str(target.get("root") or "").strip()
        expected_root = RuntimeStateBootstrapEffectAdapter._state_root()
        allowed_root = str(context.services.get("_server_allowed_root") or "").strip()
        if raw_root != str(expected_root) or allowed_root != str(expected_root):
            raise ExecutionGatewayError(
                "Runtime state root is not canonical",
                code="runtime_state_root_invalid",
            )
        if request.session_id != f"runtime-state:{expected_root}":
            raise ExecutionGatewayError(
                "Runtime state identity does not match its canonical root",
                code="runtime_state_identity_invalid",
            )
        root = expected_root
        if root.exists() and not root.is_dir():
            raise ExecutionGatewayError(
                "Runtime state root must be a directory",
                code="runtime_state_root_invalid",
            )
        return root

    @classmethod
    def _validate_child_directory(cls, root: Path, path: Path) -> None:
        if cls._is_link(path):
            raise ExecutionGatewayError(
                "Runtime state directory cannot be a link",
                code="runtime_state_symlink_forbidden",
            )
        if path.exists() and not path.is_dir():
            raise ExecutionGatewayError(
                "Runtime state directory target is not a directory",
                code="runtime_state_target_invalid",
            )
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ExecutionGatewayError(
                "Runtime state directory escapes its root",
                code="runtime_state_path_out_of_scope",
            ) from exc

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        self._require_policy(context)
        target = request.target if isinstance(request.target, dict) else {}
        operation = str(target.get("operation") or "")
        root = self._validate_root(request, context)

        if operation == "ensure_directories":
            directories = [root, *(root / name for name in self._DIRECTORIES)]
            for directory in directories:
                self._validate_child_directory(root, directory)
            try:
                for directory in directories:
                    directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ExecutionGatewayError(
                    f"Runtime state directory initialization failed: {exc}",
                    code="runtime_state_directory_failed",
                ) from exc
            return {
                "ok": True,
                "executed": True,
                "effect_id": request.effect_id,
                "operation": operation,
                "root": str(root),
                "directories": list(self._DIRECTORIES),
                "receipt_id": f"runtime-state-directories:{root}",
            }

        if operation != "seed_examples":
            raise ExecutionGatewayError(
                "Runtime state bootstrap operation is invalid",
                code="runtime_state_operation_invalid",
            )

        source_root = self._repo_root() / ".bago" / "state.example"
        raw_source = str(target.get("source_root") or "").strip()
        if raw_source != str(source_root):
            raise ExecutionGatewayError(
                "Runtime state example root is not canonical",
                code="runtime_state_source_invalid",
            )
        if not source_root.exists():
            return {"ok": True, "executed": False, "copied": False, "reason": "examples_missing"}
        if self._is_link(source_root) or not source_root.is_dir():
            raise ExecutionGatewayError(
                "Runtime state example root must be a regular directory",
                code="runtime_state_source_invalid",
            )

        marker = root / "global_state.json"
        if self._is_link(marker):
            raise ExecutionGatewayError(
                "Runtime state marker cannot be a link",
                code="runtime_state_symlink_forbidden",
            )
        if marker.exists():
            return {"ok": True, "executed": False, "copied": False, "reason": "already_initialized"}

        sources = sorted(source_root.rglob("*"))
        copies: list[tuple[Path, Path]] = []
        for source in sources:
            relative = source.relative_to(source_root)
            if ".." in relative.parts or self._is_link(source):
                raise ExecutionGatewayError(
                    "Runtime state examples cannot contain links or traversal paths",
                    code="runtime_state_source_invalid",
                )
            if not source.is_file() or source.name == ".gitkeep":
                continue
            for parent in source.parents:
                if parent == source_root:
                    break
                if self._is_link(parent):
                    raise ExecutionGatewayError(
                        "Runtime state example path cannot contain links",
                        code="runtime_state_source_invalid",
                    )
            destination = root / relative
            self._validate_child_directory(root, destination.parent)
            if self._is_link(destination):
                raise ExecutionGatewayError(
                    "Runtime state destination cannot be a link",
                    code="runtime_state_symlink_forbidden",
                )
            if destination.exists() and not destination.is_file():
                raise ExecutionGatewayError(
                    "Runtime state destination is not a regular file",
                    code="runtime_state_target_invalid",
                )
            if not destination.exists():
                copies.append((source, destination))

        try:
            for source, destination in copies:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Runtime state example initialization failed: {exc}",
                code="runtime_state_copy_failed",
            ) from exc
        return {
            "ok": True,
            "executed": bool(copies),
            "copied": bool(copies),
            "files": [str(destination.relative_to(root)).replace("\\", "/") for _, destination in copies],
            "receipt_id": f"runtime-state-seed:{root}",
        }

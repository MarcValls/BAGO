"""Server-owned materializer and cleanup for temporary validation snapshots."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class ValidationStagingEffectAdapter:
    effect_ids = frozenset({"workspace.validation.stage"})
    server_policy_only = True
    _lock = threading.RLock()
    _active: set[str] = set()
    _FORBIDDEN = frozenset({".git", ".bago", ".env", "node_modules", ".venv", "venv", "dist", "build", "release"})
    _OPTIONAL_IGNORES = frozenset({"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"})

    @staticmethod
    def _require_policy(context: ExecutionContext) -> None:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError("Validation staging requires server policy authorization", code="validation_staging_authorization_required")

    @staticmethod
    def _base() -> Path:
        return Path(tempfile.gettempdir()).resolve() / "BAGO" / "validation"

    @staticmethod
    def _is_link(path: Path) -> bool:
        is_junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(is_junction and is_junction())

    @staticmethod
    def _identifier(value: Any) -> str:
        staging_id = str(value or "")
        if not re.fullmatch(r"[0-9a-f]{32}", staging_id):
            raise ExecutionGatewayError("Validation staging identity is invalid", code="validation_staging_identity_invalid")
        return staging_id

    @staticmethod
    def _namespace(value: Any) -> str:
        namespace = str(value or "")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", namespace):
            raise ExecutionGatewayError("Validation staging namespace is invalid", code="validation_staging_namespace_invalid")
        return namespace

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        self._require_policy(context)
        target = request.target if isinstance(request.target, dict) else {}
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        operation = str(target.get("operation") or "")
        staging_id = self._identifier(target.get("staging_id"))
        namespace = self._namespace(target.get("label"))
        root = self._base()
        namespace_root = root / namespace
        destination = namespace_root / staging_id
        owner_key = f"{namespace}:{staging_id}"
        if str(target.get("root") or "") != str(root):
            raise ExecutionGatewayError("Validation staging root is not canonical", code="validation_staging_root_invalid")

        with self._lock:
            if operation == "cleanup":
                if owner_key not in self._active:
                    raise ExecutionGatewayError("Validation staging cleanup is not owned by this runtime", code="validation_staging_cleanup_unowned")
                try:
                    if self._is_link(root.parent) or self._is_link(root) or self._is_link(namespace_root):
                        raise ExecutionGatewayError("Validation staging namespace cannot be a symlink", code="validation_staging_symlink_forbidden")
                    if destination.exists():
                        if self._is_link(destination):
                            raise ExecutionGatewayError("Validation staging target cannot be a symlink", code="validation_staging_symlink_forbidden")
                        shutil.rmtree(destination)
                    self._active.discard(owner_key)
                    try:
                        namespace_root.rmdir()
                    except OSError:
                        pass
                    try:
                        root.rmdir()
                    except OSError:
                        pass
                except OSError as exc:
                    raise ExecutionGatewayError(f"Validation staging cleanup failed: {exc}", code="validation_staging_cleanup_failed") from exc
                return {"ok": True, "executed": True, "effect_id": request.effect_id, "removed": not destination.exists(), "receipt_id": f"validation-stage-cleanup:{staging_id}"}

            if operation != "create":
                raise ExecutionGatewayError("Validation staging operation is invalid", code="validation_staging_operation_invalid")
            raw_source = Path(str(target.get("source_root") or "")).expanduser()
            if not raw_source.is_absolute():
                raise ExecutionGatewayError("Validation source root must be absolute", code="validation_staging_source_invalid")
            try:
                source = raw_source.resolve(strict=True)
                source_has_link = any(self._is_link(component) for component in (raw_source, *raw_source.parents))
                if not source.is_dir() or source_has_link:
                    raise OSError("source root identity changed or is not a directory")
            except (OSError, RuntimeError) as exc:
                raise ExecutionGatewayError("Validation source root is unavailable or linked", code="validation_staging_source_invalid") from exc
            ignore_values = arguments.get("ignore")
            if not isinstance(ignore_values, list) or len(ignore_values) > 128:
                raise ExecutionGatewayError("Validation ignore list is invalid", code="validation_staging_ignore_invalid")
            ignores = set(self._FORBIDDEN | self._OPTIONAL_IGNORES)
            for value in ignore_values:
                name = str(value)
                if not name or len(name) > 255 or "/" in name or "\\" in name:
                    raise ExecutionGatewayError("Validation ignore entry is invalid", code="validation_staging_ignore_invalid")
                ignores.add(name)

            if destination.exists() or self._is_link(destination):
                raise ExecutionGatewayError("Validation staging identity already exists", code="validation_staging_collision")
            copied: list[str] = []
            try:
                if self._is_link(root.parent) or self._is_link(root):
                    raise OSError("canonical staging root contains a link")
                root.mkdir(parents=True, exist_ok=True)
                if root.resolve() != root:
                    raise OSError("canonical staging root identity changed")
                if self._is_link(namespace_root):
                    raise OSError("staging namespace contains a link")
                namespace_root.mkdir(exist_ok=True)
                if namespace_root.resolve() != namespace_root:
                    raise OSError("staging namespace identity changed")
                if raw_source.resolve(strict=True) != source:
                    raise OSError("source root identity changed before staging")
                destination.mkdir(exist_ok=False)
                for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
                    current = Path(dirpath)
                    relative_dir = current.relative_to(source)
                    dirnames[:] = [
                        name for name in dirnames
                        if (relative_dir.parts or name not in ignores) and not self._is_link(current / name)
                    ]
                    target_dir = destination / relative_dir
                    if relative_dir.parts:
                        target_dir.mkdir(parents=True, exist_ok=True)
                        copied.append(relative_dir.as_posix())
                    for filename in filenames:
                        source_file = current / filename
                        if self._is_link(source_file) or not source_file.is_file():
                            continue
                        relative_file = source_file.relative_to(source)
                        if relative_file.parts and relative_file.parts[0] in ignores:
                            continue
                        target_file = destination / relative_file
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_file, target_file, follow_symlinks=False)
                        if self._is_link(target_file):
                            target_file.unlink(missing_ok=True)
                            raise OSError("validation copy unexpectedly produced a link")
                        copied.append(relative_file.as_posix())
                self._active.add(owner_key)
            except OSError as exc:
                if destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                try:
                    namespace_root.rmdir()
                except OSError:
                    pass
                raise ExecutionGatewayError(f"Validation staging materialization failed: {exc}", code="validation_staging_create_failed") from exc

        copied_paths = sorted(set(copied))
        digest = hashlib.sha256("\n".join(copied_paths).encode("utf-8")).hexdigest()
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "staging_root": str(destination),
            "staging_id": staging_id,
            "label": namespace,
            "copied_paths": copied_paths,
            "copied_paths_sha256": digest,
            "receipt_id": f"validation-stage:{staging_id}:{digest}",
        }

"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
import hashlib
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Mapping
from execution_request import ExecutionRequest, stable_digest


class ProjectWriteEffectAdapter:
    """Gateway-owned adapter for bounded project-file and project lifecycle writes."""

    effect_ids = frozenset({"project.write"})
    _FILE_RESOURCE = "project_file"
    _OPERATION_RESOURCE = "project_operation"
    _OPERATIONS = frozenset({"init", "link", "seed", "demo"})
    _FORBIDDEN_SEGMENTS = frozenset({".git", ".env", "node_modules", ".venv", "venv", "dist", "release", "__pycache__"})
    _LOCKS_GUARD = threading.RLock()
    _LOCKS: dict[str, threading.RLock] = {}

    @staticmethod
    def _trusted_root(manager: Any) -> Path:
        raw_root = str(getattr(manager, "project_root", "") or "").strip()
        if not raw_root:
            raise ExecutionGatewayError(
                "Project write requires SessionManager project_root",
                code="project_write_root_required",
            )
        return Path(raw_root).expanduser().resolve()

    @classmethod
    def _root_lock(cls, root: Path) -> threading.RLock:
        key = os.path.normcase(str(root))
        with cls._LOCKS_GUARD:
            return cls._LOCKS.setdefault(key, threading.RLock())

    @classmethod
    def _validate_operation_target(cls, trusted_root: Path, raw_path: str, operation: str) -> Path:
        clean_path = str(raw_path or "").strip()
        if not clean_path:
            raise ExecutionGatewayError(
                "Project operation target path is required",
                code="project_write_path_required",
            )
        candidate = Path(clean_path).expanduser()
        if not candidate.is_absolute():
            raise ExecutionGatewayError(
                "Project operation target must be absolute",
                code="project_write_path_absolute_required",
            )
        lexical = candidate
        if lexical.is_symlink():
            raise ExecutionGatewayError(
                "Project operation target cannot be a symlink",
                code="project_write_symlink_forbidden",
            )
        target = lexical.resolve()
        if operation in {"init", "link", "seed"}:
            if target != trusted_root:
                raise ExecutionGatewayError(
                    "Project lifecycle target does not match its authorized root",
                    code="project_write_root_mismatch",
                )
            if target.name.lower() in cls._FORBIDDEN_SEGMENTS:
                raise ExecutionGatewayError(
                    "Project operation target contains a forbidden segment",
                    code="project_write_forbidden_path",
                )
            return target
        try:
            relative = target.relative_to(trusted_root)
        except ValueError as exc:
            raise ExecutionGatewayError(
                "Project operation target is outside its trusted root",
                code="project_write_path_out_of_scope",
            ) from exc
        if any(part.lower() in cls._FORBIDDEN_SEGMENTS for part in relative.parts):
            raise ExecutionGatewayError(
                "Project operation target contains a forbidden segment",
                code="project_write_forbidden_path",
            )
        if operation == "demo" and target == trusted_root:
            raise ExecutionGatewayError(
                "Demo project requires a dedicated child directory",
                code="project_write_demo_target_invalid",
            )
        return target

    @staticmethod
    def operation_descriptor(target: Path, operation: str) -> dict[str, Any]:
        """Return a stable pre-mutation descriptor without reading secret content."""

        clean_operation = str(operation or "").strip().lower()
        target = Path(target).expanduser().resolve()
        entries: list[dict[str, Any]] = []
        if target.exists():
            if not target.is_dir():
                raise ExecutionGatewayError(
                    "Project operation target must be a directory",
                    code="project_write_target_invalid",
                )
            scan_root = target
            if clean_operation in {"init", "link"}:
                scan_root = target / ".bago"
            if scan_root.exists():
                for path in sorted(scan_root.rglob("*"), key=lambda item: str(item).lower()):
                    try:
                        relative = path.relative_to(target).as_posix()
                        stat = path.lstat()
                    except OSError as exc:
                        raise ExecutionGatewayError(
                            f"Project target cannot be fingerprinted: {exc}",
                            code="project_write_target_unreadable",
                        ) from exc
                    entries.append({
                        "path": relative,
                        "kind": "symlink" if path.is_symlink() else "dir" if path.is_dir() else "file",
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "link": os.readlink(path) if path.is_symlink() else "",
                    })
        return {
            "operation": clean_operation,
            "path": str(target),
            "exists": target.exists(),
            "entries": entries,
        }

    @classmethod
    def operation_descriptor_digest(cls, target: Path, operation: str) -> str:
        return stable_digest(cls.operation_descriptor(target, operation))

    @classmethod
    def prepare_operation(cls, manager: Any, raw_path: str, operation: str) -> tuple[Path, Path, str]:
        clean_operation = str(operation or "").strip().lower()
        if clean_operation not in cls._OPERATIONS:
            raise ExecutionGatewayError(
                "Project write operation is not approved",
                code="project_write_operation_invalid",
            )
        raw_target = Path(str(raw_path or "").strip()).expanduser()
        trusted_root = (
            raw_target.resolve()
            if clean_operation in {"init", "link", "seed"} and raw_target.is_absolute()
            else cls._trusted_root(manager)
        )
        target = cls._validate_operation_target(trusted_root, raw_path, clean_operation)
        return trusted_root, target, cls.operation_descriptor_digest(target, clean_operation)

    @staticmethod
    def _execute_project_operation(target: Path, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        import project_memory

        if operation == "init":
            return dict(project_memory.init_project(target))
        if operation == "link":
            return dict(project_memory.link_project(target))
        if operation == "seed":
            depth = max(1, min(int(arguments.get("depth", 3)), 8))
            ref_value = str(arguments.get("ref") or "").strip()
            return dict(project_memory.seed_project(target, depth=depth, ref=ref_value or None))
        if operation == "demo":
            return dict(project_memory.create_demo_project(target))
        raise ExecutionGatewayError(
            "Project write operation is not approved",
            code="project_write_operation_invalid",
        )

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Project write requires SessionManager context",
                code="execution_context_manager_required",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("state") != "consumed":
            raise ExecutionGatewayError(
                "Project write requires consumed gateway authorization",
                code="project_write_authorization_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if not manager_session or manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )

        # The authorized request binds the selected root and target digest.
        # Do not compare it to the manager's current root: a separately
        # authorized workspace switch is valid, while target revalidation below
        # still rejects tampering between approval and execution.
        root_text = str(request.target.get("allowed_root") or "").strip()
        if not root_text:
            raise ExecutionGatewayError(
                "Project write trusted root is missing",
                code="project_write_root_mismatch",
            )
        root = Path(root_text).expanduser().resolve()
        resource = str(request.target.get("resource") or "").strip()
        if resource not in {self._FILE_RESOURCE, self._OPERATION_RESOURCE}:
            raise ExecutionGatewayError(
                "Project write resource is not approved",
                code="project_write_resource_invalid",
            )

        raw_path = str(request.target.get("path") or "").strip()
        if not raw_path:
            raise ExecutionGatewayError(
                "Project write target path is required",
                code="project_write_path_required",
            )
        if resource == self._OPERATION_RESOURCE:
            operation = str(request.target.get("operation") or "").strip().lower()
            if operation not in self._OPERATIONS:
                raise ExecutionGatewayError(
                    "Project write operation is not approved",
                    code="project_write_operation_invalid",
                )
            if request.scope != "workspace":
                raise ExecutionGatewayError(
                    "Project operation scope is not approved",
                    code="project_write_scope_invalid",
                )
            target = self._validate_operation_target(root, raw_path, operation)
            approved_digest = str(request.target.get("root_digest") or "").strip()
            if not approved_digest:
                raise ExecutionGatewayError(
                    "Project operation request lacks target digest",
                    code="project_write_digest_required",
                )
            arguments = request.arguments if isinstance(request.arguments, dict) else {}
            current_root = self._trusted_root(manager)
            should_activate = operation in {"init", "link", "seed"} and target != current_root
            rebind = getattr(manager, "rebind_project_root", None)
            if should_activate and not callable(rebind):
                raise ExecutionGatewayError(
                    "SessionManager does not expose rebind_project_root()",
                    code="project_write_rebind_unavailable",
                )
            with self._root_lock(root):
                current_digest = self.operation_descriptor_digest(target, operation)
                if current_digest != approved_digest:
                    raise ExecutionGatewayError(
                        "Project target changed after authorization request was constructed",
                        code="project_write_target_changed",
                    )
                try:
                    result = self._execute_project_operation(target, operation, arguments)
                    if should_activate:
                        rebind(target)
                except ExecutionGatewayError:
                    raise
                except Exception as exc:
                    raise ExecutionGatewayError(
                        f"Project operation failed: {exc}",
                        code="project_write_failed",
                    ) from exc
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
                "evidence": [
                    f"operation:{operation}",
                    f"path:{target}",
                    f"target_digest:{approved_digest}",
                ],
                "receipt_id": f"project-write:sha256:{receipt_digest}",
            }

        candidate = Path(raw_path).expanduser()
        lexical = candidate if candidate.is_absolute() else root / candidate
        if lexical.is_symlink():
            raise ExecutionGatewayError(
                "Project write target cannot be a symlink",
                code="project_write_symlink_forbidden",
            )
        target = lexical.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ExecutionGatewayError(
                "Project write target is outside its trusted root",
                code="project_write_path_out_of_scope",
            ) from exc
        if target == root:
            raise ExecutionGatewayError(
                "Project write target must be a file",
                code="project_write_target_invalid",
            )
        if any(part.lower() in self._FORBIDDEN_SEGMENTS for part in target.parts):
            raise ExecutionGatewayError(
                "Project write target contains a forbidden segment",
                code="project_write_forbidden_path",
            )
        if target.exists() and not target.is_file():
            raise ExecutionGatewayError(
                "Project write target must be a file",
                code="project_write_target_invalid",
            )

        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        content = str(arguments.get("content") or "")
        existed = target.exists()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
            try:
                with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                ServerStateEffectAdapter._replace_with_retry(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Error escribiendo archivo del proyecto: {exc}",
                code="project_write_failed",
            ) from exc

        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        try:
            relative = str(target.relative_to(root)).replace("\\", "/")
        except ValueError:
            relative = str(target)
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "resource": self._FILE_RESOURCE,
            "path": relative,
            "absolute_path": str(target),
            "project_root": str(root),
            "created": not existed,
            "overwritten": existed,
            "bytes_written": len(content.encode("utf-8")),
            "evidence": [f"file_sha256:{digest}", f"path:{target}"],
            "receipt_id": f"project-write:sha256:{digest}",
        }

"""Closed execution gateway for governed BAGO effects.

Callers submit an ExecutionRequest plus a Permit. They cannot supply a callable.
The gateway resolves the executable adapter from a server-owned registry keyed
by canonical effect_id.
"""

from __future__ import annotations

import hashlib
import base64
import os
import threading
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from authorization_boundary import AuthorizationBoundary, AuthorizationError
from effect_registry import REGISTRY
from execution_request import ExecutionRequest, stable_digest


class ExecutionGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "execution_gateway_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Trusted runtime dependencies, never part of user authority."""

    manager: Any = None
    services: Mapping[str, Any] = field(default_factory=dict)


class EffectAdapter(Protocol):
    effect_ids: frozenset[str]

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        ...


class EffectAdapterRegistry:
    """Server-owned mapping from effect_id to implementation."""

    def __init__(self) -> None:
        self._by_effect: dict[str, EffectAdapter] = {}

    def register(self, adapter: EffectAdapter) -> None:
        effect_ids = getattr(adapter, "effect_ids", frozenset())
        if not effect_ids:
            raise ExecutionGatewayError(
                "Effect adapter must declare at least one effect_id",
                code="execution_adapter_effects_required",
            )
        for effect_id in effect_ids:
            clean = str(effect_id or "").strip()
            if not clean:
                raise ExecutionGatewayError(
                    "Effect adapter contains an empty effect_id",
                    code="execution_adapter_effect_invalid",
                )
            if not REGISTRY.contains(clean):
                raise ExecutionGatewayError(
                    f"Effect adapter declares unknown canonical effect_id {clean}",
                    code="execution_adapter_effect_unknown",
                )
            if clean in self._by_effect:
                raise ExecutionGatewayError(
                    f"Effect adapter already registered for {clean}",
                    code="execution_adapter_duplicate",
                )
        for effect_id in effect_ids:
            self._by_effect[str(effect_id)] = adapter

    def resolve(self, effect_id: str) -> EffectAdapter:
        clean = str(effect_id or "").strip()
        adapter = self._by_effect.get(clean)
        if adapter is None:
            raise ExecutionGatewayError(
                f"No EffectAdapter registered for {clean}",
                code="execution_adapter_missing",
            )
        return adapter

    def registered_effects(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_effect))


class CapabilityRuntimeEffectAdapter:
    """Governed adapter for imported Capability Package runtime."""

    effect_ids = frozenset({"capability.execute", "pipeline.execute"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from capability_packages import (
            CapabilityPackageError,
            execute_package,
            execute_pipeline_package,
            get_package,
        )

        package_id = str(request.target.get("package_id") or "").strip()
        if not package_id:
            raise ExecutionGatewayError(
                "Capability runtime target requires package_id",
                code="execution_target_missing",
            )
        package = get_package(package_id)
        expected_kind = "pipeline" if request.effect_id == "pipeline.execute" else "capability"
        requested_digest = str(request.target.get("package_digest") or "").strip()
        current_digest = str(package.get("digest") or "").strip()
        if requested_digest and requested_digest != current_digest:
            raise ExecutionGatewayError(
                "Package changed after authorization request was constructed",
                code="execution_target_digest_mismatch",
            )
        if str(package.get("kind") or "") != expected_kind:
            raise ExecutionGatewayError(
                f"Effect {request.effect_id} cannot execute package kind {package.get('kind')}",
                code="execution_target_kind_mismatch",
            )
        manager = context.manager
        if manager is not None:
            manager_session = str(getattr(manager, "session_id", "") or "")
            if manager_session and manager_session != request.session_id:
                raise ExecutionGatewayError(
                    "ExecutionContext manager belongs to another session",
                    code="execution_context_session_mismatch",
                )

        permissions = list(package.get("permissions", []))
        if request.effect_id == "pipeline.execute":
            if manager is None:
                raise ExecutionGatewayError(
                    "Pipeline execution requires SessionManager context",
                    code="execution_context_manager_required",
                )
            return execute_pipeline_package(
                package_id,
                inputs=request.arguments,
                confirmed=True,
                approved_permissions=permissions,
                manager=manager,
            )
        return execute_package(
            package_id,
            inputs=request.arguments,
            confirmed=True,
            approved_permissions=permissions,
        )


class FilesystemEffectAdapter:
    """Gateway-owned adapter for one scoped workspace file write."""

    effect_ids = frozenset({"filesystem.write"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from filesystem_effects import FilesystemEffectError, write_file_effect

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Filesystem write requires SessionManager context",
                code="execution_context_manager_required",
            )
        if not isinstance(context.services.get("_authorization"), dict):
            raise ExecutionGatewayError(
                "Filesystem write requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager_session and manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )
        raw_path = str(request.target.get("path") or "").strip()
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        content = str(arguments.get("content") or "")
        try:
            return write_file_effect(manager, raw_path, content)
        except FilesystemEffectError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc



class FilesystemReadEffectAdapter:
    """Gateway-owned adapter for one scoped, read-only plan child."""

    effect_ids = frozenset({"filesystem.read"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from filesystem_effects import FilesystemEffectError, read_file_effect

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Filesystem read requires SessionManager context",
                code="execution_context_manager_required",
            )
        if not isinstance(context.services.get("_authorization"), dict):
            raise ExecutionGatewayError(
                "Filesystem read requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager_session and manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )
        try:
            return read_file_effect(manager, str(request.target.get("path") or ""))
        except FilesystemEffectError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc


class WorkspaceBindEffectAdapter:
    """Gateway-owned adapter for binding and persisting one workspace.

    ``rebind_project_root`` is a compound effect: it rebuilds the session
    mirror and rewires the live session roots.  The HTTP handler must never
    call it directly.  This adapter is the only server-owned execution point
    for ``workspace.bind`` and revalidates the target immediately before the
    first material mutation.
    """

    effect_ids = frozenset({"workspace.bind"})
    _RESOURCE = "session_workspace"
    _OPERATION = "persist"
    _LOCKS_GUARD = threading.RLock()
    _LOCKS: dict[str, threading.RLock] = {}

    @classmethod
    def _session_lock(cls, session_id: str) -> threading.RLock:
        with cls._LOCKS_GUARD:
            return cls._LOCKS.setdefault(session_id, threading.RLock())

    @staticmethod
    def _require_authorization(context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("state") != "consumed":
            raise ExecutionGatewayError(
                "Workspace binding requires consumed gateway authorization",
                code="workspace_bind_authorization_required",
            )
        return authorization

    @staticmethod
    def _validate_target(manager: Any, raw_path: str) -> Path:
        clean_path = str(raw_path or "").strip()
        if not clean_path:
            raise ExecutionGatewayError(
                "Workspace binding target path is required",
                code="workspace_bind_path_required",
            )
        candidate = Path(clean_path).expanduser()
        if not candidate.is_absolute():
            raise ExecutionGatewayError(
                "Workspace binding target must be absolute",
                code="workspace_bind_path_absolute_required",
            )

        validator = getattr(manager, "_validate_project_root", None)
        if not callable(validator):
            try:
                from session_manager import SessionManager

                validator = SessionManager._validate_project_root
            except (ImportError, AttributeError) as exc:
                raise ExecutionGatewayError(
                    "Workspace binding validator is unavailable",
                    code="workspace_bind_validator_missing",
                ) from exc

        try:
            validated = validator(candidate, require_identity=True)
        except Exception as exc:
            raise ExecutionGatewayError(
                f"Workspace binding target is not valid: {exc}",
                code="workspace_bind_target_invalid",
            ) from exc

        target = Path(validated).expanduser().resolve()
        if not target.is_dir():
            raise ExecutionGatewayError(
                "Workspace binding target must be a directory",
                code="workspace_bind_target_invalid",
            )
        return target

    @staticmethod
    def binding_descriptor(target: Path) -> dict[str, Any]:
        from workspace_binding import resolve_workspace_binding

        binding = resolve_workspace_binding(target)
        return {
            "framework_root": binding.framework_root,
            "project_root": binding.project_root,
            "workspace_state_root": binding.workspace_state_root,
            "workspace_scope_root": binding.workspace_scope_root,
            "workspace_id": binding.workspace_id,
            "manifest_path": binding.manifest_path,
            "manifest_exists": binding.manifest_exists,
            "binding_confirmed": binding.binding_confirmed,
            "binding_reason": binding.binding_reason,
        }

    @staticmethod
    def binding_descriptor_digest(binding: Mapping[str, Any]) -> str:
        return stable_digest(dict(binding))

    @classmethod
    def validate_target(cls, manager: Any, raw_path: str) -> Path:
        """Pure preflight used by the HTTP surface before issuing a challenge."""

        return cls._validate_target(manager, raw_path)

    @staticmethod
    def _persist_last_workspace(target: Path) -> dict[str, Any]:
        from bago_core.atomic_json import write_json_atomic

        last_workspace = Path.home() / ".bago" / "last_workspace.json"
        return write_json_atomic(last_workspace, {"path": str(target)})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Workspace binding requires SessionManager context",
                code="execution_context_manager_required",
            )
        self._require_authorization(context)

        manager_session = str(getattr(manager, "session_id", "") or "")
        if not manager_session or manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )
        if str(request.target.get("resource") or "").strip() != self._RESOURCE:
            raise ExecutionGatewayError(
                "Workspace binding resource is not approved",
                code="workspace_bind_resource_invalid",
            )
        if str(request.target.get("operation") or "").strip().lower() != self._OPERATION:
            raise ExecutionGatewayError(
                "Workspace binding operation is not approved",
                code="workspace_bind_operation_invalid",
            )

        rebind = getattr(manager, "rebind_project_root", None)
        save = getattr(manager, "save", None)
        if not callable(rebind):
            raise ExecutionGatewayError(
                "SessionManager does not expose rebind_project_root()",
                code="workspace_bind_rebind_unavailable",
            )
        if not callable(save):
            raise ExecutionGatewayError(
                "SessionManager does not expose save()",
                code="workspace_bind_save_unavailable",
            )

        with self._session_lock(manager_session):
            # This is deliberately the last validation before the compound
            # operation.  No rebind, save, or last-workspace write may happen
            # before this check succeeds, and concurrent binds for one live
            # session cannot interleave their lifecycle mutations.
            target = self._validate_target(manager, str(request.target.get("path") or ""))
            approved_binding_digest = str(request.target.get("binding_digest") or "").strip()
            if not approved_binding_digest:
                raise ExecutionGatewayError(
                    "Workspace binding request lacks binding digest",
                    code="workspace_bind_binding_digest_required",
                )
            current_binding = self.binding_descriptor(target)
            current_binding_digest = self.binding_descriptor_digest(current_binding)
            if current_binding_digest != approved_binding_digest:
                raise ExecutionGatewayError(
                    "Workspace binding changed after authorization request was constructed",
                    code="workspace_bind_binding_changed",
                )
            if str(request.target.get("workspace_id") or "") != str(current_binding["workspace_id"]):
                raise ExecutionGatewayError(
                    "Workspace binding identity changed after authorization request was constructed",
                    code="workspace_bind_identity_changed",
                )
            if str(request.target.get("workspace_scope_root") or "") != str(current_binding["workspace_scope_root"]):
                raise ExecutionGatewayError(
                    "Workspace binding scope changed after authorization request was constructed",
                    code="workspace_bind_scope_changed",
                )

            current_root_value = str(getattr(manager, "project_root", "") or "").strip()
            current_root = Path(current_root_value).expanduser().resolve() if current_root_value else None
            rebound = current_root != target
            if rebound:
                try:
                    rebind(target)
                except Exception as exc:
                    raise ExecutionGatewayError(
                        f"No se pudo activar el workspace {target}: {exc}",
                        code="workspace_bind_rebind_failed",
                    ) from exc

            try:
                save_receipt = save()
            except Exception as exc:
                raise ExecutionGatewayError(
                    f"El workspace se activó, pero no pudo persistirse: {exc}",
                    code="workspace_bind_save_failed",
                ) from exc
            session_json_persisted = True
            session_db_indexed: bool | None = None
            session_json_receipt_id = ""
            if isinstance(save_receipt, dict):
                session_json_persisted = bool(save_receipt.get("session_json_persisted", True))
                session_db_indexed = save_receipt.get("session_db_indexed")
                session_json_receipt = save_receipt.get("session_json_receipt")
                if isinstance(session_json_receipt, dict):
                    session_json_receipt_id = str(session_json_receipt.get("receipt_id") or "")
            if not session_json_persisted or session_db_indexed is False:
                raise ExecutionGatewayError(
                    "El workspace se activó, pero no quedó persistida toda la sesión",
                    code="workspace_bind_save_failed",
                )

            try:
                last_workspace_receipt = self._persist_last_workspace(target)
            except Exception as exc:
                raise ExecutionGatewayError(
                    f"El workspace se activó, pero no pudo guardarse como último workspace: {exc}",
                    code="workspace_bind_last_path_failed",
                ) from exc

            workspace_id = str(getattr(manager, "workspace_id", current_binding["workspace_id"]) or "")
            try:
                workspace_state = manager.workspace_state()
            except Exception:
                workspace_state = {}
            return {
                "ok": True,
                "executed": True,
                "effect_id": request.effect_id,
                "resource": self._RESOURCE,
                "operation": self._OPERATION,
                "saved": str(target),
                "path": str(target),
                "workspace_id": workspace_id,
                "workspace_state_root": str(workspace_state.get("workspace_state_root", "")),
                "rebound": rebound,
                "session_json_persisted": session_json_persisted,
                "session_db_indexed": session_db_indexed,
                "last_workspace_persisted": True,
                "binding_digest": approved_binding_digest,
                "evidence": [
                    f"path:{target}",
                    f"previous_root:{current_root or ''}",
                    f"workspace_id:{workspace_id}",
                    f"binding_digest:{approved_binding_digest}",
                    f"rebound:{str(rebound).lower()}",
                    f"session_json_persisted:{str(session_json_persisted).lower()}",
                    f"session_db_indexed:{str(session_db_indexed).lower() if session_db_indexed is not None else 'unknown'}",
                    f"session_json_receipt:{session_json_receipt_id}",
                    "last_workspace_persisted:true",
                    f"last_workspace_receipt:{last_workspace_receipt.get('receipt_id', '') if isinstance(last_workspace_receipt, dict) else ''}",
                ],
                "receipt_id": f"workspace-bind:sha256:{hashlib.sha256(request.fingerprint.encode('utf-8')).hexdigest()}",
            }


class StateDeleteEffectAdapter:
    """Gateway-owned adapter for the one bounded session-state deletion.

    Wave B starts with the router's session-model override because it is a
    destructive effect with a single canonical target.  The adapter owns the
    final unlink and derives its trusted root from the live SessionManager;
    callers can request only the exact session override, never an arbitrary
    state path.
    """

    effect_ids = frozenset({"state.delete"})
    _RESOURCE = "session_model_override"
    _FILENAME = ".bago_session_model.json"

    @staticmethod
    def _trusted_root(manager: Any) -> Path:
        raw_root = str(getattr(manager, "state_root", "") or "").strip()
        if not raw_root:
            raise ExecutionGatewayError(
                "State deletion requires SessionManager state_root",
                code="state_delete_root_required",
            )
        return Path(raw_root).expanduser().resolve()

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "State deletion requires SessionManager context",
                code="execution_context_manager_required",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("state") != "consumed":
            raise ExecutionGatewayError(
                "State deletion requires consumed gateway authorization",
                code="state_delete_authorization_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )

        root = self._trusted_root(manager)
        target_root = Path(str(request.target.get("allowed_root") or "")).expanduser().resolve()
        if target_root != root:
            raise ExecutionGatewayError(
                "State deletion trusted root is missing or changed",
                code="state_delete_root_mismatch",
            )
        resource = str(request.target.get("resource") or "").strip()
        if resource != self._RESOURCE:
            raise ExecutionGatewayError(
                "State deletion resource is not approved",
                code="state_delete_resource_invalid",
            )

        raw_path = str(request.target.get("path") or "").strip()
        if not raw_path:
            raise ExecutionGatewayError(
                "State deletion target path is required",
                code="state_delete_path_required",
            )
        lexical = Path(raw_path).expanduser()
        lexical = lexical if lexical.is_absolute() else root / lexical
        if lexical.is_symlink():
            raise ExecutionGatewayError(
                "State deletion target cannot be a symlink",
                code="state_delete_symlink_forbidden",
            )
        target = lexical.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ExecutionGatewayError(
                "State deletion target is outside its trusted root",
                code="state_delete_path_out_of_scope",
            ) from exc
        if target != root / self._FILENAME:
            raise ExecutionGatewayError(
                "State deletion target is not the session model override",
                code="state_delete_target_invalid",
            )
        if target.exists() and not target.is_file():
            raise ExecutionGatewayError(
                "State deletion target must be a file",
                code="state_delete_target_invalid",
            )

        existed = target.exists()
        prior_digest = "missing"
        if existed:
            try:
                prior_digest = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError as exc:
                raise ExecutionGatewayError(
                    f"Error leyendo el override de modelo: {exc}",
                    code="state_delete_read_failed",
                ) from exc

        try:
            target.unlink()
            deleted = True
        except FileNotFoundError:
            deleted = False
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Error eliminando el override de modelo: {exc}",
                code="state_delete_failed",
            ) from exc

        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "resource": self._RESOURCE,
            "path": self._FILENAME,
            "absolute_path": str(target),
            "deleted": deleted,
            "evidence": [
                f"path:{target}",
                f"prior_sha256:{prior_digest}",
                f"deleted:{str(deleted).lower()}",
            ],
            "receipt_id": f"state-delete:sha256:{prior_digest}",
        }


_SERVER_STATE_EFFECTS = frozenset({
    "state.write",
    "config.write",
    "memory.write",
    "agent.definition.write",
})
_SERVER_STATE_WRITE_LOCK = threading.RLock()


class ServerStateEffectAdapter:
    """Server-owned adapter for policy-authorized persistent state writes.

    The adapter owns the only material write implementation for this family.
    Callers can select a target path and payload, but cannot supply an
    executor. The gateway supplies the policy authorization and the trusted
    root; this adapter checks the root again immediately before the effect.
    """

    effect_ids = _SERVER_STATE_EFFECTS
    server_policy_only = True

    _FORBIDDEN_SEGMENTS = frozenset({".git", ".env", "node_modules", ".venv", "venv"})

    @staticmethod
    def _resolved_target(raw_path: str, raw_root: str) -> tuple[Path, Path]:
        root = Path(str(raw_root or "")).expanduser().resolve()
        if not str(raw_path or "").strip():
            raise ExecutionGatewayError(
                "Server state target path is required",
                code="server_state_path_required",
            )
        candidate = Path(str(raw_path)).expanduser()
        target = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ExecutionGatewayError(
                "Server state target is outside its trusted root",
                code="server_state_path_out_of_scope",
            ) from exc
        if target == root:
            raise ExecutionGatewayError(
                "Server state target must be a file",
                code="server_state_target_invalid",
            )
        if any(part.lower() in ServerStateEffectAdapter._FORBIDDEN_SEGMENTS for part in target.parts):
            raise ExecutionGatewayError(
                "Server state target contains a forbidden segment",
                code="server_state_forbidden_path",
            )
        if target.exists() and target.is_symlink():
            raise ExecutionGatewayError(
                "Server state target cannot be a symlink",
                code="server_state_symlink_forbidden",
            )
        return target, root

    @staticmethod
    def _replace_with_retry(temporary: Path, target: Path) -> None:
        for attempt in range(8):
            try:
                os.replace(temporary, target)
                return
            except PermissionError:
                if os.name != "nt" or attempt == 7:
                    raise
                time.sleep(0.02 * (2**attempt))

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Persistent state requires server-owned policy authorization",
                code="server_state_authorization_required",
            )
        expected_root = str(context.services.get("_server_allowed_root") or "").strip()
        target_root = str(request.target.get("allowed_root") or "").strip()
        if not expected_root or target_root != expected_root:
            raise ExecutionGatewayError(
                "Persistent state trusted root is missing or changed",
                code="server_state_root_mismatch",
            )
        target, root = self._resolved_target(str(request.target.get("path") or ""), expected_root)
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        operation = str(request.target.get("operation") or "replace_text").strip().lower()
        content = str(arguments.get("content") or "")

        try:
            with _SERVER_STATE_WRITE_LOCK:
                target.parent.mkdir(parents=True, exist_ok=True)
                if operation == "append_text":
                    with target.open("a", encoding="utf-8", newline="\n") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                elif operation == "replace_text":
                    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
                    try:
                        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                            handle.write(content)
                            handle.flush()
                            os.fsync(handle.fileno())
                        self._replace_with_retry(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
                else:
                    raise ExecutionGatewayError(
                        f"Unsupported server state operation: {operation}",
                        code="server_state_operation_invalid",
                    )
        except ExecutionGatewayError:
            raise
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Error escribiendo estado persistente: {exc}",
                code="server_state_write_failed",
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
            "operation": operation,
            "path": relative,
            "absolute_path": str(target),
            "evidence": [f"file_sha256:{digest}", f"path:{target}"],
            "receipt_id": f"{request.effect_id}:sha256:{digest}",
        }


class GatewayHTTPResponse:
    """urllib-compatible response proxy that preserves incremental reads."""

    def __init__(self, response: Any, *, status: int, headers: Mapping[str, Any], url: str) -> None:
        self._response = response
        self.status = int(status)
        self.code = self.status
        self.headers = headers
        self.url = str(url)

    def read(self, amount: int = -1) -> bytes:
        try:
            return self._response.read(amount)
        except TypeError:
            return self._response.read()

    def readinto(self, buffer: Any) -> int:
        reader = getattr(self._response, "readinto", None)
        if callable(reader):
            return int(reader(buffer))
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def close(self) -> None:
        close = getattr(self._response, "close", None)
        if callable(close):
            return close()
        return None

    def __enter__(self) -> "GatewayHTTPResponse":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def __iter__(self):
        return iter(self._response)


class NetworkReadEffectAdapter:
    """Server-owned policy adapter for approved BAGO transport reads.

    Provider inference calls may use HTTP POST at the transport layer, but
    this adapter is only reachable for an explicitly classified BAGO transport
    surface. Release, GitHub and arbitrary external mutations remain outside
    this policy adapter and must use their explicit effects in later waves.
    """

    effect_ids = frozenset({"network.read"})
    server_policy_only = True
    _ALLOWED_CLASSES = frozenset({"provider_transport", "runtime_probe", "local_discovery"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Network read requires server-owned policy authorization",
                code="network_read_authorization_required",
            )
        network_class = str(request.target.get("network_class") or "").strip()
        if network_class not in self._ALLOWED_CLASSES:
            raise ExecutionGatewayError(
                "Network target is not an approved BAGO transport surface",
                code="network_read_surface_blocked",
            )
        url = str(request.target.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            raise ExecutionGatewayError(
                "Network target must use HTTP(S)",
                code="network_read_url_invalid",
            )
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        method = str(request.target.get("method") or "GET").upper()
        headers = arguments.get("headers") if isinstance(arguments.get("headers"), dict) else {}
        encoded_data = str(arguments.get("data_b64") or "")
        try:
            data = base64.b64decode(encoded_data) if encoded_data else None
            outbound = urllib.request.Request(
                url,
                data=data,
                headers={str(key): str(value) for key, value in headers.items()},
                method=method,
            )
            timeout = float(request.target.get("timeout") or 30.0)
            response = urllib.request.urlopen(outbound, timeout=timeout)
            raw_headers = getattr(response, "headers", {})
            response_headers = raw_headers if hasattr(raw_headers, "items") else dict(raw_headers)
            getcode = getattr(response, "getcode", None)
            status = int(getattr(response, "status", getcode() if callable(getcode) else 200))
            geturl = getattr(response, "geturl", None)
            final_url = str(geturl() if callable(geturl) else url)
        except ExecutionGatewayError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError):
            # Preserve urllib's typed transport errors for provider retry and
            # fallback policies; the effect has already been authorized and
            # no caller-side sink is reintroduced by re-raising the error.
            raise
        except OSError:
            # Local discovery and provider fallback already treat transport
            # availability as a recoverable OSError boundary. Preserve that
            # contract after the server-owned dispatch.
            raise
        except Exception as exc:
            raise ExecutionGatewayError(
                f"Network read failed: {exc}",
                code="network_read_failed",
            ) from exc
        return GatewayHTTPResponse(
            response,
            status=status,
            headers=response_headers,
            url=final_url,
        )


class PlanRuntimeEffectAdapter:
    """Governed 04-FIX2 adapter for PlanEngine execution."""

    effect_ids = frozenset({"plan.execute"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from governed_work_pipeline import GovernedWorkError, execute_plan_through_gateway

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Plan execution requires SessionManager context",
                code="execution_context_manager_required",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict):
            raise ExecutionGatewayError(
                "Plan execution requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        gateway = context.services.get("_gateway")
        if not isinstance(gateway, ExecutionGateway):
            raise ExecutionGatewayError(
                "Plan execution requires the active ExecutionGateway",
                code="execution_gateway_context_required",
            )
        engine = getattr(manager, "plan_engine", None)
        if engine is None:
            raise ExecutionGatewayError(
                "PlanEngine no disponible",
                code="plan_engine_missing",
            )
        plan_id = str(request.target.get("plan_id") or "").strip()
        plan = engine.get_plan(plan_id)
        if plan is None:
            raise ExecutionGatewayError(
                f"Plan no encontrado: {plan_id}",
                code="plan_not_found",
            )
        try:
            return execute_plan_through_gateway(
                plan=plan,
                engine=engine,
                parent_request=request,
                authorization=authorization,
                gateway=gateway,
                context=context,
            )
        except GovernedWorkError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc


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
        if operation in {"init", "link", "seed"} and target != trusted_root:
            raise ExecutionGatewayError(
                "Project lifecycle operations require the active project root",
                code="project_write_root_mismatch",
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
        trusted_root = cls._trusted_root(manager)
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
            target = self._validate_operation_target(root, raw_path, operation)
            approved_digest = str(request.target.get("root_digest") or "").strip()
            if not approved_digest:
                raise ExecutionGatewayError(
                    "Project operation request lacks target digest",
                    code="project_write_digest_required",
                )
            arguments = request.arguments if isinstance(request.arguments, dict) else {}
            with self._root_lock(root):
                current_digest = self.operation_descriptor_digest(target, operation)
                if current_digest != approved_digest:
                    raise ExecutionGatewayError(
                        "Project target changed after authorization request was constructed",
                        code="project_write_target_changed",
                    )
                try:
                    result = self._execute_project_operation(target, operation, arguments)
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


class CredentialWriteEffectAdapter:
    """Gateway-owned adapter for the one bounded ``credential.write`` effect.

    ``credential.write`` is E5/``strong`` and not delegable in the canonical
    registry: the adapter rejects any authorization that did not originate
    from a direct, interactive user decision, and never returns the raw
    secret value in its receipt.
    """

    effect_ids = frozenset({"credential.write"})
    _RESOURCE = "provider_credential"
    _OPERATIONS = frozenset({"set", "delete"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from provider_catalog import PROVIDER_CATALOG
        from secret_store import get_secret_store

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Credential write requires SessionManager context",
                code="execution_context_manager_required",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("state") != "consumed":
            raise ExecutionGatewayError(
                "Credential write requires consumed gateway authorization",
                code="credential_write_authorization_required",
            )
        proof = authorization.get("proof")
        provenance = proof.get("provenance") if isinstance(proof, dict) else None
        if not isinstance(provenance, dict) or str(provenance.get("kind") or "") != "direct_user_interaction":
            raise ExecutionGatewayError(
                "Credential write requires strong, direct user authorization",
                code="credential_write_strong_proof_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if not manager_session or manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )

        resource = str(request.target.get("resource") or "").strip()
        if resource != self._RESOURCE:
            raise ExecutionGatewayError(
                "Credential write resource is not approved",
                code="credential_write_resource_invalid",
            )
        operation = str(request.target.get("operation") or "").strip().lower()
        if operation not in self._OPERATIONS:
            raise ExecutionGatewayError(
                "Credential write operation is not approved",
                code="credential_write_operation_invalid",
            )
        provider = str(request.target.get("provider") or "").strip()
        key = str(request.target.get("key") or "").strip()
        if provider not in PROVIDER_CATALOG:
            raise ExecutionGatewayError(
                f"Credential provider is not recognized: {provider}",
                code="credential_write_provider_unknown",
            )
        if key != "api_key":
            raise ExecutionGatewayError(
                f"Credential key is not recognized for provider {provider}: {key}",
                code="credential_write_key_unknown",
            )
        authorized_digest = str(request.target.get("configuration_digest") or "").strip()
        if not authorized_digest:
            raise ExecutionGatewayError(
                "Credential write requires a provider configuration digest",
                code="credential_write_configuration_digest_required",
            )

        # Fail-closed shape/type validation of the non-secret configuration
        # patch bound into this request. The patch must never carry api_key
        # or secret_ref: those fields are SecretStore-owned, never
        # config-digest-owned.
        configuration_patch = request.target.get("configuration_patch")
        if not isinstance(configuration_patch, dict):
            raise ExecutionGatewayError(
                "Credential write requires a non-secret configuration patch",
                code="credential_write_configuration_patch_invalid",
            )
        allowed_patch_fields: dict[str, type] = {
            "enabled": bool,
            "base_url": str,
            "default_model": str,
        }
        forbidden_patch_fields = frozenset({"api_key", "secret_ref"})
        for patch_field, patch_value in configuration_patch.items():
            if patch_field in forbidden_patch_fields:
                raise ExecutionGatewayError(
                    f"Credential write configuration patch may not include secret field: {patch_field}",
                    code="credential_write_configuration_patch_invalid",
                )
            expected_type = allowed_patch_fields.get(patch_field)
            if expected_type is None:
                raise ExecutionGatewayError(
                    f"Credential write configuration patch field is not permitted: {patch_field}",
                    code="credential_write_configuration_patch_invalid",
                )
            if not isinstance(patch_value, expected_type):
                raise ExecutionGatewayError(
                    f"Credential write configuration patch field has invalid type: {patch_field}",
                    code="credential_write_configuration_patch_invalid",
                )

        # Revalidate the authorized configuration digest against the current
        # backend-authoritative provider config (not the possibly-stale
        # digest computed at authorization time). This detects backend
        # config drift that occurred after authorization while still
        # accepting this same-request's own authorized non-secret patch.
        # This must happen before any SecretStore access or mutation.
        config_manager = getattr(manager, "config", None)
        provider_config_getter = getattr(config_manager, "provider_config", None) if config_manager is not None else None
        if not callable(provider_config_getter):
            raise ExecutionGatewayError(
                "Credential write requires an authoritative provider configuration source",
                code="credential_write_configuration_source_unavailable",
            )
        try:
            live_config = provider_config_getter(provider)
        except Exception as exc:
            raise ExecutionGatewayError(
                f"Error leyendo configuración autorizada del proveedor: {exc}",
                code="credential_write_configuration_source_unavailable",
            ) from exc
        if not isinstance(live_config, dict):
            raise ExecutionGatewayError(
                "Authoritative provider configuration is invalid",
                code="credential_write_configuration_source_unavailable",
            )
        candidate_config = dict(live_config)
        candidate_config.update(configuration_patch)
        recomputed_digest = stable_digest(candidate_config)
        if recomputed_digest != authorized_digest:
            raise ExecutionGatewayError(
                "Provider configuration changed since authorization; re-authorize the credential write",
                code="credential_write_configuration_changed",
            )

        secret_store = get_secret_store()
        secret_key = f"providers/{provider}/api_key"

        if operation == "set":
            arguments = request.arguments if isinstance(request.arguments, dict) else {}
            value = str(arguments.get("value") or "")
            if not value:
                raise ExecutionGatewayError(
                    "Credential write value is required for set",
                    code="credential_write_value_required",
                )
            try:
                secret_store.set_secret(secret_key, value)
            except Exception as exc:
                raise ExecutionGatewayError(
                    f"Error guardando credencial: {exc}",
                    code="credential_write_failed",
                ) from exc
            changed = True
            deleted = False
        else:
            try:
                deleted = bool(secret_store.delete_secret(secret_key))
            except Exception as exc:
                raise ExecutionGatewayError(
                    f"Error eliminando credencial: {exc}",
                    code="credential_write_failed",
                ) from exc
            changed = deleted

        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "resource": self._RESOURCE,
            "operation": operation,
            "provider": provider,
            "key": key,
            "changed": changed,
            "deleted": deleted,
            "evidence": [
                f"provider:{provider}",
                f"key:{key}",
                f"operation:{operation}",
            ],
            "receipt_id": f"credential-write:sha256:{hashlib.sha256(request.fingerprint.encode('utf-8')).hexdigest()}",
        }


class DelegationGrantEffectAdapter:
    """Persist an E6 DelegationGrant only after its parent Permit is consumed."""

    effect_ids = frozenset({"schedule.delegate"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from delegation_grant import DelegationGrantRegistry

        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict):
            raise ExecutionGatewayError(
                "Delegation adapter requires gateway-owned authorization context",
                code="execution_delegation_authorization_missing",
            )

        state_dir = context.services.get("state_dir")
        if state_dir is None and context.manager is not None:
            from pathlib import Path

            base_path = Path(getattr(context.manager, "base_path", Path.cwd()))
            state_dir = base_path / ".bago" / "state"
        if state_dir is None:
            raise ExecutionGatewayError(
                "Delegation adapter requires trusted state_dir",
                code="execution_delegation_state_required",
            )

        grant = DelegationGrantRegistry(state_dir).issue_from_authorized_request(
            request,
            authorization,
        )
        return {"ok": True, "delegation_grant": grant}


def build_default_effect_adapter_registry() -> EffectAdapterRegistry:
    registry = EffectAdapterRegistry()
    registry.register(FilesystemEffectAdapter())
    registry.register(FilesystemReadEffectAdapter())
    registry.register(WorkspaceBindEffectAdapter())
    registry.register(StateDeleteEffectAdapter())
    registry.register(ServerStateEffectAdapter())
    registry.register(NetworkReadEffectAdapter())
    registry.register(CapabilityRuntimeEffectAdapter())
    registry.register(PlanRuntimeEffectAdapter())
    registry.register(DelegationGrantEffectAdapter())
    registry.register(ProjectWriteEffectAdapter())
    registry.register(CredentialWriteEffectAdapter())
    return registry


class ExecutionGateway:
    """Consume a Permit and dispatch only through server-owned EffectAdapters."""

    def __init__(
        self,
        boundary: AuthorizationBoundary | None = None,
        adapters: EffectAdapterRegistry | None = None,
    ) -> None:
        self.boundary = boundary or AuthorizationBoundary()
        self.adapters = adapters or build_default_effect_adapter_registry()

    def execute(
        self,
        *,
        permit_token: str,
        request: ExecutionRequest,
        context: ExecutionContext | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        # Resolve first so a configuration error does not consume a valid Permit.
        adapter = self.adapters.resolve(request.effect_id)
        if bool(getattr(adapter, "server_policy_only", False)):
            raise ExecutionGatewayError(
                f"{request.effect_id} is server-policy-only",
                code="execution_server_policy_only",
            )
        authorization = self.boundary.consume_permit(
            permit_token=permit_token,
            request=request,
        )
        trusted_context = context or ExecutionContext()
        trusted_services = dict(trusted_context.services)
        # Gateway-owned metadata overwrites any caller-supplied value.
        trusted_services["_authorization"] = authorization
        trusted_services["_gateway"] = self
        trusted_context = ExecutionContext(
            manager=trusted_context.manager,
            services=trusted_services,
        )
        result = adapter.execute(request, trusted_context)
        return result, authorization

    def execute_server_owned(
        self,
        *,
        request: ExecutionRequest,
        context: ExecutionContext | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Dispatch one canonical policy effect without a user Permit.

        This path is intentionally narrower than ``execute``: only adapters
        explicitly marked ``server_policy_only`` and effects declared as
        ``policy`` may use it. Authority is still resolved before dispatch and
        the adapter remains the sole materializer.
        """

        adapter = self.adapters.resolve(request.effect_id)
        if not bool(getattr(adapter, "server_policy_only", False)):
            raise ExecutionGatewayError(
                f"{request.effect_id} is not a server-policy adapter",
                code="execution_server_adapter_required",
            )
        try:
            authorization = self.boundary.authorize_server_policy(request)
        except AuthorizationError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc
        trusted_context = context or ExecutionContext()
        trusted_services = dict(trusted_context.services)
        trusted_services["_authorization"] = authorization
        trusted_services["_gateway"] = self
        trusted_context = ExecutionContext(
            manager=trusted_context.manager,
            services=trusted_services,
        )
        result = adapter.execute(request, trusted_context)
        return result, authorization

    def execute_nested(
        self,
        *,
        parent_request: ExecutionRequest,
        child_request: ExecutionRequest,
        context: ExecutionContext,
    ) -> tuple[Any, dict[str, Any]]:
        """Dispatch a declared compound child without minting another Permit.

        The parent ``plan.execute`` Permit is consumed exactly once by
        ``execute``. This method is only an internal gateway dispatch: it
        accepts a child whose effect, target digest, workflow binding and
        idempotency preconditions were declared in the parent request. It
        never creates or consumes authority and rejects child risk above the
        parent's canonical effect.
        """

        if parent_request.effect_id != "plan.execute":
            raise ExecutionGatewayError(
                "Nested dispatch requires a plan.execute parent",
                code="execution_nested_parent_invalid",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or str(authorization.get("state") or "") != "consumed":
            raise ExecutionGatewayError(
                "Nested dispatch requires consumed parent authorization",
                code="execution_nested_authorization_missing",
            )
        if context.services.get("_gateway") is not self:
            raise ExecutionGatewayError(
                "Nested dispatch requires the active gateway context",
                code="execution_nested_gateway_context_missing",
            )
        if str(authorization.get("effect_id") or "") != parent_request.effect_id:
            raise ExecutionGatewayError(
                "Nested authorization effect differs from the parent request",
                code="execution_nested_authorization_effect_mismatch",
            )
        if str(authorization.get("operation_fingerprint") or "") != parent_request.fingerprint:
            raise ExecutionGatewayError(
                "Nested parent authorization fingerprint mismatch",
                code="execution_nested_parent_fingerprint_mismatch",
            )
        if child_request.parent_execution_id != parent_request.request_id:
            raise ExecutionGatewayError(
                "Nested child lineage is not bound to the parent request",
                code="execution_nested_lineage_mismatch",
            )
        if child_request.delegation_id != parent_request.delegation_id:
            raise ExecutionGatewayError(
                "Nested child delegation reference differs from parent",
                code="execution_nested_delegation_mismatch",
            )
        if (
            child_request.session_id != parent_request.session_id
            or child_request.principal_id != parent_request.principal_id
            or child_request.actor_kind != parent_request.actor_kind
        ):
            raise ExecutionGatewayError(
                "Nested child identity exceeds the parent request",
                code="execution_nested_identity_mismatch",
            )
        if child_request.source_surface != "plan.runtime":
            raise ExecutionGatewayError(
                "Nested child must originate in the governed PlanEngine runtime",
                code="execution_nested_surface_invalid",
            )

        parent_target = parent_request.target if isinstance(parent_request.target, dict) else {}
        child_effects = parent_target.get("child_effects")
        if not isinstance(child_effects, list):
            raise ExecutionGatewayError(
                "Parent plan request lacks declared child effects",
                code="execution_nested_children_missing",
            )
        pipeline = child_request.target.get("_pipeline") if isinstance(child_request.target, dict) else None
        if not isinstance(pipeline, dict):
            raise ExecutionGatewayError(
                "Nested child lacks 04-FIX2 pipeline binding",
                code="execution_nested_pipeline_binding_missing",
            )
        operation_id = str(pipeline.get("pipeline_operation_id") or "")
        step_id = str(pipeline.get("step_id") or "")
        if operation_id != str(parent_target.get("pipeline_operation_id") or "") or not step_id:
            raise ExecutionGatewayError(
                "Nested child pipeline binding differs from parent",
                code="execution_nested_pipeline_binding_mismatch",
            )

        preconditions = set(child_request.preconditions)
        idempotency_key = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("step_idempotency_key:")
            ),
            "",
        )
        workflow_fingerprint = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("workflow_fingerprint:")
            ),
            "",
        )
        step_fingerprint = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("step_definition_fingerprint:")
            ),
            "",
        )
        if not idempotency_key or not workflow_fingerprint or not step_fingerprint:
            raise ExecutionGatewayError(
                "Nested child lacks idempotency/version preconditions",
                code="execution_nested_preconditions_missing",
            )

        descriptor = next(
            (
                item
                for item in child_effects
                if isinstance(item, dict)
                and str(item.get("step_id") or "") == step_id
                and str(item.get("effect_id") or "") == child_request.effect_id
            ),
            None,
        )
        if not isinstance(descriptor, dict):
            raise ExecutionGatewayError(
                "Nested child effect is not declared by the parent plan",
                code="execution_nested_child_undeclared",
            )
        if str(descriptor.get("target_digest") or "") != child_request.target_digest:
            raise ExecutionGatewayError(
                "Nested child target differs from the prepared plan",
                code="execution_nested_target_mismatch",
            )
        if str(descriptor.get("arguments_digest") or "") != child_request.arguments_digest:
            raise ExecutionGatewayError(
                "Nested child arguments differ from the prepared plan",
                code="execution_nested_arguments_mismatch",
            )
        if str(descriptor.get("scope") or "") != child_request.scope:
            raise ExecutionGatewayError(
                "Nested child scope differs from the prepared plan",
                code="execution_nested_scope_mismatch",
            )
        if str(descriptor.get("step_definition_fingerprint") or "") != step_fingerprint:
            raise ExecutionGatewayError(
                "Nested child step definition is stale",
                code="execution_nested_step_definition_stale",
            )
        if not idempotency_key.startswith(str(descriptor.get("step_idempotency_key_prefix") or "")):
            raise ExecutionGatewayError(
                "Nested child idempotency key is outside the prepared step",
                code="execution_nested_idempotency_mismatch",
            )
        if workflow_fingerprint != str(parent_target.get("workflow_fingerprint") or ""):
            raise ExecutionGatewayError(
                "Nested child workflow fingerprint is stale",
                code="execution_nested_workflow_stale",
            )

        parent_effect = REGISTRY.get(parent_request.effect_id)
        child_effect = REGISTRY.get(child_request.effect_id)
        if child_effect.risk_rank > parent_effect.risk_rank:
            raise ExecutionGatewayError(
                "Nested child effect exceeds the parent plan risk boundary",
                code="execution_nested_risk_exceeded",
            )
        if child_request.policy_version != parent_request.policy_version or child_request.policy_version != REGISTRY.digest:
            raise ExecutionGatewayError(
                "Nested child policy is stale",
                code="execution_nested_policy_stale",
            )

        adapter = self.adapters.resolve(child_request.effect_id)
        trusted_services = dict(context.services)
        trusted_services["_parent_request"] = parent_request
        nested_context = ExecutionContext(manager=context.manager, services=trusted_services)
        return adapter.execute(child_request, nested_context), authorization


__all__ = [
    "CapabilityRuntimeEffectAdapter",
    "CredentialWriteEffectAdapter",
    "DelegationGrantEffectAdapter",
    "EffectAdapter",
    "EffectAdapterRegistry",
    "ExecutionContext",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "FilesystemEffectAdapter",
    "FilesystemReadEffectAdapter",
    "ProjectWriteEffectAdapter",
    "StateDeleteEffectAdapter",
    "PlanRuntimeEffectAdapter",
    "GatewayHTTPResponse",
    "NetworkReadEffectAdapter",
    "ServerStateEffectAdapter",
    "build_default_effect_adapter_registry",
]

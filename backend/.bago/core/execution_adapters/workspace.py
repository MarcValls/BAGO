"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
import hashlib
import threading
from pathlib import Path
from typing import Any, Mapping
from execution_request import ExecutionRequest, stable_digest


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

        return resolve_workspace_binding(target).execution_descriptor()

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

"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
import hashlib
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from execution_request import ExecutionRequest

_SERVER_STATE_EFFECTS = frozenset({
    "state.directory.ensure",
    "state.write",
    "config.write",
    "memory.write",
    "agent.definition.write",
    "learning.write",
})
_SERVER_STATE_WRITE_LOCK = threading.RLock()


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

    _LEARNING_TARGETS = frozenset({
        ".bago/state/auto_learnings.jsonl",
        ".bago/knowledge/auto_patterns.md",
    })
    @classmethod
    def _ensure_directory(cls, raw_path: str, raw_root: str) -> tuple[Path, Path]:
        root = Path(str(raw_root or "")).expanduser().resolve()
        candidate = Path(str(raw_path or "")).expanduser()
        lexical = candidate if candidate.is_absolute() else root / candidate
        if root.is_symlink() or lexical.is_symlink():
            raise ExecutionGatewayError(
                "Persistent directory cannot be a symlink",
                code="server_state_directory_symlink_forbidden",
            )
        target = lexical.resolve()
        from bago_core.user_state_paths import (
            backups_root,
            cache_root,
            runtime_root,
            state_root,
            user_root,
        )

        canonical_root = user_root().resolve()
        allowed_targets = {
            canonical_root,
            runtime_root().resolve(),
            state_root().resolve(),
            cache_root().resolve(),
            backups_root().resolve(),
        }
        if root != canonical_root or target not in allowed_targets:
            raise ExecutionGatewayError(
                "Persistent directory is outside the canonical user-root set",
                code="server_state_directory_invalid",
            )
        if target != root and not root.exists():
            raise ExecutionGatewayError(
                "Persistent directory parent must already exist",
                code="server_state_directory_parent_missing",
            )
        if target == root and not root.parent.exists():
            raise ExecutionGatewayError(
                "Persistent user-root parent must already exist",
                code="server_state_directory_parent_missing",
            )
        return target, root

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
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        operation = str(request.target.get("operation") or "replace_text").strip().lower()
        if request.effect_id == "state.directory.ensure":
            if operation != "ensure_directory" or arguments:
                raise ExecutionGatewayError(
                    "Persistent directory request is invalid",
                    code="server_state_directory_request_invalid",
                )
            target, root = self._ensure_directory(str(request.target.get("path") or ""), expected_root)
            try:
                with _SERVER_STATE_WRITE_LOCK:
                    target.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ExecutionGatewayError(
                    f"Error materializing persistent directory: {exc}",
                    code="server_state_directory_create_failed",
                ) from exc
            receipt_path = (
                target.relative_to(root).as_posix()
                if target.is_relative_to(root)
                else str(target)
            )
            return {
                "ok": True,
                "executed": True,
                "effect_id": request.effect_id,
                "path": receipt_path,
                "absolute_path": str(target),
                "receipt_id": f"state-directory-ensure:{request.fingerprint}",
            }
        target, root = self._resolved_target(str(request.target.get("path") or ""), expected_root)
        content = str(arguments.get("content") or "")

        if request.effect_id == "agent.definition.write":
            relative = target.relative_to(root).as_posix()
            valid_target = relative == "agents/manifest.json" or bool(
                re.fullmatch(r"agents/[A-Za-z0-9_]{1,80}\.py", relative)
            )
            if operation != "replace_text" or not valid_target:
                raise ExecutionGatewayError(
                    "Agent definition target or operation is not approved",
                    code="agent_definition_target_invalid",
                )

        if request.effect_id == "learning.write":
            relative = target.relative_to(root).as_posix()
            if relative not in self._LEARNING_TARGETS or operation not in {"append_text", "replace_text"}:
                raise ExecutionGatewayError(
                    "Learning state target or operation is not approved",
                    code="server_learning_target_invalid",
                )

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

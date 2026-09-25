"""Strong, operation-bound owner for synthetic project canary files."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class SecurityCanaryEffectAdapter:
    effect_ids = frozenset({"security.canary.manage"})
    _TYPES = frozenset({"aws_keys", "openai_api", "github_pat", "telegram_bot", "google_api"})
    _THREAD_LOCKS_GUARD = threading.RLock()
    _THREAD_LOCKS: dict[str, threading.RLock] = {}

    @staticmethod
    def _is_link(path: Path) -> bool:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return False
        attributes = int(getattr(metadata, "st_file_attributes", 0) or 0)
        reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        return path.is_symlink() or bool(attributes & reparse)

    @classmethod
    def _lock_for(cls, key: str) -> threading.RLock:
        with cls._THREAD_LOCKS_GUARD:
            return cls._THREAD_LOCKS.setdefault(key, threading.RLock())

    @staticmethod
    def _authorization(request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
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
            raise ExecutionGatewayError("Canary materialization requires a consumed direct CLI Permit", code="canary_authorization_required")
        return authorization

    @staticmethod
    def _paths(raw_root: str) -> tuple[Path, Path, Path]:
        lexical_root = Path(os.path.abspath(str(Path(raw_root).expanduser())))
        if not lexical_root.is_absolute():
            raise ExecutionGatewayError("Canary project root must be absolute", code="canary_root_invalid")
        root = lexical_root
        if not root.is_dir():
            raise ExecutionGatewayError("Canary project root must be a directory", code="canary_root_invalid")
        current = Path(root.anchor)
        for component in root.parts[1:]:
            current = current / component
            if SecurityCanaryEffectAdapter._is_link(current):
                raise ExecutionGatewayError("Canary paths may not traverse links", code="canary_symlink_forbidden")
        bago = root / ".bago"
        state_dir = bago / "state"
        canary_dir = bago / "canary"
        for candidate in (bago, state_dir, canary_dir):
            if SecurityCanaryEffectAdapter._is_link(candidate):
                raise ExecutionGatewayError("Canary paths may not traverse links", code="canary_symlink_forbidden")
        if SecurityCanaryEffectAdapter._is_link(state_dir / "canary_tokens.json"):
            raise ExecutionGatewayError("Canary state may not be a link", code="canary_symlink_forbidden")
        return root, state_dir / "canary_tokens.json", canary_dir

    @staticmethod
    def _state_bytes(state_path: Path) -> bytes:
        try:
            return state_path.read_bytes()
        except FileNotFoundError:
            return b""
        except OSError as exc:
            raise ExecutionGatewayError(f"Cannot read canary state: {exc}", code="canary_state_read_failed") from exc

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    @classmethod
    @contextmanager
    def _resource_lock(cls, root: Path) -> Iterator[None]:
        for directory in (root / ".bago", root / ".bago" / "state"):
            if cls._is_link(directory) or (directory.exists() and not directory.is_dir()):
                raise ExecutionGatewayError("Canary state directory changed before execution", code="canary_state_path_invalid")
        lock_path = root / ".bago" / "state" / "canary_tokens.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if cls._is_link(lock_path):
            raise ExecutionGatewayError("Canary state lock cannot be a link", code="canary_symlink_forbidden")
        with cls._lock_for(str(root)):
            with lock_path.open("a+b") as handle:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    if handle.read(1) == b"":
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    try:
                        yield
                    finally:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    try:
                        yield
                    finally:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @classmethod
    def _render(cls, token_type: str, stamp: str) -> tuple[str, bytes]:
        if token_type not in cls._TYPES or not re.fullmatch(r"\d{8}_\d{6}_\d{6}", stamp):
            raise ExecutionGatewayError("Canary type or timestamp is invalid", code="canary_plan_invalid")
        values = {
            "aws_keys": (f"aws_{stamp}.env", "AWS_ACCESS_KEY_ID=AKIAFAKE123456789012\nAWS_SECRET_ACCESS_KEY=fakeAwsSecretKeyValue000000000000000000000000\n"),
            "openai_api": (f"openai_{stamp}.env", "OPENAI_API_KEY=sk-fakeOpenAIToken00000000000000000000\n"),
            "github_pat": (f"github_{stamp}.env", "GITHUB_TOKEN=ghp_FAKEGitHubTokenValue123456789012345678\n"),
            "telegram_bot": (f"telegram_{stamp}.txt", "987654321:FAKETelegramBotTokenValue1234567890abcd\n"),
            "google_api": (f"google_{stamp}.env", "GOOGLE_API_KEY=AIzaFakeGoogleApiKeyValue000000000000\n"),
        }
        filename, content = values[token_type]
        return filename, content.encode("utf-8")

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        self._authorization(request, context)
        target = request.target if isinstance(request.target, dict) else {}
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        root, state_path, canary_dir = self._paths(str(target.get("project_root") or ""))
        operation = str(target.get("operation") or "")
        expected_session = "canary:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]
        if (
            request.actor_kind != "user"
            or request.principal_id != "interactive-local-user"
            or request.session_id != expected_session
            or request.source_surface != f"cli.security.canary.{operation}"
        ):
            raise ExecutionGatewayError("Canary request identity does not match its project and operation", code="canary_identity_mismatch")
        state_bytes = self._state_bytes(state_path)
        current_digest = hashlib.sha256(state_bytes).hexdigest() if state_bytes else "missing"
        if current_digest != str(target.get("state_sha256") or ""):
            raise ExecutionGatewayError("Canary state changed after approval", code="canary_state_drift")

        with self._resource_lock(root):
            locked_root, locked_state_path, locked_canary_dir = self._paths(str(root))
            if (locked_root, locked_state_path, locked_canary_dir) != (root, state_path, canary_dir):
                raise ExecutionGatewayError("Canary paths changed before execution", code="canary_target_drift")
            # Revalidate while holding the cross-process resource lock.
            state_bytes = self._state_bytes(state_path)
            current_digest = hashlib.sha256(state_bytes).hexdigest() if state_bytes else "missing"
            if current_digest != str(target.get("state_sha256") or ""):
                raise ExecutionGatewayError("Canary state changed after approval", code="canary_state_drift")
            try:
                state = json.loads(state_bytes.decode("utf-8")) if state_bytes else {"tokens": []}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ExecutionGatewayError("Canary state is invalid", code="canary_state_invalid") from exc
            if not isinstance(state, dict) or not isinstance(state.get("tokens"), list):
                raise ExecutionGatewayError("Canary state is invalid", code="canary_state_invalid")

            if operation == "deploy":
                raw_types = target.get("types")
                stamp = str(target.get("stamp") or "")
                if not isinstance(raw_types, list) or not raw_types or any(str(item) not in self._TYPES for item in raw_types):
                    raise ExecutionGatewayError("Canary deployment plan is invalid", code="canary_plan_invalid")
                if not isinstance(target.get("created_at"), str) or not target["created_at"]:
                    raise ExecutionGatewayError("Canary deployment timestamp is invalid", code="canary_plan_invalid")
                if len(raw_types) != len(set(raw_types)):
                    raise ExecutionGatewayError("Canary deployment plan contains duplicates", code="canary_plan_invalid")
                tokens = list(state["tokens"])
                created: list[dict[str, Any]] = []
                materialized: list[Path] = []
                for token_type in raw_types:
                    filename, content = self._render(str(token_type), stamp)
                    path = canary_dir / filename
                    if path.exists() or self._is_link(path):
                        raise ExecutionGatewayError("Canary target already exists", code="canary_target_collision")
                    entry = {
                        "type": str(token_type),
                        "path": path.relative_to(root).as_posix(),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "created_at": request.target.get("created_at"),
                        "size": len(content),
                    }
                    created.append(entry)
                    tokens.append(entry)
                state_payload = json.dumps({"tokens": tokens}, indent=2, ensure_ascii=True).encode("utf-8")
                try:
                    for entry, token_type in zip(created, raw_types):
                        if self._is_link(state_path) or self._is_link(canary_dir):
                            raise ExecutionGatewayError("Canary path changed after approval", code="canary_symlink_forbidden")
                        filename, content = self._render(str(token_type), stamp)
                        path = root / entry["path"]
                        self._atomic_write(path, content)
                        materialized.append(path)
                    self._atomic_write(state_path, state_payload)
                except Exception:
                    for path in materialized:
                        try:
                            path.unlink()
                        except OSError:
                            pass
                    raise
                changed = len(created)
                removed = 0
                evidence = [entry["path"] for entry in created]
            elif operation == "purge":
                raw_files = target.get("artifacts")
                if not isinstance(raw_files, list):
                    raise ExecutionGatewayError("Canary purge plan is invalid", code="canary_plan_invalid")
                approved_paths: dict[str, str] = {}
                for item in raw_files:
                    if not isinstance(item, dict):
                        raise ExecutionGatewayError("Canary purge plan is invalid", code="canary_plan_invalid")
                    relative = str(item.get("path") or "")
                    token_type = str(item.get("type") or "")
                    prefixes = {"aws_keys": "aws", "openai_api": "openai", "github_pat": "github", "telegram_bot": "telegram", "google_api": "google"}
                    extensions = {"aws_keys": ".env", "openai_api": ".env", "github_pat": ".env", "telegram_bot": ".txt", "google_api": ".env"}
                    if token_type not in self._TYPES or not re.fullmatch(r"\.bago/canary/(aws|openai|github|telegram|google)_\d{8}_\d{6}_\d{6}\.(env|txt)", relative):
                        raise ExecutionGatewayError("Canary purge path is not canonical", code="canary_path_invalid")
                    if not Path(relative).name.startswith(prefixes[token_type] + "_"):
                        raise ExecutionGatewayError("Canary purge path does not match its type", code="canary_path_invalid")
                    if not Path(relative).name.endswith(extensions[token_type]):
                        raise ExecutionGatewayError("Canary purge extension does not match its type", code="canary_path_invalid")
                    if relative in approved_paths:
                        raise ExecutionGatewayError("Canary purge plan contains duplicates", code="canary_plan_invalid")
                    approved_paths[relative] = str(item.get("sha256") or "")
                current_entries = {str(item.get("path")): item for item in state["tokens"] if isinstance(item, dict)}
                if set(approved_paths) != set(current_entries):
                    raise ExecutionGatewayError("Canary inventory changed after approval", code="canary_state_drift")
                files: list[Path] = []
                for relative, approved_sha in approved_paths.items():
                    path = root / Path(relative)
                    if any(self._is_link(item) for item in (root / ".bago", root / ".bago" / "canary", path)):
                        raise ExecutionGatewayError("Canary purge path changed after approval", code="canary_symlink_forbidden")
                    if self._is_link(path) or (path.exists() and not path.is_file()):
                        raise ExecutionGatewayError("Canary purge target is not a regular file", code="canary_target_invalid")
                    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"
                    if actual_sha != approved_sha:
                        raise ExecutionGatewayError("Canary file changed after approval", code="canary_target_drift")
                    files.append(path)
                for path in files:
                    if path.exists():
                        path.unlink()
                self._atomic_write(state_path, json.dumps({"tokens": []}, indent=2, ensure_ascii=True).encode("utf-8"))
                try:
                    canary_dir.rmdir()
                except OSError:
                    pass
                changed = 0
                removed = len(files)
                evidence = [path.relative_to(root).as_posix() for path in files]
            else:
                raise ExecutionGatewayError("Canary operation is not allowed", code="canary_operation_invalid")

        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "operation": operation,
            "created": changed,
            "removed": removed,
            "entries": created if operation == "deploy" else [],
            "evidence": evidence,
            "receipt_id": f"canary:{operation}:sha256:{hashlib.sha256(request.fingerprint.encode()).hexdigest()}",
        }

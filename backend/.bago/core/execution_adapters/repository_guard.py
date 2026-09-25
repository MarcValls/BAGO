"""Gateway owner for BAGO's repository-local debt guard settings and hook."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


_MAX_CONTENT_BYTES = 2 * 1024 * 1024
_PATHS = {
    "config": Path(".bago/debt_guard_config.json"),
    "hook": Path(".git/hooks/pre-commit"),
}
_HOOK_MARKER = "# BAGO-DEBT-GUARD"


def _repository_root(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ExecutionGatewayError("Repository root must be absolute", code="repository_guard_root_invalid")
    try:
        root = candidate.resolve(strict=True)
    except OSError as exc:
        raise ExecutionGatewayError("Repository root is unavailable", code="repository_guard_root_invalid") from exc
    marker = root / ".git"
    try:
        info = marker.lstat()
    except OSError as exc:
        raise ExecutionGatewayError("Repository marker is unavailable", code="repository_guard_root_invalid") from exc
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    if marker.is_symlink() or bool(int(getattr(info, "st_file_attributes", 0) or 0) & reparse):
        raise ExecutionGatewayError("Repository marker cannot be linked", code="repository_guard_root_invalid")
    if not (marker.is_dir() or marker.is_file()):
        raise ExecutionGatewayError("Repository marker is invalid", code="repository_guard_root_invalid")
    return root


def _no_links(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    for part in absolute.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if current.is_symlink() or bool(int(getattr(info, "st_file_attributes", 0) or 0) & reparse):
            return False
    return True


class RepositoryGuardEffectAdapter:
    effect_ids = frozenset({"repository.guard.manage"})

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        temporary = Path(raw_temp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

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
            raise ExecutionGatewayError("Repository guard mutation requires its consumed CLI Permit", code="repository_guard_authorization_required")

        target = request.target if isinstance(request.target, dict) else {}
        operation = str(target.get("operation") or "")
        resource = str(target.get("resource") or "")
        relative = _PATHS.get(resource)
        raw_root = str(target.get("repository_root") or "")
        if (
            operation not in {"write", "delete"}
            or relative is None
            or request.source_surface != f"cli.debt_guard.{resource}.{operation}"
            or request.scope != "workspace"
        ):
            raise ExecutionGatewayError("Repository guard operation is not allowed", code="repository_guard_operation_invalid")
        root = _repository_root(raw_root)
        session_id = "repository:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]
        if request.session_id != session_id:
            raise ExecutionGatewayError("Repository guard identity changed", code="repository_guard_root_invalid")
        path = root / relative
        if not _no_links(path):
            raise ExecutionGatewayError("Repository guard path contains a link", code="repository_guard_path_linked")
        if path.exists() and not path.is_file():
            raise ExecutionGatewayError("Repository guard target must be a regular file", code="repository_guard_target_invalid")
        current = path.read_bytes() if path.is_file() else b""
        before_digest = hashlib.sha256(current).hexdigest() if current else ""
        if str(target.get("before_sha256") or "") != before_digest:
            raise ExecutionGatewayError("Repository guard target changed after approval", code="repository_guard_target_drift")

        if operation == "delete":
            if resource != "hook" or not current or _HOOK_MARKER.encode("utf-8") not in current:
                raise ExecutionGatewayError("Only a BAGO-owned hook can be deleted", code="repository_guard_hook_not_owned")
            path.unlink()
            after_digest = ""
        else:
            content = target.get("content")
            if not isinstance(content, str) or len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
                raise ExecutionGatewayError("Repository guard content is invalid", code="repository_guard_content_invalid")
            encoded = content.encode("utf-8")
            if hashlib.sha256(encoded).hexdigest() != str(target.get("after_sha256") or ""):
                raise ExecutionGatewayError("Repository guard content digest does not match", code="repository_guard_content_invalid")
            if resource == "config":
                try:
                    value = json.loads(content)
                except (TypeError, ValueError) as exc:
                    raise ExecutionGatewayError("Debt guard config must be JSON", code="repository_guard_config_invalid") from exc
                if not isinstance(value, dict) or not isinstance(value.get("rules"), dict):
                    raise ExecutionGatewayError("Debt guard config schema is invalid", code="repository_guard_config_invalid")
            elif _HOOK_MARKER not in content:
                raise ExecutionGatewayError("Hook content must retain the BAGO ownership marker", code="repository_guard_hook_invalid")
            self._atomic_write(path, content)
            if resource == "hook":
                try:
                    path.chmod(0o755)
                except OSError:
                    pass
            after_digest = hashlib.sha256(encoded).hexdigest()

        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "resource": resource,
            "operation": operation,
            "path": str(path),
            "before_sha256": before_digest,
            "after_sha256": after_digest,
            "receipt_id": f"repository-guard:{resource}:{operation}:{after_digest or 'deleted'}",
        }

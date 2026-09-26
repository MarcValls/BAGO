"""Gateway owner for creating repository role definitions and their manifest entry."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


ROLE_ROOT = Path(__file__).resolve().parents[2] / "roles"
_FAMILIES = frozenset({"gobierno", "especialistas", "supervision", "produccion"})
_LOCK = threading.RLock()


def _no_links(path: Path) -> bool:
    current = Path(path.anchor)
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    for part in path.parts[1:]:
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


class RoleDefinitionCreateEffectAdapter:
    effect_ids = frozenset({"role.definition.create"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        authorization = context.services.get("_authorization")
        if not (
            isinstance(authorization, dict)
            and authorization.get("state") == "consumed"
            and authorization.get("effect_id") == request.effect_id
            and authorization.get("operation_fingerprint") == request.fingerprint
            and authorization.get("session_id") == request.session_id
            and request.actor_kind == "user"
            and request.principal_id == "interactive-local-user"
            and request.source_surface == "cli.role_factory.create"
            and request.scope == "workspace"
        ):
            raise ExecutionGatewayError("Role creation requires its consumed CLI Permit", code="role_definition_authorization_required")

        root = ROLE_ROOT.absolute()
        target = request.target if isinstance(request.target, dict) else {}
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        family = str(target.get("family") or "")
        name = str(target.get("name") or "")
        content = arguments.get("content")
        if (
            str(target.get("role_root") or "") != str(root)
            or request.session_id != "roles:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]
            or family not in _FAMILIES
            or not re.fullmatch(r"[A-Za-z0-9_]{1,80}", name)
            or not isinstance(content, str)
            or len(content.encode("utf-8")) > 64 * 1024
        ):
            raise ExecutionGatewayError("Role definition target is invalid", code="role_definition_target_invalid")

        role_file = root / family / f"{name.upper()}.md"
        manifest_file = root / "manifest.json"
        if not root.is_dir() or not _no_links(root) or not _no_links(role_file) or not _no_links(manifest_file):
            raise ExecutionGatewayError("Role definition path is unavailable or linked", code="role_definition_path_invalid")

        with _LOCK:
            if not _no_links(root) or not _no_links(role_file) or not _no_links(manifest_file):
                raise ExecutionGatewayError("Role definition path changed", code="role_definition_path_invalid")
            if role_file.exists():
                raise ExecutionGatewayError("Role already exists", code="role_definition_exists")
            try:
                current = manifest_file.read_bytes() if manifest_file.exists() else b""
                digest = hashlib.sha256(current).hexdigest() if current else "missing"
                if target.get("manifest_sha256") != digest:
                    raise ExecutionGatewayError("Role manifest changed after approval", code="role_definition_manifest_changed")
                manifest = json.loads(current) if current else {"roles": {}, "created": datetime.now(timezone.utc).isoformat()}
                if not isinstance(manifest, dict) or not isinstance(manifest.get("roles"), dict):
                    raise ExecutionGatewayError("Role manifest is invalid", code="role_definition_manifest_invalid")
                role_id = f"role_{family}_{name}"
                if role_id in manifest["roles"]:
                    raise ExecutionGatewayError("Role already exists in manifest", code="role_definition_exists")
                manifest["roles"][role_id] = {
                    "family": family, "name": name, "file": f"{family}/{name.upper()}.md",
                    "created": datetime.now(timezone.utc).isoformat(), "status": "active",
                }
                encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                role_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = manifest_file.with_name(f".manifest.{uuid.uuid4().hex}.tmp")
                role_created = False
                manifest_committed = False
                try:
                    with temporary.open("xb") as stream:
                        stream.write(encoded)
                        stream.flush()
                        os.fsync(stream.fileno())
                    with role_file.open("x", encoding="utf-8", newline="\n") as stream:
                        role_created = True
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    latest = manifest_file.read_bytes() if manifest_file.exists() else b""
                    if latest != current:
                        raise ExecutionGatewayError("Role manifest changed before publication", code="role_definition_manifest_changed")
                    os.replace(temporary, manifest_file)
                    manifest_committed = True
                finally:
                    temporary.unlink(missing_ok=True)
                    if role_created and not manifest_committed:
                        role_file.unlink(missing_ok=True)
            except ExecutionGatewayError:
                raise
            except (OSError, ValueError) as exc:
                raise ExecutionGatewayError("Role definition could not be created", code="role_definition_write_failed") from exc

        return {
            "ok": True, "executed": True, "effect_id": request.effect_id,
            "role": role_id, "path": f"{family}/{name.upper()}.md",
            "receipt_id": f"role-definition:sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        }

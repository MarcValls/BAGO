"""Gateway owner for Electron manager settings persisted in canonical user state."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


_ROLES = frozenset({"active", "dev", "launch", "writer", "illustrator"})
_MAX_CHAIN_BYTES = 1024 * 1024


def _no_links(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if current.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400):
            return False
    return True


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _user_root() -> Path:
    raw = os.environ.get("BAGO_USER_ROOT", "").strip()
    if raw:
        root = Path(raw).expanduser().absolute()
    elif os.environ.get("LOCALAPPDATA", "").strip():
        root = Path(os.environ["LOCALAPPDATA"]).expanduser().absolute() / "BAGO"
    else:
        root = Path.home() / "AppData" / "Local" / "BAGO"
    if not _no_links(root):
        raise ExecutionGatewayError("Canonical manager user root contains a link", code="manager_settings_root_linked")
    return root.resolve(strict=False)


class ManagerSettingsWriteEffectAdapter:
    effect_ids = frozenset({"manager.settings.write"})

    @staticmethod
    def prepare_target(arguments: dict[str, Any]) -> dict[str, Any]:
        resource = str(arguments.get("resource") or "").strip()
        root = _user_root()
        if resource == "install_selection":
            role = str(arguments.get("role") or "").strip()
            raw_path = str(arguments.get("install_dir") or "").strip()
            if role not in _ROLES or not raw_path:
                raise ExecutionGatewayError("Install selection requires a known role and install path", code="manager_settings_request_invalid")
            install_dir = Path(raw_path).expanduser().absolute()
            launcher = install_dir / "bago_core" / "launcher.py"
            if not _no_links(install_dir) or not install_dir.is_dir() or not _no_links(launcher) or not launcher.is_file():
                raise ExecutionGatewayError("Selected installation is missing or linked", code="manager_settings_install_invalid")
            return {
                "resource": resource, "path": str(root / "install_selection.json"),
                "role": role, "install_dir": str(install_dir.resolve(strict=True)),
                "launcher_sha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
            }
        if resource == "chain_registry":
            chains = arguments.get("chains")
            if not isinstance(chains, list) or len(chains) > 256:
                raise ExecutionGatewayError("Chain registry must be a bounded array", code="manager_settings_chains_invalid")
            encoded = _canonical_json({"version": 1, "chains": chains})
            if len(encoded) > _MAX_CHAIN_BYTES:
                raise ExecutionGatewayError("Chain registry exceeds the size limit", code="manager_settings_chains_invalid")
            identities = [str(item.get("id") or "").strip() for item in chains if isinstance(item, dict)]
            if len(identities) != len(chains) or any(not identity for identity in identities) or len(set(identities)) != len(identities):
                raise ExecutionGatewayError("Every chain requires a unique id", code="manager_settings_chains_invalid")
            return {
                "resource": resource, "path": str(root / "manager" / "chains.json"),
                "chains_sha256": hashlib.sha256(encoded).hexdigest(), "chain_count": len(chains),
                "chain_ids": identities,
            }
        raise ExecutionGatewayError("Manager settings resource is not supported", code="manager_settings_resource_invalid")

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        if not _no_links(path.parent) or not _no_links(path):
            raise ExecutionGatewayError("Manager settings path contains a link", code="manager_settings_path_linked")
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        if manager is None or str(getattr(manager, "session_id", "") or "") != request.session_id:
            raise ExecutionGatewayError("Manager settings write requires the active SessionManager", code="manager_settings_session_mismatch")
        authorization = context.services.get("_authorization")
        if (not isinstance(authorization, dict) or authorization.get("state") != "consumed"
                or authorization.get("effect_id") != request.effect_id
                or authorization.get("operation_fingerprint") != request.fingerprint
                or authorization.get("session_id") != request.session_id):
            raise ExecutionGatewayError("Manager settings write requires its consumed Permit", code="manager_settings_authorization_required")
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        target = self.prepare_target(arguments)
        if target != request.target:
            raise ExecutionGatewayError("Manager setting changed after approval", code="manager_settings_target_changed")
        if target["resource"] == "install_selection":
            path = Path(target["path"])
            current: dict[str, Any] = {"version": 1, "updated_at": "", "roles": {}}
            if path.is_file():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict) and isinstance(loaded.get("roles"), dict):
                        current.update({"updated_at": loaded.get("updated_at", ""), "roles": loaded["roles"]})
                except (OSError, ValueError):
                    raise ExecutionGatewayError("Existing install selection is unreadable", code="manager_settings_state_invalid")
            current["roles"][target["role"]] = {
                "path": target["install_dir"], "label": target["role"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            current["version"] = 1
            payload = (json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        else:
            chains = arguments["chains"]
            payload = (json.dumps({"version": 1, "updated_at": datetime.now(timezone.utc).isoformat(), "chains": chains}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = Path(target["path"])
        self._atomic_write(path, payload)
        return {"ok": True, "executed": True, "effect_id": request.effect_id,
                "resource": target["resource"], "path": str(path),
                "receipt_id": f"manager-settings-write:{request.fingerprint}"}

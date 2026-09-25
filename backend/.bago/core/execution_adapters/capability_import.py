"""Permit-bound materialization of imported Capability Packages."""
from __future__ import annotations

import base64
import hashlib
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest


class CapabilityPackageImportEffectAdapter:
    effect_ids = frozenset({"capability.package.import"})

    @staticmethod
    def prepare_target(arguments: dict[str, Any]) -> dict[str, Any]:
        from capability_packages import _decode_archive
        from package_contract import load_archive

        encoded = str(arguments.get("content_base64") or "")
        file_name = str(arguments.get("file_name") or "")
        try:
            archive = _decode_archive(content_base64=encoded, file_name=file_name)
            loaded = load_archive(archive)
        except Exception as exc:
            raise ExecutionGatewayError(str(exc), code="capability_package_invalid") from exc
        manifest = loaded.manifest
        return {
            "package_id": str(manifest["id"]),
            "package_version": str(manifest["version"]),
            "package_kind": str(manifest["kind"]),
            "archive_sha256": hashlib.sha256(archive).hexdigest(),
            "file_name": file_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:180],
        }

    @staticmethod
    def _materialize_authorized(*, storage: Any, content_base64: str, file_name: str, confirm_trust: bool = False) -> dict[str, Any]:
        import hashlib, tempfile
        from pathlib import Path, PurePosixPath
        from package_contract import PackageContractError, canonical_json, load_archive
        CapabilityPackageError = storage.CapabilityPackageError
        _LOCK = storage._LOCK
        _decode_archive = storage._decode_archive
        _installed_capability_manifest = storage._installed_capability_manifest
        _load_registry = storage._load_registry
        _now = storage._now
        _public_record = storage._public_record
        _read_json = storage._read_json
        _save_registry = storage._save_registry
        _write_json_atomic = storage._write_json_atomic
        packages_root = storage.packages_root
        _ = confirm_trust
        # Import-time confirmation never grants activation trust.
        _ = confirm_trust
        # Retained for wire compatibility; import-time confirmation never grants activation trust.
        _ = confirm_trust
        try:
            archive = _decode_archive(content_base64=content_base64, file_name=file_name)
            loaded = load_archive(archive)
        except PackageContractError as exc:
            raise CapabilityPackageError(str(exc), code=exc.code) from exc
        manifest = loaded.manifest
        digest = hashlib.sha256(archive).hexdigest()
        root = packages_root()
        staging_root = root / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="import-", dir=staging_root) as temporary:
            temporary_path = Path(temporary) / "package"
            temporary_path.mkdir()
            for relative, content in loaded.payload.items():
                target_path = temporary_path / Path(*PurePosixPath(relative).parts)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(content)
            if not loaded.legacy_source:
                (temporary_path / "bago.package.json").write_bytes(canonical_json(manifest))
            if manifest["kind"] == "capability" and manifest["execution_mode"] == "executable":
                _installed_capability_manifest(
                    {"legacy_source": loaded.legacy_source},
                    temporary_path,
                    manifest,
                )
            capability_id = manifest["id"]
            version = manifest["version"]
            target = root / "packages" / capability_id / version
            warnings = list(loaded.warnings)
            trust_required = bool(
                manifest["kind"] == "pipeline"
                or manifest["execution_mode"] == "executable"
                or manifest["permissions"]
            )
            if trust_required:
                warnings.append("El paquete está importado pero requiere confirmación de confianza antes de activarse.")
            metadata = {
                "id": capability_id,
                "name": manifest["name"],
                "version": version,
                "description": manifest["description"],
                "kind": manifest["kind"],
                "execution_mode": manifest["execution_mode"],
                "digest": digest,
                "digest_state": loaded.digest_state,
                "signature_state": loaded.signature_state,
                "legacy_source": loaded.legacy_source,
                "warnings": warnings,
                "trust_state": "untrusted",
                "trust_required": trust_required,
                "package_manifest": manifest,
                "source_file": Path(file_name).name[:180],
                "installed_at": _now(),
            }
            _write_json_atomic(temporary_path / ".bago-package.json", metadata)
            with _LOCK:
                registry = _load_registry()
                existing = registry["packages"].get(capability_id)
                if target.exists():
                    existing_meta = _read_json(target / ".bago-package.json", {})
                    if existing_meta.get("digest") != digest:
                        raise CapabilityPackageError(
                            f"Ya existe {capability_id}@{version} con contenido diferente",
                            code="version_conflict",
                        )
                    return {"ok": True, "already_installed": True, "package": _public_record(existing or metadata)}
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary_path.rename(target)
                record = {
                    **metadata,
                    "enabled": False,
                    "trust_state": "untrusted",
                    "trusted_permissions": [],
                    "config": {},
                    "last_status": "not_started",
                    "last_receipt_id": None,
                    "last_run_at": None,
                }
                registry["packages"][capability_id] = record
                _save_registry(registry)
        return {"ok": True, "already_installed": False, "package": _public_record(record)}


    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        authorization = context.services.get("_authorization")
        if (not isinstance(authorization, dict) or authorization.get("state") != "consumed"
                or authorization.get("effect_id") != request.effect_id
                or authorization.get("operation_fingerprint") != request.fingerprint
                or authorization.get("session_id") != request.session_id):
            raise ExecutionGatewayError("Package import requires its consumed Permit", code="capability_import_authorization_required")
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        current = self.prepare_target(arguments)
        if current != request.target:
            raise ExecutionGatewayError("Package changed after authorization", code="capability_import_target_changed")
        import sys
        return self._materialize_authorized(
            storage=sys.modules["capability_packages"],
            content_base64=str(arguments["content_base64"]),
            file_name=str(arguments["file_name"]),
        )

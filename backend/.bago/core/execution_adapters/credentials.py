"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
import hashlib
import os
import threading
import uuid
from pathlib import Path
from typing import Any
from execution_request import ExecutionRequest, stable_digest


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
    _LOCK = threading.RLock()

    @staticmethod
    def _is_link(path: Path) -> bool:
        metadata = None
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return False
        is_junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(is_junction and is_junction()) or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)

    @classmethod
    def _validate_secret_path(cls, path: Path, root: Path) -> None:
        if path.parent != root or path.suffix != ".bin":
            raise ExecutionGatewayError("Credential target is outside the canonical SecretStore", code="credential_write_path_invalid")
        for component in (path, *path.parents):
            if component == root.parent.parent:
                break
            if cls._is_link(component):
                raise ExecutionGatewayError("Credential target cannot traverse a link or reparse point", code="credential_write_link_forbidden")

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
        from credential_manager import CREDENTIAL_SCHEMA
        if key != "api_key" and key not in CREDENTIAL_SCHEMA.get(provider, {}):
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
        secret_key = f"providers/{provider}/{key}"
        path = secret_store.path_for_key(secret_key)
        from bago_core.user_state_paths import secrets_root

        root = secrets_root().expanduser().resolve()
        if path.parent.expanduser().resolve() != root:
            raise ExecutionGatewayError("Credential target is not under the canonical SecretStore root", code="credential_write_path_invalid")
        self._validate_secret_path(path, root)

        if operation == "set":
            arguments = request.arguments if isinstance(request.arguments, dict) else {}
            value = str(arguments.get("value") or "")
            if not value:
                raise ExecutionGatewayError(
                    "Credential write value is required for set",
                    code="credential_write_value_required",
                )
            try:
                ciphertext = secret_store.protect_secret(value)
                with self._LOCK:
                    root.mkdir(parents=True, exist_ok=True)
                    self._validate_secret_path(path, root)
                    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
                    try:
                        with temporary.open("xb") as handle:
                            handle.write(ciphertext)
                            handle.flush()
                            os.fsync(handle.fileno())
                        self._validate_secret_path(path, root)
                        os.replace(str(temporary), str(path))
                        try:
                            os.chmod(str(path), 0o600)
                        except (OSError, NotImplementedError):
                            pass
                    finally:
                        temporary.unlink(missing_ok=True)
            except Exception as exc:
                raise ExecutionGatewayError(
                    f"Error guardando credencial: {exc}",
                    code="credential_write_failed",
                ) from exc
            changed = True
            deleted = False
        else:
            try:
                with self._LOCK:
                    self._validate_secret_path(path, root)
                    deleted = path.exists()
                    if deleted:
                        path.unlink()
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

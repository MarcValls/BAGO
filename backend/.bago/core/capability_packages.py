"""Capability package lifecycle backed by the generic BAGO Package v1 contract.

Legacy ``capability.json`` archives remain supported. The renderer never loads
package JavaScript. All code execution remains backend-owned, requires an
enabled package plus explicit confirmation, runs without a shell, and produces
a persisted receipt.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from bago_core.user_state_paths import state_root
from package_contract import (
    MAX_ARCHIVE_BYTES,
    PackageContractError,
    canonical_archive,
    canonical_json,
    inspection_error,
    load_archive,
    validate_pipeline_definition,
)


CONTRACT_VERSION = "bago.capability/v1"
SCHEMA_VERSION = "1.0"
MAX_OUTPUT_CHARS = 64 * 1024
MAX_RUNTIME_SECONDS = 900
ALLOWED_PERMISSIONS = {
    "filesystem.read",
    "filesystem.write",
    "network",
    "process",
}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9._-]+)?$")
_TEMPLATE_RE = re.compile(r"\$\{((?:inputs|variables|steps)(?:\.[A-Za-z0-9_-]+)+)\}")
_LOCK = threading.RLock()
_PIPELINE_EXECUTION = threading.local()


class CapabilityPackageError(ValueError):
    """A user-correctable package or lifecycle error."""

    def __init__(self, message: str, *, code: str = "invalid_package") -> None:
        super().__init__(message)
        self.code = code


def packages_root() -> Path:
    return state_root() / "capabilities"


def registry_path() -> Path:
    return packages_root() / "registry.json"


def receipts_root() -> Path:
    return packages_root() / "receipts"


def examples_root() -> Path:
    return Path(__file__).resolve().parents[3] / "examples" / "packages"


def _example_archive(package_dir: Path) -> bytes:
    manifest_path = package_dir / "bago.package.json"
    if not manifest_path.is_file():
        raise CapabilityPackageError("El ejemplo no contiene bago.package.json", code="not_found")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityPackageError(f"Manifest de ejemplo inválido: {exc}") from exc
    payload = {
        item.relative_to(package_dir).as_posix(): item.read_bytes()
        for item in sorted(package_dir.rglob("*"))
        if item.is_file() and item != manifest_path
    }
    return canonical_archive(manifest, payload)


def list_example_packages() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    root = examples_root()
    if not root.is_dir():
        return examples
    for package_dir in sorted(item for item in root.iterdir() if item.is_dir()):
        manifest_path = package_dir / "bago.package.json"
        if not manifest_path.is_file():
            continue
        loaded = load_archive(_example_archive(package_dir))
        inspection = loaded.inspection()
        examples.append({
            **inspection["identity"],
            "kind": inspection["kind"],
            "execution_mode": inspection["execution_mode"],
            "permissions": inspection["permissions"],
            "dependencies": inspection["dependencies"],
            "schedule_defaults": loaded.manifest.get("schedule_defaults", []),
            "source": package_dir.name,
        })
    return examples


def install_example_package(package_id: str) -> dict[str, Any]:
    clean_id = str(package_id or "").strip()
    for package_dir in sorted(item for item in examples_root().iterdir() if item.is_dir()):
        archive = _example_archive(package_dir)
        loaded = load_archive(archive)
        if loaded.manifest["id"] != clean_id:
            continue
        return import_package(
            content_base64=base64.b64encode(archive).decode("ascii"),
            file_name=f"{package_dir.name}.bago.zip",
            confirm_trust=False,
        )
    raise CapabilityPackageError(f"Ejemplo no encontrado: {clean_id}", code="not_found")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _load_registry() -> dict[str, Any]:
    data = _read_json(registry_path(), {})
    if not isinstance(data, dict) or not isinstance(data.get("packages"), dict):
        return {"schema_version": 1, "packages": {}}
    return data


def _save_registry(data: dict[str, Any]) -> None:
    data["schema_version"] = 1
    data["updated_at"] = _now()
    _write_json_atomic(registry_path(), data)


def _safe_relative_path(raw: str, *, field: str) -> PurePosixPath:
    normalized = str(raw or "").replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise CapabilityPackageError(f"{field} debe ser una ruta relativa segura", code="unsafe_path")
    return path


def _validate_object_schema(raw: Any, *, field: str) -> dict[str, Any]:
    if raw in (None, {}):
        return {"type": "object", "properties": {}, "required": []}
    if not isinstance(raw, dict) or raw.get("type", "object") != "object":
        raise CapabilityPackageError(f"{field} debe ser un schema JSON de objeto")
    properties = raw.get("properties", {})
    required = raw.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise CapabilityPackageError(f"{field} contiene properties/required inválidos")
    allowed_types = {"string", "number", "integer", "boolean"}
    clean_properties: dict[str, Any] = {}
    for name, definition in properties.items():
        if not isinstance(name, str) or not name or not isinstance(definition, dict):
            raise CapabilityPackageError(f"{field} contiene una propiedad inválida")
        value_type = str(definition.get("type") or "string")
        if value_type not in allowed_types:
            raise CapabilityPackageError(f"{field}.{name}: tipo no soportado {value_type}")
        clean = {
            "type": value_type,
            "title": str(definition.get("title") or name),
            "description": str(definition.get("description") or ""),
        }
        if "default" in definition:
            clean["default"] = definition["default"]
        if isinstance(definition.get("enum"), list):
            clean["enum"] = definition["enum"]
        clean_properties[name] = clean
    clean_required = [str(name) for name in required if str(name) in clean_properties]
    return {
        "type": "object",
        "properties": clean_properties,
        "required": clean_required,
        "additionalProperties": bool(raw.get("additionalProperties", False)),
    }


def validate_manifest(raw: Any, *, package_dir: Path | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CapabilityPackageError("capability.json debe contener un objeto JSON")
    if raw.get("contract_version") != CONTRACT_VERSION or str(raw.get("schema_version")) != SCHEMA_VERSION:
        raise CapabilityPackageError(f"Contrato requerido: {CONTRACT_VERSION} schema {SCHEMA_VERSION}", code="unsupported_contract")
    capability_id = str(raw.get("id") or "").strip().lower()
    if not _ID_RE.fullmatch(capability_id):
        raise CapabilityPackageError("id inválido; usa 3-64 caracteres [a-z0-9._-]")
    version = str(raw.get("version") or "").strip()
    if not _VERSION_RE.fullmatch(version):
        raise CapabilityPackageError("version debe usar formato semver, por ejemplo 1.0.0")
    name = str(raw.get("name") or "").strip()
    description = str(raw.get("description") or "").strip()
    if not name or not description:
        raise CapabilityPackageError("name y description son obligatorios")

    runtime = raw.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("kind") != "python":
        raise CapabilityPackageError("runtime.kind debe ser python")
    entrypoint = _safe_relative_path(str(runtime.get("entrypoint") or ""), field="runtime.entrypoint")
    if entrypoint.suffix.lower() != ".py":
        raise CapabilityPackageError("runtime.entrypoint debe ser un archivo .py")
    timeout_s = max(1, min(int(runtime.get("timeout_s") or 30), MAX_RUNTIME_SECONDS))
    if package_dir is not None and not (package_dir / Path(*entrypoint.parts)).is_file():
        raise CapabilityPackageError(f"No existe el entrypoint declarado: {entrypoint}")

    permissions_raw = raw.get("permissions", [])
    if not isinstance(permissions_raw, list):
        raise CapabilityPackageError("permissions debe ser una lista")
    permissions = sorted({str(item) for item in permissions_raw if str(item)})
    unknown = sorted(set(permissions) - ALLOWED_PERMISSIONS)
    if unknown:
        raise CapabilityPackageError(f"Permisos no soportados: {', '.join(unknown)}")

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "id": capability_id,
        "name": name[:120],
        "version": version,
        "description": description[:500],
        "author": str(raw.get("author") or "local")[:120],
        "permissions": permissions,
        "runtime": {"kind": "python", "entrypoint": str(entrypoint), "timeout_s": timeout_s},
        "configuration_schema": _validate_object_schema(raw.get("configuration_schema"), field="configuration_schema"),
        "input_schema": _validate_object_schema(raw.get("input_schema"), field="input_schema"),
        "output_schema": raw.get("output_schema") if isinstance(raw.get("output_schema"), dict) else {},
        "tags": [str(tag)[:40] for tag in raw.get("tags", []) if str(tag).strip()][:12] if isinstance(raw.get("tags"), list) else [],
    }


def _package_dir(record: dict[str, Any]) -> Path:
    return packages_root() / "packages" / str(record["id"]) / str(record["version"])


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    package_dir = _package_dir(record)
    metadata = _read_json(package_dir / ".bago-package.json", {})
    package_manifest = metadata.get("package_manifest", {}) if isinstance(metadata, dict) else {}
    kind = str(package_manifest.get("kind") or record.get("kind") or "capability")
    execution_mode = str(package_manifest.get("execution_mode") or record.get("execution_mode") or "executable")
    manifest: dict[str, Any] = {}
    try:
        if kind == "capability" and execution_mode == "executable":
            manifest = _installed_capability_manifest(record, package_dir, package_manifest)
        elif kind == "capability":
            manifest = _read_definition(package_dir, package_manifest)
        else:
            manifest = _read_definition(package_dir, package_manifest)
        available = True
        error = ""
    except CapabilityPackageError as exc:
        manifest = manifest if isinstance(manifest, dict) else {}
        available = False
        error = str(exc)
    return {
        "id": record.get("id", ""),
        "name": package_manifest.get("name") or manifest.get("name") or record.get("name", record.get("id", "")),
        "version": record.get("version", ""),
        "description": package_manifest.get("description") or manifest.get("description") or record.get("description", ""),
        "author": package_manifest.get("author") or manifest.get("author", "local"),
        "enabled": bool(record.get("enabled")) and available,
        "available": available,
        "error": error,
        "kind": kind,
        "execution_mode": execution_mode,
        "contract_version": str(package_manifest.get("contract_version") or CONTRACT_VERSION),
        "legacy_source": bool(metadata.get("legacy_source") or record.get("legacy_source")),
        "permissions": package_manifest.get("permissions", manifest.get("permissions", [])),
        "runtime": manifest.get("runtime", {}),
        "configuration_schema": manifest.get("configuration_schema", {"type": "object", "properties": {}, "required": []}),
        "input_schema": manifest.get("input_schema", {"type": "object", "properties": {}, "required": []}),
        "config": record.get("config", {}) if isinstance(record.get("config"), dict) else {},
        "digest": record.get("digest", ""),
        "digest_state": str(metadata.get("digest_state") or record.get("digest_state") or "unknown"),
        "signature_state": str(metadata.get("signature_state") or record.get("signature_state") or "unsigned"),
        "trust_state": str(record.get("trust_state") or metadata.get("trust_state") or "untrusted"),
        "trusted_permissions": list(record.get("trusted_permissions", [])),
        "warnings": list(metadata.get("warnings", record.get("warnings", []))),
        "compatibility": package_manifest.get("compatibility", {}),
        "dependencies": package_manifest.get("dependencies", []),
        "files": package_manifest.get("files", []),
        "schedule_defaults": package_manifest.get("schedule_defaults", []),
        "installed_at": record.get("installed_at", ""),
        "last_run_at": record.get("last_run_at"),
        "last_status": record.get("last_status", "not_started"),
        "last_receipt_id": record.get("last_receipt_id"),
        "tags": manifest.get("tags", []),
    }


def _read_definition(package_dir: Path, package_manifest: dict[str, Any]) -> dict[str, Any]:
    reference = str(package_manifest.get("definition") or "capability.json")
    relative = _safe_relative_path(reference, field="definition")
    definition = _read_json(package_dir / Path(*relative.parts), None)
    if not isinstance(definition, dict):
        raise CapabilityPackageError(f"No se puede leer la definición instalada: {reference}")
    return definition


def _installed_capability_manifest(
    record: dict[str, Any],
    package_dir: Path,
    package_manifest: dict[str, Any],
) -> dict[str, Any]:
    if bool(record.get("legacy_source")) or package_manifest.get("definition") == "capability.json":
        return validate_manifest(_read_json(package_dir / "capability.json", {}), package_dir=package_dir)
    definition = _read_definition(package_dir, package_manifest)
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    raw = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "id": package_manifest.get("id"),
        "name": package_manifest.get("name"),
        "version": package_manifest.get("version"),
        "description": package_manifest.get("description"),
        "author": package_manifest.get("author"),
        "permissions": package_manifest.get("permissions", []),
        "runtime": {
            "kind": runtime.get("kind", "python"),
            "entrypoint": package_manifest.get("entrypoint"),
            "timeout_s": runtime.get("timeout_s", 30),
        },
        "configuration_schema": definition.get("configuration_schema"),
        "input_schema": definition.get("input_schema"),
        "output_schema": definition.get("output_schema"),
        "tags": definition.get("tags", []),
    }
    return validate_manifest(raw, package_dir=package_dir)


def _decode_archive(*, content_base64: str, file_name: str) -> bytes:
    if not str(file_name or "").lower().endswith(".zip"):
        raise CapabilityPackageError("Solo se admiten paquetes .zip")
    try:
        archive = base64.b64decode(str(content_base64 or ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CapabilityPackageError("content_base64 no es válido") from exc
    if not archive or len(archive) > MAX_ARCHIVE_BYTES:
        raise CapabilityPackageError("El ZIP debe pesar entre 1 byte y 600 KB", code="package_too_large")
    return archive


def inspect_package(*, content_base64: str, file_name: str) -> dict[str, Any]:
    """Validate and describe an archive without touching persistent state."""
    try:
        archive = _decode_archive(content_base64=content_base64, file_name=file_name)
        return load_archive(archive).inspection()
    except PackageContractError as exc:
        return inspection_error(exc)
    except CapabilityPackageError as exc:
        return inspection_error(PackageContractError(str(exc), code=exc.code))


def import_package(*, content_base64: str, file_name: str, confirm_trust: bool = False) -> dict[str, Any]:
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


def export_package(package_id: str) -> dict[str, Any]:
    """Return a deterministic canonical ZIP for an installed package."""
    with _LOCK:
        record = _load_registry()["packages"].get(str(package_id))
    if not isinstance(record, dict):
        raise CapabilityPackageError("Paquete externo no encontrado", code="not_found")
    package_dir = _package_dir(record)
    metadata = _read_json(package_dir / ".bago-package.json", {})
    manifest = metadata.get("package_manifest", {}) if isinstance(metadata, dict) else {}
    if not isinstance(manifest, dict) or not manifest:
        raise CapabilityPackageError("Faltan metadatos del contrato instalado")
    if bool(metadata.get("legacy_source")):
        legacy = _read_json(package_dir / "capability.json", None)
        if not isinstance(legacy, dict):
            raise CapabilityPackageError("No se puede exportar capability.json")
        entrypoint = str(manifest["entrypoint"])
        payload = {"definitions/capability.json": canonical_json(legacy)}
        for item in manifest["files"]:
            path = str(item["path"])
            if path == "capability.json":
                continue
            content = (package_dir / Path(*PurePosixPath(path).parts)).read_bytes()
            target = f"runtime/{path}" if path == entrypoint else f"assets/{path}"
            payload[target] = content
        export_manifest = {
            **{key: value for key, value in manifest.items() if key not in {"files", "definition", "entrypoint"}},
            "definition": "definitions/capability.json",
            "entrypoint": f"runtime/{entrypoint}",
        }
    else:
        payload = {}
        for item in manifest["files"]:
            path = str(item["path"])
            payload[path] = (package_dir / Path(*PurePosixPath(path).parts)).read_bytes()
        export_manifest = manifest
    archive = canonical_archive(export_manifest, payload)
    return {
        "ok": True,
        "file_name": f"{manifest['id']}-{manifest['version']}.zip",
        "content_base64": base64.b64encode(archive).decode("ascii"),
        "size": len(archive),
        "digest": hashlib.sha256(archive).hexdigest(),
    }


def list_packages() -> list[dict[str, Any]]:
    with _LOCK:
        records = list(_load_registry()["packages"].values())
    return sorted((_public_record(record) for record in records), key=lambda item: (item["name"].lower(), item["id"]))


def get_package(capability_id: str) -> dict[str, Any]:
    with _LOCK:
        record = _load_registry()["packages"].get(str(capability_id))
    if not isinstance(record, dict):
        raise CapabilityPackageError("Capacidad externa no encontrada", code="not_found")
    return _public_record(record)


def set_enabled(capability_id: str, enabled: bool, *, confirm_trust: bool = False) -> dict[str, Any]:
    with _LOCK:
        registry = _load_registry()
        record = registry["packages"].get(capability_id)
        if not isinstance(record, dict):
            raise CapabilityPackageError("Capacidad externa no encontrada", code="not_found")
        public = _public_record(record)
        if enabled and not public["available"]:
            raise CapabilityPackageError(public["error"] or "El paquete no está disponible")
        if enabled and public["kind"] == "capability" and public["execution_mode"] != "executable":
            raise CapabilityPackageError("Solo se pueden activar capacidades ejecutables", code="not_executable")
        trust_required = bool(
            public["kind"] == "pipeline"
            or public["execution_mode"] == "executable"
            or public["permissions"]
        )
        if enabled and not bool(record.get("enabled")) and trust_required and not confirm_trust:
            raise CapabilityPackageError(
                "La activación requiere confirmación explícita de confianza",
                code="trust_confirmation_required",
            )
        if enabled and trust_required:
            record["trust_state"] = "trusted"
            record["trusted_at"] = _now()
            record["trusted_permissions"] = list(public["permissions"])
        record["enabled"] = bool(enabled)
        registry["packages"][capability_id] = record
        _save_registry(registry)
    return _public_record(record)


def _validate_values(schema: dict[str, Any], values: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise CapabilityPackageError(f"{field} debe ser un objeto")
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [name for name in required if name not in values or values[name] in (None, "")]
    if missing:
        raise CapabilityPackageError(f"{field}: faltan {', '.join(missing)}")
    if not schema.get("additionalProperties", False):
        unknown = sorted(set(values) - set(properties))
        if unknown:
            raise CapabilityPackageError(f"{field}: campos desconocidos {', '.join(unknown)}")
    clean: dict[str, Any] = {}
    for name, value in values.items():
        definition = properties.get(name)
        if not isinstance(definition, dict):
            clean[name] = value
            continue
        expected = definition.get("type", "string")
        valid = (
            (expected == "string" and isinstance(value, str))
            or (expected == "boolean" and isinstance(value, bool))
            or (expected == "integer" and isinstance(value, int) and not isinstance(value, bool))
            or (expected == "number" and isinstance(value, (int, float)) and not isinstance(value, bool))
        )
        if not valid:
            raise CapabilityPackageError(f"{field}.{name}: se esperaba {expected}")
        choices = definition.get("enum")
        if isinstance(choices, list) and value not in choices:
            raise CapabilityPackageError(f"{field}.{name}: valor fuera de enum")
        clean[name] = value
    return clean


def configure_package(capability_id: str, config: Any) -> dict[str, Any]:
    with _LOCK:
        registry = _load_registry()
        record = registry["packages"].get(capability_id)
        if not isinstance(record, dict):
            raise CapabilityPackageError("Capacidad externa no encontrada", code="not_found")
        public = _public_record(record)
        if public["kind"] != "capability":
            raise CapabilityPackageError("Los pipelines no admiten configuración de capacidad", code="wrong_kind")
        clean = _validate_values(public["configuration_schema"], config, field="config")
        record["config"] = clean
        registry["packages"][capability_id] = record
        _save_registry(registry)
    return _public_record(record)


def _execution_environment(capability_id: str, version: str) -> dict[str, str]:
    allowed = (
        "PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "USERPROFILE",
        "LOCALAPPDATA", "APPDATA", "PROGRAMDATA", "HOMEDRIVE", "HOMEPATH",
        "USERNAME", "COMSPEC", "PATHEXT", "JAVA_HOME",
        "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
    )
    environment = {key: value for key in allowed if (value := os.environ.get(key))}
    environment.update({
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "BAGO_CAPABILITY_ID": capability_id,
        "BAGO_CAPABILITY_VERSION": version,
    })
    return environment


def _parse_output(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _store_receipt(receipt: dict[str, Any]) -> None:
    _write_json_atomic(receipts_root() / f"{receipt['receipt_id']}.json", receipt)
    with _LOCK:
        registry = _load_registry()
        package_id = str(receipt.get("package_id") or receipt.get("capability_id") or "")
        record = registry["packages"].get(package_id)
        if isinstance(record, dict):
            record["last_receipt_id"] = receipt["receipt_id"]
            record["last_run_at"] = receipt["finished_at"]
            record["last_status"] = receipt["status"]
            registry["packages"][package_id] = record
            _save_registry(registry)


def execute_package(
    capability_id: str,
    *,
    inputs: Any,
    confirmed: bool,
    approved_permissions: Any,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    package = get_package(capability_id)
    if package["kind"] != "capability" or package["execution_mode"] != "executable":
        raise CapabilityPackageError("El paquete no es una capacidad ejecutable", code="not_executable")
    if not package["enabled"]:
        raise CapabilityPackageError("Activa la capacidad antes de ejecutarla", code="not_enabled")
    if package["trust_state"] != "trusted":
        raise CapabilityPackageError("La capacidad no tiene confianza confirmada", code="trust_required")
    if not confirmed:
        raise CapabilityPackageError("La ejecución requiere confirmación explícita", code="confirmation_required")
    approvals = {str(item) for item in approved_permissions} if isinstance(approved_permissions, list) else set()
    missing_permissions = sorted(set(package["permissions"]) - approvals)
    if missing_permissions:
        raise CapabilityPackageError(
            f"Falta aprobar: {', '.join(missing_permissions)}",
            code="permission_approval_required",
        )
    clean_inputs = _validate_values(package["input_schema"], inputs, field="input")
    with _LOCK:
        record = _load_registry()["packages"].get(capability_id)
    if not isinstance(record, dict):
        raise CapabilityPackageError("Capacidad externa no encontrada", code="not_found")
    package_dir = _package_dir(record)
    metadata = _read_json(package_dir / ".bago-package.json", {})
    package_manifest = metadata.get("package_manifest", {}) if isinstance(metadata, dict) else {}
    manifest = _installed_capability_manifest(record, package_dir, package_manifest)
    effective_timeout = int(manifest["runtime"]["timeout_s"])
    if timeout_s is not None:
        if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or not 1 <= timeout_s <= MAX_RUNTIME_SECONDS:
            raise CapabilityPackageError("timeout_s debe estar entre 1 y 900")
        effective_timeout = min(effective_timeout, timeout_s)
    entrypoint = package_dir / Path(*PurePosixPath(manifest["runtime"]["entrypoint"]).parts)
    payload = {
        "input": clean_inputs,
        "config": package["config"],
        "context": {"capability_id": capability_id, "version": package["version"]},
    }
    encoded_input = json.dumps(payload, ensure_ascii=False)
    execution_id = f"cap-{uuid.uuid4().hex[:16]}"
    receipt_id = f"receipt-{uuid.uuid4().hex[:16]}"
    started_at = _now()
    started = time.perf_counter()
    status = "failed"
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    error = ""
    try:
        completed = subprocess.run(
            [sys.executable, str(entrypoint)],
            input=encoded_input,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            cwd=str(package_dir),
            env=_execution_environment(capability_id, package["version"]),
            timeout=effective_timeout,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout[-MAX_OUTPUT_CHARS:]
        stderr = completed.stderr[-MAX_OUTPUT_CHARS:]
        status = "succeeded" if completed.returncode == 0 else "failed"
        if completed.returncode != 0:
            error = stderr.strip() or f"El runner terminó con código {completed.returncode}"
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        error = f"Timeout de {effective_timeout}s"
        stdout = str(exc.stdout or "")[-MAX_OUTPUT_CHARS:]
        stderr = str(exc.stderr or "")[-MAX_OUTPUT_CHARS:]
    except OSError as exc:
        error = str(exc)

    receipt = {
        "receipt_id": receipt_id,
        "execution_id": execution_id,
        "capability_id": capability_id,
        "capability_version": package["version"],
        "package_digest": package["digest"],
        "input_digest": hashlib.sha256(encoded_input.encode("utf-8")).hexdigest(),
        "permissions": package["permissions"],
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        "exit_code": exit_code,
        "result": _parse_output(stdout),
        "stderr": stderr.strip(),
        "error": error,
        "executor": {"kind": "python-subprocess", "shell": False},
    }
    _store_receipt(receipt)
    return {"ok": status == "succeeded", "receipt": receipt}


def _pipeline_definition(
    record: dict[str, Any],
    package_dir: Path,
    package_manifest: dict[str, Any],
) -> dict[str, Any]:
    definition = _read_definition(package_dir, package_manifest)
    try:
        return validate_pipeline_definition(definition, package_id=str(record["id"]))
    except PackageContractError as exc:
        raise CapabilityPackageError(str(exc), code=exc.code) from exc


def _version_satisfies(version: str, requirement: str) -> bool:
    def numeric(value: str) -> tuple[int, int, int] | None:
        match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", value)
        if not match:
            return None
        return tuple(int(item or 0) for item in match.groups())

    requirement = requirement.strip()
    if requirement in {"", "*"}:
        return True
    if requirement.startswith("="):
        return version == requirement.lstrip("=")
    if requirement.startswith("^"):
        base = numeric(requirement[1:])
        actual = numeric(version)
        return bool(base and actual and base[0] == actual[0] and actual >= base)
    if requirement.startswith(">="):
        base = numeric(requirement[2:])
        actual = numeric(version)
        return bool(base and actual and actual >= base)
    return version == requirement


def _enforce_pipeline_dependencies(manifest: dict[str, Any], definition: dict[str, Any]) -> None:
    dependencies = {
        str(item["id"]): str(item["version"])
        for item in manifest.get("dependencies", [])
        if isinstance(item, dict)
    }
    references = {
        str(step["uses"])
        for step in definition["steps"]
        if step["type"] in {"capability", "pipeline"}
    }
    undeclared = sorted(references - set(dependencies))
    if undeclared:
        raise CapabilityPackageError(
            f"Referencias de paquete no declaradas como dependencies: {', '.join(undeclared)}",
            code="undeclared_dependency",
        )
    for dependency_id, requirement in dependencies.items():
        dependency = get_package(dependency_id)
        if not _version_satisfies(str(dependency["version"]), requirement):
            raise CapabilityPackageError(
                f"{dependency_id}@{dependency['version']} no satisface {requirement}",
                code="dependency_version_mismatch",
            )
        if not dependency["enabled"]:
            raise CapabilityPackageError(f"La dependencia {dependency_id} no está activa", code="dependency_not_enabled")
        if dependency["trust_state"] != "trusted":
            raise CapabilityPackageError(
                f"La dependencia {dependency_id} no tiene confianza confirmada",
                code="dependency_untrusted",
            )


def _lookup_pipeline_value(context: dict[str, Any], reference: str) -> Any:
    current: Any = context
    for part in reference.split("."):
        if not isinstance(current, dict) or part not in current:
            raise CapabilityPackageError(f"Referencia pipeline no disponible: {reference}", code="unresolved_reference")
        current = current[part]
    return current


def _resolve_pipeline_values(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_pipeline_values(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_pipeline_values(item, context) for item in value]
    if not isinstance(value, str):
        return value
    exact = _TEMPLATE_RE.fullmatch(value)
    if exact:
        return _lookup_pipeline_value(context, exact.group(1))

    def replace(match: re.Match[str]) -> str:
        resolved = _lookup_pipeline_value(context, match.group(1))
        if isinstance(resolved, str):
            return resolved
        return json.dumps(resolved, ensure_ascii=False, separators=(",", ":"))

    return _TEMPLATE_RE.sub(replace, value)


def _pipeline_condition(condition: Any, context: dict[str, Any]) -> bool:
    if isinstance(condition, bool):
        return condition
    expression = str(condition)
    negate = expression.startswith("!") or expression.startswith("not ")
    reference = expression[1:] if expression.startswith("!") else expression[4:] if expression.startswith("not ") else expression
    value = _lookup_pipeline_value(context, reference)
    if reference.endswith(".status"):
        result = value in {"succeeded", "skipped"}
    else:
        result = bool(value)
    return not result if negate else result


def _pipeline_retry_policy(raw: Any) -> tuple[int, float]:
    if isinstance(raw, dict):
        return int(raw.get("max_attempts", 1)), float(raw.get("delay_s", 0))
    return int(raw) + 1, 0.0


def _pipeline_step_order(definition: dict[str, Any]) -> list[dict[str, Any]]:
    pending = list(definition["steps"])
    completed: set[str] = set()
    ordered: list[dict[str, Any]] = []
    while pending:
        ready = [step for step in pending if set(step["depends_on"]) <= completed]
        if not ready:
            raise CapabilityPackageError("El pipeline contiene un ciclo", code="pipeline_cycle")
        for step in ready:
            pending.remove(step)
            completed.add(step["id"])
            ordered.append(step)
    return ordered


def _invoke_pipeline_step(
    step: dict[str, Any],
    parameters: dict[str, Any],
    *,
    confirmed: bool,
    approved_permissions: Any,
    manager: Any,
) -> dict[str, Any]:
    step_type = step["type"]
    if step_type == "noop":
        return {"ok": True, "result": parameters, "receipt_id": None}
    if step_type == "approval":
        if not confirmed:
            raise CapabilityPackageError(
                f"El paso {step['id']} requiere aprobación explícita",
                code="confirmation_required",
            )
        return {"ok": True, "result": {"approved": True, **parameters}, "receipt_id": None}
    referenced = get_package(str(step["uses"]))
    if step_type == "capability":
        if referenced["kind"] != "capability":
            raise CapabilityPackageError(f"{step['uses']} no es una capacidad", code="wrong_kind")
        child = execute_package(
            str(step["uses"]),
            inputs=parameters,
            confirmed=confirmed,
            approved_permissions=approved_permissions,
            timeout_s=step.get("timeout_s"),
        )
    else:
        if referenced["kind"] != "pipeline":
            raise CapabilityPackageError(f"{step['uses']} no es un pipeline", code="wrong_kind")
        child = execute_pipeline_package(
            str(step["uses"]),
            inputs=parameters,
            confirmed=confirmed,
            approved_permissions=approved_permissions,
            manager=manager,
        )
    receipt = child.get("receipt", {}) if isinstance(child, dict) else {}
    return {
        "ok": bool(child.get("ok")) if isinstance(child, dict) else False,
        "result": receipt.get("result"),
        "receipt_id": receipt.get("receipt_id"),
    }


def _pipeline_receipt(
    *,
    package: dict[str, Any],
    execution_id: str,
    receipt_id: str,
    started_at: str,
    started: float,
    encoded_input: str,
    status: str,
    result: Any,
    error: str,
    executor: dict[str, Any],
    permissions: list[str],
    steps: list[dict[str, Any]] | None = None,
    exit_code: int | None = None,
    stderr: str = "",
) -> dict[str, Any]:
    receipt = {
        "receipt_id": receipt_id,
        "execution_id": execution_id,
        "package_id": package["id"],
        "pipeline_id": package["id"],
        "pipeline_version": package["version"],
        "package_digest": package["digest"],
        "input_digest": hashlib.sha256(encoded_input.encode("utf-8")).hexdigest(),
        "permissions": permissions,
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        "result": result,
        "steps": steps or [],
        "error": error,
        "stderr": stderr,
        "exit_code": exit_code,
        "executor": executor,
    }
    _store_receipt(receipt)
    return receipt


def execute_pipeline_package(
    package_id: str,
    inputs: Any,
    confirmed: bool,
    approved_permissions: Any,
    manager: Any,
) -> dict[str, Any]:
    """Execute an enabled imported pipeline and persist its receipt."""
    package = get_package(package_id)
    if package["kind"] != "pipeline":
        raise CapabilityPackageError("El paquete no es un pipeline", code="wrong_kind")
    if not package["enabled"]:
        raise CapabilityPackageError("Activa el pipeline antes de ejecutarlo", code="not_enabled")
    if package["trust_state"] != "trusted":
        raise CapabilityPackageError("El pipeline no tiene confianza confirmada", code="trust_required")
    if package["execution_mode"] == "executable" and not confirmed:
        raise CapabilityPackageError("El pipeline ejecutable requiere confirmación explícita", code="confirmation_required")
    approvals = {str(item) for item in approved_permissions} if isinstance(approved_permissions, list) else set()
    missing_permissions = sorted(set(package["permissions"]) - approvals)
    if missing_permissions:
        raise CapabilityPackageError(
            f"Falta aprobar: {', '.join(missing_permissions)}",
            code="permission_approval_required",
        )

    with _LOCK:
        record = _load_registry()["packages"].get(package_id)
    if not isinstance(record, dict):
        raise CapabilityPackageError("Pipeline externo no encontrado", code="not_found")
    package_dir = _package_dir(record)
    metadata = _read_json(package_dir / ".bago-package.json", {})
    manifest = metadata.get("package_manifest", {}) if isinstance(metadata, dict) else {}
    definition = _pipeline_definition(record, package_dir, manifest)
    clean_inputs = _validate_values(
        _validate_object_schema(definition.get("input_schema"), field="pipeline.input_schema"),
        inputs,
        field="input",
    )
    _enforce_pipeline_dependencies(manifest, definition)

    stack = list(getattr(_PIPELINE_EXECUTION, "stack", []))
    if package_id in stack:
        raise CapabilityPackageError(
            f"Referencia pipeline anidada cíclica: {' -> '.join([*stack, package_id])}",
            code="pipeline_cycle",
        )
    _PIPELINE_EXECUTION.stack = [*stack, package_id]
    encoded_input = json.dumps({"input": clean_inputs}, ensure_ascii=False)
    execution_id = f"pipe-{uuid.uuid4().hex[:16]}"
    receipt_id = f"receipt-{uuid.uuid4().hex[:16]}"
    started_at = _now()
    started = time.perf_counter()
    try:
        if package["execution_mode"] == "executable":
            entrypoint = package_dir / Path(*PurePosixPath(str(manifest["entrypoint"])).parts)
            payload = {
                "input": clean_inputs,
                "context": {"pipeline_id": package_id, "version": package["version"]},
            }
            encoded_input = json.dumps(payload, ensure_ascii=False)
            timeout_s = int(definition["runtime"]["timeout_s"])
            try:
                completed = subprocess.run(
                    [sys.executable, str(entrypoint)],
                    input=encoded_input,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    cwd=str(package_dir),
                    env=_execution_environment(package_id, package["version"]),
                    timeout=timeout_s,
                    shell=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                stdout = completed.stdout[-MAX_OUTPUT_CHARS:]
                stderr = completed.stderr[-MAX_OUTPUT_CHARS:].strip()
                status = "succeeded" if completed.returncode == 0 else "failed"
                error = "" if completed.returncode == 0 else stderr or f"El runner terminó con código {completed.returncode}"
                exit_code = completed.returncode
            except subprocess.TimeoutExpired as exc:
                stdout = str(exc.stdout or "")[-MAX_OUTPUT_CHARS:]
                stderr = str(exc.stderr or "")[-MAX_OUTPUT_CHARS:]
                status = "timeout"
                error = f"Timeout de {timeout_s}s"
                exit_code = None
            except OSError as exc:
                stdout = ""
                stderr = ""
                status = "failed"
                error = str(exc)
                exit_code = None
            receipt = _pipeline_receipt(
                package=package,
                execution_id=execution_id,
                receipt_id=receipt_id,
                started_at=started_at,
                started=started,
                encoded_input=encoded_input,
                status=status,
                result=_parse_output(stdout),
                error=error,
                stderr=stderr,
                exit_code=exit_code,
                executor={"kind": "python-subprocess", "shell": False},
                permissions=package["permissions"],
            )
            return {"ok": status == "succeeded", "receipt": receipt}

        context = {"inputs": clean_inputs, "variables": definition["variables"], "steps": {}}
        step_receipts: list[dict[str, Any]] = []
        pipeline_status = "succeeded"
        pipeline_error = ""
        final_result: Any = None
        for step in _pipeline_step_order(definition):
            step_started = time.perf_counter()
            try:
                condition_met = _pipeline_condition(step["condition"], context)
                parameters = _resolve_pipeline_values(step["with"], context) if condition_met else {}
            except CapabilityPackageError as exc:
                pipeline_status = "failed"
                pipeline_error = f"{step['id']}: {exc}"
                failed_step = {
                    "step_id": step["id"],
                    "type": step["type"],
                    "status": "failed",
                    "attempts": 0,
                    "duration_ms": round((time.perf_counter() - step_started) * 1000, 1),
                    "result": None,
                    "receipt_id": None,
                    "error": str(exc),
                }
                step_receipts.append(failed_step)
                context["steps"][step["id"]] = {"ok": False, "status": "failed", "result": None}
                break
            if not condition_met:
                step_receipt = {
                    "step_id": step["id"],
                    "type": step["type"],
                    "status": "skipped",
                    "attempts": 0,
                    "duration_ms": 0.0,
                    "result": None,
                    "receipt_id": None,
                    "error": "",
                }
                step_receipts.append(step_receipt)
                context["steps"][step["id"]] = {"ok": True, "status": "skipped", "result": None}
                continue
            attempts, delay_s = _pipeline_retry_policy(step["retry"])
            invocation: dict[str, Any] = {"ok": False, "result": None, "receipt_id": None}
            step_error = ""
            step_status = "failed"
            used_attempts = 0
            for attempt in range(1, attempts + 1):
                used_attempts = attempt
                try:
                    invocation = _invoke_pipeline_step(
                        step,
                        parameters,
                        confirmed=confirmed,
                        approved_permissions=approved_permissions,
                        manager=manager,
                    )
                    step_status = "succeeded" if invocation["ok"] else "failed"
                    if invocation["ok"]:
                        break
                    step_error = "La ejecución referenciada devolvió estado fallido"
                except CapabilityPackageError as exc:
                    step_error = str(exc)
                    step_status = "blocked" if exc.code in {
                        "confirmation_required",
                        "permission_approval_required",
                        "trust_required",
                    } else "failed"
                if attempt < attempts and delay_s:
                    time.sleep(delay_s)
            elapsed_ms = round((time.perf_counter() - step_started) * 1000, 1)
            if step.get("timeout_s") and elapsed_ms > int(step["timeout_s"]) * 1000:
                step_status = "timeout"
                step_error = f"El paso superó {step['timeout_s']}s"
            step_receipt = {
                "step_id": step["id"],
                "type": step["type"],
                "status": step_status,
                "attempts": used_attempts,
                "duration_ms": elapsed_ms,
                "result": invocation.get("result"),
                "receipt_id": invocation.get("receipt_id"),
                "error": step_error,
            }
            step_receipts.append(step_receipt)
            context["steps"][step["id"]] = {
                "ok": step_status == "succeeded",
                "status": step_status,
                "result": invocation.get("result"),
            }
            if step_status != "succeeded":
                pipeline_status = "blocked" if step_status == "blocked" else "failed"
                pipeline_error = f"{step['id']}: {step_error}"
                break
            final_result = invocation.get("result")
        result = {"output": final_result, "steps": context["steps"]}
        receipt = _pipeline_receipt(
            package=package,
            execution_id=execution_id,
            receipt_id=receipt_id,
            started_at=started_at,
            started=started,
            encoded_input=encoded_input,
            status=pipeline_status,
            result=result,
            error=pipeline_error,
            executor={"kind": "declarative-pipeline"},
            permissions=package["permissions"],
            steps=step_receipts,
        )
        return {"ok": pipeline_status == "succeeded", "receipt": receipt}
    finally:
        _PIPELINE_EXECUTION.stack = stack


def list_receipts(limit: int = 50) -> list[dict[str, Any]]:
    root = receipts_root()
    if not root.exists():
        return []
    receipts = [_read_json(path, {}) for path in root.glob("receipt-*.json")]
    valid = [item for item in receipts if isinstance(item, dict) and item.get("receipt_id")]
    valid.sort(key=lambda item: str(item.get("finished_at") or ""), reverse=True)
    return valid[: max(1, min(int(limit), 100))]


def build_package_snapshot(capability_id: str) -> dict[str, Any]:
    package = get_package(capability_id)
    receipt = next((item for item in list_receipts() if item.get("receipt_id") == package.get("last_receipt_id")), None)
    runtime_state = package.get("last_status") or "not_started"
    execution_id = receipt.get("execution_id") if receipt else None
    receipt_id = receipt.get("receipt_id") if receipt else None
    evidence = [{"receipt_id": receipt_id, "status": runtime_state}] if receipt and runtime_state == "succeeded" else []
    pieces = [
        {
            "id": "package-input", "name": "Entrada validada", "type": "input",
            "purpose": "Datos declarados por input_schema.", "definition_state": "prepared",
            "availability": "available", "implementation": {"kind": "validator", "ref": CONTRACT_VERSION, "owner": "backend"},
            "requires": [], "produces": ["validated_input"],
            "authorization": {"mode": "inspect", "permissions": [], "approval_required": False},
            "evidence_expected": ["input_digest"], "fallback_piece_id": None, "block_reason": None,
        },
        {
            "id": "package-runner", "name": package["name"], "type": "tool",
            "purpose": package["description"], "definition_state": "prepared",
            "availability": "available" if package["enabled"] else "conditional",
            "implementation": {"kind": "python", "ref": package["runtime"].get("entrypoint", ""), "owner": "external_package"},
            "requires": ["validated_input"], "produces": ["runner_result"],
            "authorization": {"mode": "execute", "permissions": package["permissions"], "approval_required": True},
            "evidence_expected": ["execution receipt"], "fallback_piece_id": None,
            "block_reason": None if package["enabled"] else "La capacidad está desactivada.",
        },
        {
            "id": "package-output", "name": "Resultado con receipt", "type": "output",
            "purpose": "Salida limitada y evidencia persistida por el backend.", "definition_state": "prepared",
            "availability": "available", "implementation": {"kind": "receipt", "ref": "capabilities/receipts", "owner": "backend"},
            "requires": ["runner_result"], "produces": ["capability_result"],
            "authorization": {"mode": "inspect", "permissions": [], "approval_required": False},
            "evidence_expected": ["receipt_id"], "fallback_piece_id": None, "block_reason": None,
        },
    ]
    return {
        "schema_version": "0.2",
        "contract_version": "bago.capability/v0.2",
        "revision": 1,
        "etag": package["digest"],
        "source": {"authority": "backend", "provenance": f"capability-package:{capability_id}", "generated_at": _now()},
        "capability": {
            "id": package["id"], "name": package["name"], "version": package["version"],
            "description": package["description"], "definition_state": "prepared",
            "availability": "available" if package["enabled"] else "conditional", "tags": ["external", *package["tags"]],
        },
        "construction": {"user_goal": "Usar una capacidad externa gobernada por BAGO.", "confirmed": [], "assumptions": [], "missing_information": [], "decisions": [], "conflicts": []},
        "inputs": [{"id": "package-input", "name": "Input", "required": True, "media_types": ["application/json"], "constraints": []}],
        "outputs": [{"id": "package-output", "name": "Resultado", "media_types": ["application/json", "text/plain"], "acceptance_criteria": ["Receipt persistente"]}],
        "pieces": pieces,
        "routes": [{
            "id": "execute-package", "name": f"Ejecutar {package['name']}", "description": "Ruta backend con confirmación y receipt.",
            "priority": 1, "condition": "Paquete activo y permisos confirmados.",
            "steps": ["package-input", "package-runner", "package-output"],
            "availability": "available" if package["enabled"] else "conditional",
            "block_reason": None if package["enabled"] else "La capacidad está desactivada.",
            "fallback_route_id": None, "evidence_expected": ["receipt_id"],
        }],
        "governance": {
            "authority": {"decision": "backend", "execution": "backend", "verification": "backend"},
            "recommended_route_id": "execute-package",
            "confirmation_policy": {"required_for": ["external_code", *package["permissions"]], "reason": "Código local externo."},
            "action_policy": {
                "allowed": [{"id": "inspect", "kind": "inspect", "label": "Inspeccionar"}],
                "blocked": [{"id": "execute", "kind": "command", "label": "Ejecutar", "reason": "Usa el endpoint gobernado de Capability Packages."}],
            },
            "validation_criteria": [{"id": "package-valid", "description": "Manifest y runner válidos.", "method": "validate_manifest", "required": True}],
        },
        "runtime_snapshot": {
            "source": "capability_packages", "run_state": runtime_state, "selected_piece_id": "package-runner",
            "active_route_id": "execute-package", "execution_id": execution_id, "receipt_id": receipt_id,
            "observed_at": package.get("last_run_at"),
        },
        "host_binding": {"host": "BAGO", "surface": "graph", "mode": "read_only", "feature_flag": "capability_packages_v1", "persistence_root": "user_state", "expected_contract_version": "bago.contract.ui.v1"},
        "evidence": evidence,
    }

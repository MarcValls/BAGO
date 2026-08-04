"""Capability Packages v1: import, registry, execution and receipts.

External packages are ZIP archives with a declarative ``capability.json`` and
one Python entrypoint. The renderer never loads package JavaScript. All code
execution remains backend-owned, requires an enabled package plus explicit
confirmation, runs without a shell, and produces a persisted receipt.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from bago_core.user_state_paths import state_root


CONTRACT_VERSION = "bago.capability/v1"
SCHEMA_VERSION = "1.0"
MAX_ARCHIVE_BYTES = 600 * 1024
MAX_UNPACKED_BYTES = 2 * 1024 * 1024
MAX_MEMBERS = 64
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
_LOCK = threading.RLock()


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


def _extract_archive(archive: bytes, destination: Path) -> dict[str, Any]:
    try:
        zip_file = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise CapabilityPackageError("El archivo no es un ZIP válido") from exc
    with zip_file:
        members = zip_file.infolist()
        if not members or len(members) > MAX_MEMBERS:
            raise CapabilityPackageError(f"El paquete debe contener entre 1 y {MAX_MEMBERS} entradas")
        total = sum(max(0, member.file_size) for member in members)
        if total > MAX_UNPACKED_BYTES:
            raise CapabilityPackageError("El contenido descomprimido supera 2 MB", code="package_too_large")
        for member in members:
            relative = _safe_relative_path(member.filename, field="entrada ZIP")
            mode = (member.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise CapabilityPackageError("No se permiten enlaces simbólicos", code="unsafe_path")
            target = destination / Path(*relative.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zip_file.read(member))
    manifest_path = destination / "capability.json"
    if not manifest_path.is_file():
        raise CapabilityPackageError("Falta capability.json en la raíz del ZIP")
    return _read_json(manifest_path, None)


def _package_dir(record: dict[str, Any]) -> Path:
    return packages_root() / "packages" / str(record["id"]) / str(record["version"])


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    package_dir = _package_dir(record)
    manifest = _read_json(package_dir / "capability.json", {})
    try:
        manifest = validate_manifest(manifest, package_dir=package_dir)
        available = True
        error = ""
    except CapabilityPackageError as exc:
        manifest = manifest if isinstance(manifest, dict) else {}
        available = False
        error = str(exc)
    return {
        "id": record.get("id", ""),
        "name": manifest.get("name") or record.get("name", record.get("id", "")),
        "version": record.get("version", ""),
        "description": manifest.get("description") or record.get("description", ""),
        "author": manifest.get("author", "local"),
        "enabled": bool(record.get("enabled")) and available,
        "available": available,
        "error": error,
        "permissions": manifest.get("permissions", []),
        "runtime": manifest.get("runtime", {}),
        "configuration_schema": manifest.get("configuration_schema", {"type": "object", "properties": {}, "required": []}),
        "input_schema": manifest.get("input_schema", {"type": "object", "properties": {}, "required": []}),
        "config": record.get("config", {}) if isinstance(record.get("config"), dict) else {},
        "digest": record.get("digest", ""),
        "installed_at": record.get("installed_at", ""),
        "last_run_at": record.get("last_run_at"),
        "last_status": record.get("last_status", "not_started"),
        "last_receipt_id": record.get("last_receipt_id"),
        "tags": manifest.get("tags", []),
    }


def import_package(*, content_base64: str, file_name: str, confirm_trust: bool) -> dict[str, Any]:
    if not confirm_trust:
        raise CapabilityPackageError("Debes confirmar que confías en el código local del paquete", code="trust_required")
    if not str(file_name or "").lower().endswith(".zip"):
        raise CapabilityPackageError("Solo se admiten paquetes .zip")
    try:
        archive = base64.b64decode(str(content_base64 or ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CapabilityPackageError("content_base64 no es válido") from exc
    if not archive or len(archive) > MAX_ARCHIVE_BYTES:
        raise CapabilityPackageError("El ZIP debe pesar entre 1 byte y 600 KB", code="package_too_large")
    digest = hashlib.sha256(archive).hexdigest()
    root = packages_root()
    staging_root = root / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="import-", dir=staging_root) as temporary:
        temporary_path = Path(temporary) / "package"
        temporary_path.mkdir()
        raw_manifest = _extract_archive(archive, temporary_path)
        manifest = validate_manifest(raw_manifest, package_dir=temporary_path)
        capability_id = manifest["id"]
        version = manifest["version"]
        target = root / "packages" / capability_id / version
        metadata = {
            "id": capability_id,
            "name": manifest["name"],
            "version": version,
            "description": manifest["description"],
            "digest": digest,
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
                "config": {},
                "last_status": "not_started",
                "last_receipt_id": None,
                "last_run_at": None,
            }
            registry["packages"][capability_id] = record
            _save_registry(registry)
    return {"ok": True, "already_installed": False, "package": _public_record(record)}


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


def set_enabled(capability_id: str, enabled: bool) -> dict[str, Any]:
    with _LOCK:
        registry = _load_registry()
        record = registry["packages"].get(capability_id)
        if not isinstance(record, dict):
            raise CapabilityPackageError("Capacidad externa no encontrada", code="not_found")
        public = _public_record(record)
        if enabled and not public["available"]:
            raise CapabilityPackageError(public["error"] or "El paquete no está disponible")
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
        record = registry["packages"].get(receipt["capability_id"])
        if isinstance(record, dict):
            record["last_receipt_id"] = receipt["receipt_id"]
            record["last_run_at"] = receipt["finished_at"]
            record["last_status"] = receipt["status"]
            registry["packages"][receipt["capability_id"]] = record
            _save_registry(registry)


def execute_package(
    capability_id: str,
    *,
    inputs: Any,
    confirmed: bool,
    approved_permissions: Any,
) -> dict[str, Any]:
    package = get_package(capability_id)
    if not package["enabled"]:
        raise CapabilityPackageError("Activa la capacidad antes de ejecutarla", code="not_enabled")
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
    manifest = validate_manifest(_read_json(package_dir / "capability.json", {}), package_dir=package_dir)
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
            timeout=int(manifest["runtime"]["timeout_s"]),
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
        error = f"Timeout de {manifest['runtime']['timeout_s']}s"
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

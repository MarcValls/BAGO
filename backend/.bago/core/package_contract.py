"""Validation and deterministic serialization for ``bago.package/v1``."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


CONTRACT_VERSION = "bago.package/v1"
SCHEMA_VERSION = "1.0"
MAX_ARCHIVE_BYTES = 600 * 1024
MAX_UNPACKED_BYTES = 2 * 1024 * 1024
MAX_MEMBERS = 64
KINDS = {"capability", "pipeline"}
EXECUTION_MODES = {"declarative", "executable"}
ALLOWED_PERMISSIONS = {
    "filesystem.read",
    "filesystem.write",
    "network",
    "process",
}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9._-]+)?$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SIGNATURE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:/+-]{1,160}$")
_STEP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CONDITION_RE = re.compile(
    r"^(?:!|not )?(?:(?:inputs|variables)\.[A-Za-z0-9_.-]+|steps\.[A-Za-z0-9._-]+\.(?:ok|status))$"
)
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
PIPELINE_STEP_TYPES = {"capability", "pipeline", "approval", "noop"}


class PackageContractError(ValueError):
    """A package does not satisfy the archive or contract rules."""

    def __init__(self, message: str, *, code: str = "invalid_package") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LoadedPackage:
    manifest: dict[str, Any]
    payload: dict[str, bytes]
    legacy_source: bool
    digest_state: str
    signature_state: str
    warnings: tuple[str, ...]

    def inspection(self) -> dict[str, Any]:
        manifest = self.manifest
        return {
            "ok": True,
            "identity": {
                "id": manifest["id"],
                "name": manifest["name"],
                "version": manifest["version"],
                "description": manifest["description"],
                "author": manifest["author"],
            },
            "kind": manifest["kind"],
            "execution_mode": manifest["execution_mode"],
            "definition": manifest["definition"],
            "entrypoint": manifest.get("entrypoint"),
            "files": manifest["files"],
            "compatibility": manifest["compatibility"],
            "dependencies": manifest["dependencies"],
            "permissions": manifest["permissions"],
            "digest_state": self.digest_state,
            "signature_state": self.signature_state,
            "legacy_source": self.legacy_source,
            "warnings": list(self.warnings),
            "errors": [],
        }


def safe_relative_path(raw: Any, *, field: str) -> PurePosixPath:
    if not isinstance(raw, str):
        raise PackageContractError(f"{field} debe ser una ruta relativa segura", code="unsafe_path")
    normalized = raw.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    unsafe_segment = any(
        not part
        or part[-1:] in {".", " "}
        or any(ord(character) < 32 for character in part)
        or part.split(".", 1)[0].casefold() in _WINDOWS_RESERVED
        for part in path.parts
    )
    if (
        not normalized
        or raw != normalized
        or str(path) != normalized
        or "\x00" in normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or ":" in normalized
        or unsafe_segment
    ):
        raise PackageContractError(f"{field} debe ser una ruta relativa segura", code="unsafe_path")
    return path


def _required_text(raw: dict[str, Any], field: str, *, maximum: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PackageContractError(f"{field} es obligatorio")
    clean = value.strip()
    if len(clean) > maximum:
        raise PackageContractError(f"{field} supera {maximum} caracteres")
    return clean


def _validate_permissions(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PackageContractError("permissions debe ser una lista de strings")
    permissions = sorted(set(value))
    unknown = sorted(set(permissions) - ALLOWED_PERMISSIONS)
    if unknown:
        raise PackageContractError(f"Permisos no soportados: {', '.join(unknown)}")
    return permissions


def _validate_dependencies(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise PackageContractError("dependencies debe ser una lista")
    dependencies: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise PackageContractError("Cada dependencia debe ser un objeto")
        if set(item) != {"id", "version"}:
            raise PackageContractError("Cada dependencia solo admite id y version")
        dependency_id = str(item.get("id") or "").strip().lower()
        version = str(item.get("version") or "").strip()
        if not _ID_RE.fullmatch(dependency_id) or not version:
            raise PackageContractError("Cada dependencia requiere id válido y version")
        if dependency_id in seen:
            raise PackageContractError(f"Dependencia duplicada: {dependency_id}")
        seen.add(dependency_id)
        dependencies.append({"id": dependency_id, "version": version})
    return dependencies


def _validate_signature(value: Any) -> tuple[dict[str, str] | None, str, list[str]]:
    if value is None:
        return None, "unsigned", ["El paquete no incluye firma; se tratará como no firmado."]
    if not isinstance(value, dict):
        raise PackageContractError("signature contiene metadatos inválidos", code="invalid_signature")
    if set(value) != {"algorithm", "key_id", "value"}:
        raise PackageContractError("signature contiene campos inválidos", code="invalid_signature")
    algorithm = value.get("algorithm")
    key_id = value.get("key_id")
    encoded = value.get("value")
    if not all(isinstance(item, str) and _SIGNATURE_TOKEN_RE.fullmatch(item) for item in (algorithm, key_id)):
        raise PackageContractError("signature.algorithm/key_id son inválidos", code="invalid_signature")
    if not isinstance(encoded, str) or not encoded:
        raise PackageContractError("signature.value es inválido", code="invalid_signature")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PackageContractError("signature.value debe ser base64 válido", code="invalid_signature") from exc
    if not decoded:
        raise PackageContractError("signature.value está vacío", code="invalid_signature")
    clean = {"algorithm": algorithm, "key_id": key_id, "value": encoded}
    return clean, "unknown_key", [f"No hay almacén de claves para verificar la firma {key_id}."]


def _validate_inventory(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise PackageContractError("files debe ser un inventario no vacío")
    inventory: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise PackageContractError("Cada entrada de files debe ser un objeto")
        if set(item) != {"path", "size", "sha256"}:
            raise PackageContractError("Cada entrada de files requiere solo path, size y sha256")
        path = str(safe_relative_path(item.get("path"), field="files.path"))
        key = path.casefold()
        if key in seen or path == "bago.package.json":
            raise PackageContractError(f"Entrada de inventario duplicada o reservada: {path}")
        seen.add(key)
        size = item.get("size")
        sha256 = item.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise PackageContractError(f"files[{path}].size debe ser un entero no negativo")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise PackageContractError(f"files[{path}].sha256 debe ser un SHA-256 hexadecimal")
        inventory.append({"path": path, "size": size, "sha256": sha256.lower()})
    return sorted(inventory, key=lambda item: item["path"])


def validate_pipeline_definition(raw: Any, *, package_id: str) -> dict[str, Any]:
    """Validate and normalize the supported declarative pipeline definition."""
    if not isinstance(raw, dict):
        raise PackageContractError("definitions/pipeline.json debe contener un objeto")
    allowed = {
        "schema_version",
        "contract_version",
        "id",
        "description",
        "variables",
        "runtime",
        "input_schema",
        "output_schema",
        "steps",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise PackageContractError(f"Campos pipeline no soportados: {', '.join(unknown)}")
    if raw.get("schema_version") not in (None, SCHEMA_VERSION):
        raise PackageContractError("schema_version pipeline no soportado", code="unsupported_contract")
    if raw.get("contract_version") not in (None, "bago.pipeline/v1"):
        raise PackageContractError("contract_version pipeline debe ser bago.pipeline/v1", code="unsupported_contract")
    pipeline_id = raw.get("id")
    if not isinstance(pipeline_id, str) or pipeline_id != package_id:
        raise PackageContractError("El pipeline requiere un id igual al del paquete")
    variables = raw.get("variables", {})
    if not isinstance(variables, dict):
        raise PackageContractError("pipeline.variables debe ser un objeto")
    for schema_name in ("input_schema", "output_schema"):
        schema = raw.get(schema_name)
        if schema is not None and (not isinstance(schema, dict) or schema.get("type", "object") != "object"):
            raise PackageContractError(f"pipeline.{schema_name} debe ser un schema de objeto")
    input_schema = raw.get("input_schema") or {"type": "object", "properties": {}}
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise PackageContractError("pipeline.input_schema contiene properties/required inválidos")
    if any(not isinstance(name, str) or name not in properties for name in required):
        raise PackageContractError("pipeline.input_schema.required contiene propiedades desconocidas")
    for name, property_schema in properties.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(property_schema, dict)
            or property_schema.get("type", "string") not in {"string", "number", "integer", "boolean"}
        ):
            raise PackageContractError(f"pipeline.input_schema.{name} no está soportado")
    runtime = raw.get("runtime", {"kind": "python", "timeout_s": 30})
    if (
        not isinstance(runtime, dict)
        or set(runtime) - {"kind", "timeout_s"}
        or runtime.get("kind", "python") != "python"
    ):
        raise PackageContractError("pipeline.runtime solo admite Python")
    runtime_timeout = runtime.get("timeout_s", 30)
    if (
        not isinstance(runtime_timeout, int)
        or isinstance(runtime_timeout, bool)
        or not 1 <= runtime_timeout <= 900
    ):
        raise PackageContractError("pipeline.runtime.timeout_s debe estar entre 1 y 900")
    steps = raw.get("steps")
    if not isinstance(steps, list):
        raise PackageContractError("La definición pipeline requiere steps")

    clean_steps: list[dict[str, Any]] = []
    step_ids: set[str] = set()
    for item in steps:
        if not isinstance(item, dict):
            raise PackageContractError("Cada paso pipeline debe ser un objeto")
        allowed_step = {"id", "type", "depends_on", "uses", "with", "timeout_s", "retry", "condition"}
        unknown_step = sorted(set(item) - allowed_step)
        if unknown_step:
            raise PackageContractError(f"Campos de paso no soportados: {', '.join(unknown_step)}")
        step_id = item.get("id")
        step_type = item.get("type")
        if not isinstance(step_id, str) or not _STEP_ID_RE.fullmatch(step_id):
            raise PackageContractError("Cada paso pipeline requiere un id estable")
        if step_id in step_ids:
            raise PackageContractError(f"Paso pipeline duplicado: {step_id}", code="duplicate_step")
        if step_type not in PIPELINE_STEP_TYPES:
            raise PackageContractError(f"Tipo de paso no soportado: {step_type}", code="unsupported_step")
        step_ids.add(step_id)
        depends_on = item.get("depends_on", [])
        if not isinstance(depends_on, list) or any(not isinstance(value, str) for value in depends_on):
            raise PackageContractError(f"{step_id}.depends_on debe ser una lista de ids")
        if len(depends_on) != len(set(depends_on)) or step_id in depends_on:
            raise PackageContractError(f"{step_id}.depends_on contiene ids duplicados o propios")
        uses = item.get("uses")
        if step_type in {"capability", "pipeline"}:
            if not isinstance(uses, str) or not _ID_RE.fullmatch(uses):
                raise PackageContractError(f"{step_id}.uses debe ser un id de paquete")
        elif uses not in (None, ""):
            raise PackageContractError(f"{step_id}.uses no aplica al tipo {step_type}")
        parameters = item.get("with", {})
        if not isinstance(parameters, dict):
            raise PackageContractError(f"{step_id}.with debe ser un objeto")
        timeout_s = item.get("timeout_s")
        if timeout_s is not None and (
            not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or not 1 <= timeout_s <= 900
        ):
            raise PackageContractError(f"{step_id}.timeout_s debe estar entre 1 y 900")
        retry = item.get("retry", 0)
        if isinstance(retry, int) and not isinstance(retry, bool):
            if not 0 <= retry <= 5:
                raise PackageContractError(f"{step_id}.retry debe estar entre 0 y 5")
            clean_retry: int | dict[str, Any] = retry
        elif isinstance(retry, dict):
            if set(retry) - {"max_attempts", "delay_s"}:
                raise PackageContractError(f"{step_id}.retry contiene campos no soportados")
            attempts = retry.get("max_attempts", 1)
            delay_s = retry.get("delay_s", 0)
            if (
                not isinstance(attempts, int)
                or isinstance(attempts, bool)
                or not 1 <= attempts <= 6
                or not isinstance(delay_s, (int, float))
                or isinstance(delay_s, bool)
                or not 0 <= delay_s <= 60
            ):
                raise PackageContractError(f"{step_id}.retry es inválido")
            clean_retry = {"max_attempts": attempts, "delay_s": delay_s}
        else:
            raise PackageContractError(f"{step_id}.retry es inválido")
        condition = item.get("condition", True)
        if not isinstance(condition, bool) and (
            not isinstance(condition, str) or not _CONDITION_RE.fullmatch(condition)
        ):
            raise PackageContractError(f"{step_id}.condition no está soportada")
        clean_step = {
            "id": step_id,
            "type": step_type,
            "depends_on": list(depends_on),
            "with": parameters,
            "retry": clean_retry,
            "condition": condition,
        }
        if uses:
            clean_step["uses"] = uses
        if timeout_s is not None:
            clean_step["timeout_s"] = timeout_s
        clean_steps.append(clean_step)

    unknown_dependencies = sorted({
        dependency
        for step in clean_steps
        for dependency in step["depends_on"]
        if dependency not in step_ids
    })
    if unknown_dependencies:
        raise PackageContractError(
            f"Dependencias de paso desconocidas: {', '.join(unknown_dependencies)}",
            code="unknown_step_dependency",
        )
    for step in clean_steps:
        condition = step["condition"]
        if isinstance(condition, str):
            expression = condition[1:] if condition.startswith("!") else condition[4:] if condition.startswith("not ") else condition
            if expression.startswith("steps."):
                referenced_step = expression.split(".", 2)[1]
                if referenced_step not in step_ids:
                    raise PackageContractError(
                        f"Condición con paso desconocido: {referenced_step}",
                        code="unknown_step_dependency",
                    )
                if referenced_step not in step["depends_on"]:
                    raise PackageContractError(
                        f"{step['id']}.condition debe referir un paso de depends_on",
                        code="unknown_step_dependency",
                    )
    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {step["id"]: step for step in clean_steps}

    def visit(step_id: str) -> None:
        if step_id in visiting:
            raise PackageContractError("El pipeline contiene un ciclo", code="pipeline_cycle")
        if step_id in visited:
            return
        visiting.add(step_id)
        for dependency in by_id[step_id]["depends_on"]:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step in clean_steps:
        visit(step["id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": "bago.pipeline/v1",
        "id": pipeline_id,
        "description": str(raw.get("description") or ""),
        "variables": variables,
        "runtime": {"kind": "python", "timeout_s": runtime_timeout},
        "input_schema": input_schema,
        "output_schema": raw.get("output_schema") or {"type": "object"},
        "steps": clean_steps,
    }


def validate_manifest(raw: Any, payload: dict[str, bytes]) -> tuple[dict[str, Any], str, list[str]]:
    if not isinstance(raw, dict):
        raise PackageContractError("bago.package.json debe contener un objeto JSON")
    if raw.get("contract_version") != CONTRACT_VERSION or str(raw.get("schema_version")) != SCHEMA_VERSION:
        raise PackageContractError(
            f"Contrato requerido: {CONTRACT_VERSION} schema {SCHEMA_VERSION}",
            code="unsupported_contract",
        )
    allowed_fields = {
        "schema_version",
        "contract_version",
        "kind",
        "execution_mode",
        "id",
        "name",
        "version",
        "description",
        "author",
        "definition",
        "entrypoint",
        "permissions",
        "compatibility",
        "dependencies",
        "files",
        "signature",
        "schedule_defaults",
    }
    unknown_fields = sorted(set(raw) - allowed_fields)
    if unknown_fields:
        raise PackageContractError(f"Campos de manifest no soportados: {', '.join(unknown_fields)}")
    kind = raw.get("kind")
    execution_mode = raw.get("execution_mode")
    if kind not in KINDS or execution_mode not in EXECUTION_MODES:
        raise PackageContractError("kind o execution_mode no soportado")
    package_id = _required_text(raw, "id", maximum=64).lower()
    version = _required_text(raw, "version", maximum=80)
    if not _ID_RE.fullmatch(package_id):
        raise PackageContractError("id inválido; usa 3-64 caracteres [a-z0-9._-]")
    if not _VERSION_RE.fullmatch(version):
        raise PackageContractError("version debe usar formato semver, por ejemplo 1.0.0")

    definition = str(safe_relative_path(raw.get("definition"), field="definition"))
    expected_definition = f"definitions/{kind}.json"
    if definition != expected_definition:
        raise PackageContractError(f"definition debe ser {expected_definition}")
    entrypoint: str | None = None
    if execution_mode == "executable":
        entrypoint = str(safe_relative_path(raw.get("entrypoint"), field="entrypoint"))
        if not entrypoint.startswith("runtime/") or not entrypoint.endswith(".py"):
            raise PackageContractError("entrypoint ejecutable debe ser un .py bajo runtime/")
    elif raw.get("entrypoint") not in (None, ""):
        raise PackageContractError("Los paquetes declarativos no deben declarar entrypoint")

    compatibility = raw.get("compatibility")
    if not isinstance(compatibility, dict):
        raise PackageContractError("compatibility debe ser un objeto")
    inventory = _validate_inventory(raw.get("files"))
    declared = {item["path"]: item for item in inventory}
    actual = set(payload)
    missing = sorted(set(declared) - actual)
    undeclared = sorted(actual - set(declared))
    if missing:
        raise PackageContractError(f"Faltan archivos declarados: {', '.join(missing)}", code="missing_file")
    if undeclared:
        raise PackageContractError(f"Archivos no declarados: {', '.join(undeclared)}", code="undeclared_file")
    for path, item in declared.items():
        content = payload[path]
        if len(content) != item["size"]:
            raise PackageContractError(f"Tamaño inválido para {path}", code="digest_mismatch")
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise PackageContractError(f"SHA-256 inválido para {path}", code="digest_mismatch")
    if definition not in payload:
        raise PackageContractError(f"No existe la definición declarada: {definition}", code="missing_file")
    if entrypoint and entrypoint not in payload:
        raise PackageContractError(f"No existe el entrypoint declarado: {entrypoint}", code="missing_file")

    try:
        definition_data = json.loads(payload[definition].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageContractError(f"{definition} no contiene JSON UTF-8 válido") from exc
    if not isinstance(definition_data, dict):
        raise PackageContractError(f"{definition} debe contener un objeto JSON")
    if definition_data.get("id") not in (None, package_id):
        raise PackageContractError("El id de la definición no coincide con el manifest")
    if kind == "capability":
        for schema_name in ("configuration_schema", "input_schema", "output_schema"):
            schema = definition_data.get(schema_name)
            if schema is not None and (not isinstance(schema, dict) or schema.get("type", "object") != "object"):
                raise PackageContractError(f"{definition}: {schema_name} debe ser un schema de objeto")
        tags = definition_data.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise PackageContractError(f"{definition}: tags debe ser una lista de strings")
        if execution_mode == "executable":
            runtime = definition_data.get("runtime")
            if not isinstance(runtime, dict) or runtime.get("kind") != "python":
                raise PackageContractError(f"{definition}: runtime.kind debe ser python")
            timeout_s = runtime.get("timeout_s", 30)
            if not isinstance(timeout_s, int) or isinstance(timeout_s, bool) or not 1 <= timeout_s <= 900:
                raise PackageContractError(f"{definition}: runtime.timeout_s debe estar entre 1 y 900")
    else:
        validate_pipeline_definition(definition_data, package_id=package_id)

    schedule_defaults = raw.get("schedule_defaults", [])
    if not isinstance(schedule_defaults, list):
        raise PackageContractError("schedule_defaults debe ser una lista")
    clean_schedules: list[dict[str, Any]] = []
    for suggestion in schedule_defaults:
        if not isinstance(suggestion, dict) or set(suggestion) - {"name", "schedule_type", "interval_s", "cron_expr", "timezone"}:
            raise PackageContractError("schedule_defaults contiene una sugerencia inválida")
        name = str(suggestion.get("name") or "").strip()
        schedule_type = str(suggestion.get("schedule_type") or "").strip()
        timezone_name = str(suggestion.get("timezone") or "UTC").strip()
        if not name or schedule_type not in {"interval", "cron"} or not timezone_name:
            raise PackageContractError("Cada schedule_default requiere name, schedule_type y timezone")
        clean_schedule = {"name": name[:120], "schedule_type": schedule_type, "timezone": timezone_name}
        if schedule_type == "interval":
            interval_s = suggestion.get("interval_s")
            if not isinstance(interval_s, int) or isinstance(interval_s, bool) or interval_s < 60:
                raise PackageContractError("schedule_defaults.interval_s debe ser al menos 60")
            clean_schedule["interval_s"] = interval_s
        else:
            cron_expr = str(suggestion.get("cron_expr") or "").strip()
            if len(cron_expr.split()) != 5:
                raise PackageContractError("schedule_defaults.cron_expr debe tener cinco campos")
            clean_schedule["cron_expr"] = cron_expr
        clean_schedules.append(clean_schedule)

    signature, signature_state, warnings = _validate_signature(raw.get("signature"))
    clean: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "kind": kind,
        "execution_mode": execution_mode,
        "id": package_id,
        "name": _required_text(raw, "name", maximum=120),
        "version": version,
        "description": _required_text(raw, "description", maximum=500),
        "author": _required_text(raw, "author", maximum=120),
        "definition": definition,
        "permissions": _validate_permissions(raw.get("permissions")),
        "compatibility": compatibility,
        "dependencies": _validate_dependencies(raw.get("dependencies")),
        "files": inventory,
        "schedule_defaults": clean_schedules,
    }
    if entrypoint:
        clean["entrypoint"] = entrypoint
    if signature:
        clean["signature"] = signature
    return clean, signature_state, warnings


def _archive_payload(archive: bytes) -> tuple[dict[str, bytes], dict[str, bool]]:
    if not archive or len(archive) > MAX_ARCHIVE_BYTES:
        raise PackageContractError("El ZIP debe pesar entre 1 byte y 600 KB", code="package_too_large")
    try:
        zip_file = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise PackageContractError("El archivo no es un ZIP válido") from exc
    payload: dict[str, bytes] = {}
    directories: dict[str, bool] = {}
    seen: set[str] = set()
    files_seen: set[str] = set()
    total = 0
    with zip_file:
        members = zip_file.infolist()
        if not members or len(members) > MAX_MEMBERS:
            raise PackageContractError(f"El paquete debe contener entre 1 y {MAX_MEMBERS} entradas")
        for member in members:
            path = str(safe_relative_path(member.filename.rstrip("/"), field="entrada ZIP"))
            key = path.casefold()
            if key in seen:
                raise PackageContractError(f"Entrada ZIP duplicada: {path}", code="duplicate_entry")
            seen.add(key)
            mode = (member.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise PackageContractError("No se permiten enlaces simbólicos", code="unsafe_path")
            if member.is_dir():
                directories[path] = True
                continue
            if any(str(parent).casefold() in files_seen for parent in PurePosixPath(path).parents if str(parent) != "."):
                raise PackageContractError(f"Conflicto de rutas ZIP: {path}", code="unsafe_path")
            if any(existing.startswith(f"{key}/") for existing in files_seen):
                raise PackageContractError(f"Conflicto de rutas ZIP: {path}", code="unsafe_path")
            files_seen.add(key)
            total += max(0, member.file_size)
            if total > MAX_UNPACKED_BYTES:
                raise PackageContractError("El contenido descomprimido supera 2 MB", code="package_too_large")
            try:
                content = zip_file.read(member)
            except (OSError, RuntimeError, NotImplementedError, zipfile.BadZipFile) as exc:
                raise PackageContractError(f"No se pudo leer {path} del ZIP") from exc
            if len(content) != member.file_size:
                raise PackageContractError(f"Tamaño ZIP incoherente para {path}")
            payload[path] = content
    return payload, directories


def _legacy_manifest(payload: dict[str, bytes]) -> tuple[dict[str, Any], str, list[str]]:
    try:
        legacy = json.loads(payload["capability.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageContractError("capability.json no contiene JSON UTF-8 válido") from exc
    if not isinstance(legacy, dict):
        raise PackageContractError("capability.json debe contener un objeto JSON")
    package_id = _required_text(legacy, "id", maximum=64).lower()
    version = _required_text(legacy, "version", maximum=80)
    if legacy.get("contract_version") != "bago.capability/v1" or str(legacy.get("schema_version")) != SCHEMA_VERSION:
        raise PackageContractError("Contrato legacy requerido: bago.capability/v1 schema 1.0")
    if not _ID_RE.fullmatch(package_id) or not _VERSION_RE.fullmatch(version):
        raise PackageContractError("id o version legacy inválidos")
    runtime = legacy.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("kind") != "python":
        raise PackageContractError("runtime.kind legacy debe ser python")
    entrypoint = str(safe_relative_path(runtime.get("entrypoint"), field="runtime.entrypoint"))
    if entrypoint not in payload:
        raise PackageContractError(f"No existe el entrypoint declarado: {entrypoint}", code="missing_file")
    inventory = [
        {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in sorted(payload.items())
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "kind": "capability",
        "execution_mode": "executable",
        "id": package_id,
        "name": _required_text(legacy, "name", maximum=120),
        "version": version,
        "description": _required_text(legacy, "description", maximum=500),
        "author": str(legacy.get("author") or "local")[:120],
        "definition": "capability.json",
        "entrypoint": entrypoint,
        "permissions": _validate_permissions(legacy.get("permissions", [])),
        "compatibility": {"bago": "legacy-capability-v1"},
        "dependencies": [],
        "files": inventory,
        "schedule_defaults": [],
    }
    return manifest, "unsigned", ["Paquete capability.json legacy normalizado.", "El paquete no incluye firma; se tratará como no firmado."]


def load_archive(archive: bytes) -> LoadedPackage:
    payload, _directories = _archive_payload(archive)
    if "bago.package.json" in payload:
        try:
            raw = json.loads(payload.pop("bago.package.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PackageContractError("bago.package.json no contiene JSON UTF-8 válido") from exc
        manifest, signature_state, warnings = validate_manifest(raw, payload)
        return LoadedPackage(manifest, payload, False, "verified", signature_state, tuple(warnings))
    if "capability.json" in payload:
        manifest, signature_state, warnings = _legacy_manifest(payload)
        return LoadedPackage(manifest, payload, True, "verified", signature_state, tuple(warnings))
    raise PackageContractError("Falta bago.package.json o capability.json en la raíz del ZIP")


def inspection_error(error: PackageContractError) -> dict[str, Any]:
    return {
        "ok": False,
        "identity": None,
        "kind": None,
        "execution_mode": None,
        "files": [],
        "compatibility": {},
        "dependencies": [],
        "permissions": [],
        "digest_state": "invalid" if error.code == "digest_mismatch" else "unknown",
        "signature_state": "invalid" if error.code == "invalid_signature" else "unsigned",
        "legacy_source": False,
        "warnings": [],
        "errors": [{"code": error.code, "message": str(error)}],
    }


def canonical_json(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def canonical_archive(manifest: dict[str, Any], payload: dict[str, bytes]) -> bytes:
    clean_manifest = {key: value for key, value in manifest.items() if key != "files"}
    clean_manifest["files"] = [
        {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in sorted(payload.items())
    ]
    manifest_bytes = canonical_json(clean_manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in [("bago.package.json", manifest_bytes), *sorted(payload.items())]:
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()

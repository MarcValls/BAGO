#!/usr/bin/env python3
"""Canonical pattern registry for context routing.

The mixin consumes immutable snapshots from this module. File formats, pack
manifests, integrity checks, precedence, and diagnostics stay here.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import threading
import time
import tomllib
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any


PATTERN_DIR = Path(__file__).resolve().parent / "context_patterns"
LOADER_VERSION = "pattern-loader-v1"
SCHEMA_VERSION = "context-pattern-schema-v1"
MIGRATIONS_VERSION = "none"
RUNTIME_VERSION = "4.8.0"
MANIFEST_NAME = "manifest.json"
AUTHORIZED_EXTENSIONS = frozenset({".json", ".toml", ".csv", ".md", ".markdown", ".yml", ".yaml", ".blob", ".txt"})
MAX_FILE_BYTES = 128 * 1024
MAX_RECORDS = 5000
MAX_STRING_LENGTH = 512
MAX_DEPTH = 12

CATEGORIES = ("workspace_markers", "workspace_followups")
CATEGORY_ALIASES = MappingProxyType({
    "markers": "workspace_markers",
    "marker": "workspace_markers",
    "workspace_markers": "workspace_markers",
    "workspace": "workspace_markers",
    "followups": "workspace_followups",
    "followup": "workspace_followups",
    "workspace_followups": "workspace_followups",
})

CANONICAL_FIELD_SCHEMA = MappingProxyType({
    "canonical_id": {"type": "str", "required": True, "nullable": False, "merge": "identity", "overridable": False, "sensitivity": "low"},
    "domain": {"type": "str", "required": True, "nullable": False, "merge": "identity", "overridable": False, "sensitivity": "low"},
    "category": {"type": "str", "required": True, "nullable": False, "merge": "identity", "overridable": False, "sensitivity": "low"},
    "name": {"type": "str", "required": True, "nullable": False, "merge": "identity", "overridable": False, "sensitivity": "low"},
    "pattern_version": {"type": "str", "required": True, "nullable": False, "merge": "replace", "overridable": False, "sensitivity": "low"},
    "value": {"type": "str", "required": True, "nullable": False, "merge": "union_unique", "overridable": True, "sensitivity": "low"},
    "aliases": {"type": "list[str]", "required": False, "default": [], "nullable": False, "merge": "union_unique", "overridable": True, "sensitivity": "low"},
    "case_sensitive": {"type": "bool", "required": False, "default": False, "nullable": False, "merge": "replace", "overridable": False, "sensitivity": "low"},
    "normalization": {"type": "str", "required": False, "default": "unicode_nfkc_lower_space", "nullable": False, "merge": "replace", "overridable": False, "sensitivity": "low"},
    "deprecated": {"type": "bool", "required": False, "default": False, "nullable": False, "merge": "replace", "overridable": True, "sensitivity": "low"},
    "state": {"type": "str", "required": True, "nullable": False, "merge": "lifecycle", "overridable": False, "sensitivity": "low"},
})


@dataclass(frozen=True)
class PatternDiagnostic:
    severity: str
    message: str
    pack_id: str = ""
    file: str = ""
    line: int = 0
    column: int = 0
    field_path: str = ""
    pattern_id: str = ""
    rule: str = ""
    received: str = ""
    expected: str = ""
    correction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class PatternSource:
    pack_id: str
    path: str
    line: int = 0
    column: int = 0
    original_value: str = ""
    normalized_value: str = ""
    migration: str = ""


@dataclass(frozen=True)
class PatternDefinition:
    canonical_id: str
    domain: str
    category: str
    name: str
    pattern_version: str
    value: str
    aliases: tuple[str, ...]
    case_sensitive: bool
    normalization: str
    deprecated: bool
    state: str
    priority: int
    trust_level: str
    pack_id: str
    source: PatternSource


@dataclass(frozen=True)
class PatternPackManifest:
    pack_id: str
    pack_version: str
    required_schema_version: str
    domains: tuple[str, ...]
    dependencies: tuple[str, ...]
    priority: int
    trust_level: str
    files: tuple[dict[str, str], ...]
    runtime_min: str
    runtime_max: str
    required: bool
    recursive: bool
    authorized_extensions: tuple[str, ...]
    symlinks: str
    source_kinds: tuple[str, ...]
    manifest_path: str


@dataclass(frozen=True)
class PatternSnapshot:
    snapshot_id: str
    snapshot_version: str
    global_hash: str
    built_at: str
    packs: tuple[PatternPackManifest, ...]
    diagnostics: tuple[PatternDiagnostic, ...]
    precedence_rules: tuple[str, ...]
    loader_version: str
    schema_version: str
    migrations_version: str
    patterns: tuple[PatternDefinition, ...]
    effective: dict[str, tuple[str, ...]] = field(repr=False)
    definitions_by_id: dict[str, tuple[PatternDefinition, ...]] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "effective", MappingProxyType({
            key: tuple(value) for key, value in self.effective.items()
        }))
        object.__setattr__(self, "definitions_by_id", MappingProxyType({
            key: tuple(value) for key, value in self.definitions_by_id.items()
        }))


def _diagnostic(severity: str, message: str, **kwargs: Any) -> PatternDiagnostic:
    return PatternDiagnostic(severity=severity, message=message, **kwargs)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_limited(path: Path) -> bytes:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {MAX_FILE_BYTES} bytes")
    return path.read_bytes()


def _normalize_space(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\s+", " ", normalized.strip())
    return normalized.lower()


def _category(value: str) -> str:
    key = re.sub(r"[\s-]+", "_", str(value or "").strip().lower())
    return CATEGORY_ALIASES.get(key, "")


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_") or "pattern"


def _assert_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError(f"structure exceeds max depth {MAX_DEPTH}")
    if isinstance(value, dict):
        for item in value.values():
            _assert_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _assert_depth(item, depth + 1)
    elif isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        raise ValueError(f"string exceeds {MAX_STRING_LENGTH} chars")


def _json_no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class SourceResolver:
    """Discovers only manifests inside authorized roots, then declared files."""

    def __init__(self, roots: tuple[Path, ...] | None = None):
        self.roots = tuple((roots or (PATTERN_DIR,)))

    def resolve(self) -> tuple[PatternPackManifest, tuple[Path, ...], tuple[PatternDiagnostic, ...]]:
        manifests: list[PatternPackManifest] = []
        files: list[Path] = []
        diagnostics: list[PatternDiagnostic] = []
        seen_paths: set[Path] = set()
        for root in self.roots:
            root = root.resolve()
            manifest_path = (root / MANIFEST_NAME).resolve()
            if not manifest_path.exists():
                diagnostics.append(_diagnostic("fatal", "missing mandatory pattern manifest", file=str(manifest_path), rule="manifest_required"))
                continue
            try:
                manifest = ManifestValidator().load(manifest_path, root)
                manifests.append(manifest)
                for entry in manifest.files:
                    rel = entry["path"]
                    path = (root / rel).resolve()
                    if path in seen_paths:
                        diagnostics.append(_diagnostic("fatal", "same file declared twice", pack_id=manifest.pack_id, file=str(path), rule="duplicate_source"))
                        continue
                    if not str(path).lower().startswith(str(root).lower()):
                        diagnostics.append(_diagnostic("fatal", "declared file escapes authorized root", pack_id=manifest.pack_id, file=str(path), rule="root_escape"))
                        continue
                    if path.is_symlink() and manifest.symlinks == "reject":
                        diagnostics.append(_diagnostic("fatal", "symlink source rejected", pack_id=manifest.pack_id, file=str(path), rule="symlink_policy"))
                        continue
                    if path.suffix.lower() not in set(manifest.authorized_extensions):
                        diagnostics.append(_diagnostic("fatal", "extension not authorized by manifest", pack_id=manifest.pack_id, file=str(path), rule="extension_policy"))
                        continue
                    if not path.exists():
                        diagnostics.append(_diagnostic("fatal", "declared file missing", pack_id=manifest.pack_id, file=str(path), rule="declared_file_exists"))
                        continue
                    seen_paths.add(path)
                    files.append(path)
            except Exception as exc:
                diagnostics.append(_diagnostic("fatal", str(exc), file=str(manifest_path), rule="manifest_parse"))
        return tuple(manifests), tuple(files), tuple(diagnostics)


class ManifestValidator:
    REQUIRED = (
        "pack_id", "pack_version", "required_schema_version", "domains", "dependencies",
        "priority", "trust_level", "files", "runtime", "required", "discovery",
    )

    def load(self, path: Path, root: Path) -> PatternPackManifest:
        raw = _read_limited(path)
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_no_duplicate_keys)
        _assert_depth(data)
        missing = [key for key in self.REQUIRED if key not in data]
        if missing:
            raise ValueError(f"manifest missing required fields: {', '.join(missing)}")
        if data["required_schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"schema mismatch: {data['required_schema_version']} != {SCHEMA_VERSION}")
        discovery = dict(data["discovery"])
        runtime = dict(data["runtime"])
        files = tuple(dict(item) for item in data["files"])
        if not files:
            raise ValueError("manifest must declare at least one file")
        for entry in files:
            if "path" not in entry or "sha256" not in entry or "format" not in entry:
                raise ValueError("each manifest file requires path, sha256, and format")
            if Path(str(entry["path"])).is_absolute():
                raise ValueError("manifest file paths must be relative")
        return PatternPackManifest(
            pack_id=str(data["pack_id"]),
            pack_version=str(data["pack_version"]),
            required_schema_version=str(data["required_schema_version"]),
            domains=tuple(str(item) for item in data["domains"]),
            dependencies=tuple(str(item) for item in data["dependencies"]),
            priority=int(data["priority"]),
            trust_level=str(data["trust_level"]),
            files=files,
            runtime_min=str(runtime["min"]),
            runtime_max=str(runtime["max"]),
            required=bool(data["required"]),
            recursive=bool(discovery["recursive"]),
            authorized_extensions=tuple(str(item).lower() for item in discovery["authorized_extensions"]),
            symlinks=str(discovery["symlinks"]),
            source_kinds=tuple(str(item) for item in discovery["source_kinds"]),
            manifest_path=str(path),
        )


class FormatDecoder:
    def decode(self, path: Path, fmt: str) -> Any:
        raw = _read_limited(path)
        suffix = path.suffix.lower()
        fmt = fmt.lower()
        if suffix not in AUTHORIZED_EXTENSIONS:
            raise ValueError(f"unauthorized extension: {suffix}")
        text = raw.decode("utf-8")
        if fmt == "json":
            data = json.loads(text, object_pairs_hook=_json_no_duplicate_keys)
        elif fmt == "toml":
            data = tomllib.loads(text)
        elif fmt == "csv":
            data = self._decode_csv(text)
        elif fmt == "markdown":
            data = self._decode_markdown(text)
        elif fmt == "yaml-simple":
            data = self._decode_yaml_simple(text)
        elif fmt == "blob":
            data = self._decode_blob(text)
        else:
            raise ValueError(f"unsupported format: {fmt}")
        _assert_depth(data)
        return data

    def _decode_csv(self, text: str) -> list[dict[str, str]]:
        rows = list(csv.DictReader(text.splitlines(), delimiter=",", quotechar='"'))
        if not rows:
            return []
        if set(rows[0].keys()) != {"category", "phrase"}:
            raise ValueError("CSV requires exactly category,phrase headers")
        return rows

    def _decode_markdown(self, text: str) -> dict[str, list[str]]:
        current = ""
        result: dict[str, list[str]] = {}
        for lineno, raw in enumerate(text.splitlines(), start=1):
            heading = re.match(r"^#+\s+(.+?)\s*$", raw)
            if heading:
                current = heading.group(1)
                result.setdefault(current, [])
                continue
            item = re.match(r"^\s*[-*]\s+(.+?)\s*$", raw)
            if item and current:
                result[current].append(item.group(1))
            elif raw.strip() and not raw.startswith("#"):
                raise ValueError(f"unsupported markdown content at line {lineno}")
        return result

    def _decode_yaml_simple(self, text: str) -> dict[str, list[str]]:
        if re.search(r"(^|\s)[&*!<>{}\\[]", text):
            raise ValueError("YAML simple rejects tags, anchors, aliases, and complex tokens")
        current = ""
        result: dict[str, list[str]] = {}
        for lineno, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(":"):
                current = line[:-1].strip()
                result.setdefault(current, [])
                continue
            if line.startswith("- ") and current:
                result[current].append(line[2:].strip().strip("'\""))
                continue
            raise ValueError(f"unsupported YAML simple content at line {lineno}")
        return result

    def _decode_blob(self, text: str) -> dict[str, list[str]]:
        current = ""
        result: dict[str, list[str]] = {}
        for lineno, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(":"):
                current = line[:-1].strip()
                result.setdefault(current, [])
                continue
            if not current:
                raise ValueError(f"blob requires category header before line {lineno}")
            result[current].append(line)
        return result


class Normalizer:
    def normalize(self, data: Any, *, manifest: PatternPackManifest, path: Path) -> tuple[PatternDefinition, ...]:
        pairs = self._pairs(data)
        definitions: list[PatternDefinition] = []
        for index, (category_raw, value_raw) in enumerate(pairs):
            category = _category(category_raw)
            value = _normalize_space(str(value_raw))
            if not category or not value:
                continue
            name = f"{_slug(value)}_{_hash_bytes(value.encode('utf-8'))[:8]}"
            domain = manifest.domains[0]
            canonical_id = f"{domain}:{category}:{name}:{manifest.pack_version}"
            definitions.append(PatternDefinition(
                canonical_id=canonical_id,
                domain=domain,
                category=category,
                name=name,
                pattern_version=manifest.pack_version,
                value=value,
                aliases=(),
                case_sensitive=False,
                normalization="unicode_nfkc_lower_space",
                deprecated=False,
                state="normalized",
                priority=manifest.priority,
                trust_level=manifest.trust_level,
                pack_id=manifest.pack_id,
                source=PatternSource(
                    pack_id=manifest.pack_id,
                    path=str(path),
                    line=index + 1,
                    original_value=str(value_raw),
                    normalized_value=value,
                    migration="none",
                ),
            ))
            if len(definitions) > MAX_RECORDS:
                raise ValueError(f"pack exceeds {MAX_RECORDS} records")
        return tuple(definitions)

    def _pairs(self, data: Any) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        if isinstance(data, list):
            for row in data:
                pairs.append((str(row.get("category", "")), str(row.get("phrase", ""))))
            return pairs
        if isinstance(data, dict):
            for key, value in data.items():
                if _category(key):
                    if isinstance(value, list):
                        pairs.extend((key, str(item)) for item in value)
                    else:
                        pairs.append((key, str(value)))
                elif isinstance(value, dict):
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, list):
                            pairs.extend((nested_key, str(item)) for item in nested_value)
                        else:
                            pairs.append((nested_key, str(nested_value)))
            return pairs
        raise ValueError("decoded pattern data must be a mapping or CSV rows")


class StructuralValidator:
    def validate(self, definitions: tuple[PatternDefinition, ...]) -> tuple[PatternDiagnostic, ...]:
        diagnostics: list[PatternDiagnostic] = []
        seen: dict[str, PatternDefinition] = {}
        for definition in definitions:
            if definition.category not in CATEGORIES:
                diagnostics.append(_diagnostic("fatal", "unknown category", pattern_id=definition.canonical_id, rule="category_enum"))
            if definition.canonical_id in seen and seen[definition.canonical_id].value != definition.value:
                diagnostics.append(_diagnostic("fatal", "conflicting canonical id", pattern_id=definition.canonical_id, rule="identity_collision"))
            seen[definition.canonical_id] = definition
        return tuple(diagnostics)


class SemanticValidator:
    def validate(self, manifests: tuple[PatternPackManifest, ...]) -> tuple[PatternDiagnostic, ...]:
        diagnostics: list[PatternDiagnostic] = []
        pack_ids = {manifest.pack_id for manifest in manifests}
        for manifest in manifests:
            for dep in manifest.dependencies:
                if dep not in pack_ids:
                    diagnostics.append(_diagnostic("fatal", "missing pack dependency", pack_id=manifest.pack_id, rule="dependency_exists", expected=dep))
            if manifest.runtime_min > RUNTIME_VERSION or manifest.runtime_max < RUNTIME_VERSION:
                diagnostics.append(_diagnostic("fatal", "runtime version incompatible", pack_id=manifest.pack_id, rule="runtime_compatibility"))
        return tuple(diagnostics)


class MigrationEngine:
    version = MIGRATIONS_VERSION

    def migrate(self, definition: PatternDefinition) -> PatternDefinition:
        return definition


class PrecedenceResolver:
    rules = (
        "authority=system",
        "priority=manifest.priority descending",
        "version=pack_version descending",
        "tie_breaker=canonical_id ascending",
        "merge=union_unique_by_category",
    )

    def resolve(self, definitions: tuple[PatternDefinition, ...]) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[PatternDefinition, ...]]]:
        by_id: dict[str, list[PatternDefinition]] = {}
        effective: dict[str, list[str]] = {key: [] for key in CATEGORIES}
        ordered = sorted(definitions, key=lambda item: (-item.priority, item.pattern_version, item.canonical_id))
        for definition in ordered:
            by_id.setdefault(definition.canonical_id, []).append(definition)
            if definition.deprecated:
                continue
            values = effective.setdefault(definition.category, [])
            if definition.value not in values:
                values.append(definition.value)
        return (
            {key: tuple(value) for key, value in effective.items()},
            {key: tuple(value) for key, value in by_id.items()},
        )


class RegistryBuilder:
    def build(self, roots: tuple[Path, ...] | None = None) -> PatternSnapshot:
        diagnostics: list[PatternDiagnostic] = []
        manifests, files, source_diags = SourceResolver(roots).resolve()
        diagnostics.extend(source_diags)
        manifest_by_root = {Path(manifest.manifest_path).resolve().parent: manifest for manifest in manifests}
        manifest_by_file: dict[Path, PatternPackManifest] = {}
        for manifest in manifests:
            root = Path(manifest.manifest_path).resolve().parent
            for entry in manifest.files:
                manifest_by_file[(root / entry["path"]).resolve()] = manifest
        definitions: list[PatternDefinition] = []
        decoder = FormatDecoder()
        normalizer = Normalizer()
        migration = MigrationEngine()
        for path in files:
            manifest = manifest_by_file[path]
            entry = next(item for item in manifest.files if (Path(manifest.manifest_path).resolve().parent / item["path"]).resolve() == path)
            try:
                raw = _read_limited(path)
                actual_hash = _hash_bytes(raw)
                if actual_hash.lower() != str(entry["sha256"]).lower():
                    diagnostics.append(_diagnostic("fatal", "file hash mismatch", pack_id=manifest.pack_id, file=str(path), rule="sha256", received=actual_hash, expected=entry["sha256"]))
                    continue
                decoded = decoder.decode(path, str(entry["format"]))
                definitions.extend(migration.migrate(item) for item in normalizer.normalize(decoded, manifest=manifest, path=path))
            except Exception as exc:
                diagnostics.append(_diagnostic("fatal", str(exc), pack_id=manifest.pack_id, file=str(path), rule="decode_normalize"))
        diagnostics.extend(StructuralValidator().validate(tuple(definitions)))
        diagnostics.extend(SemanticValidator().validate(manifests))
        fatal = [item for item in diagnostics if item.severity == "fatal"]
        if fatal:
            return self._snapshot(manifests, tuple(diagnostics), (), {}, {})
        effective, by_id = PrecedenceResolver().resolve(tuple(definitions))
        active_patterns = tuple(definition.__class__(**{**definition.__dict__, "state": "active"}) for definition in definitions)
        return self._snapshot(manifests, tuple(diagnostics), active_patterns, effective, by_id)

    def _snapshot(
        self,
        manifests: tuple[PatternPackManifest, ...],
        diagnostics: tuple[PatternDiagnostic, ...],
        definitions: tuple[PatternDefinition, ...],
        effective: dict[str, tuple[str, ...]],
        by_id: dict[str, tuple[PatternDefinition, ...]],
    ) -> PatternSnapshot:
        payload = json.dumps({
            "packs": [manifest.pack_id + "@" + manifest.pack_version for manifest in manifests],
            "patterns": [definition.canonical_id + "=" + definition.value for definition in definitions],
            "diagnostics": [diag.to_dict() for diag in diagnostics],
            "schema": SCHEMA_VERSION,
            "loader": LOADER_VERSION,
            "migrations": MIGRATIONS_VERSION,
        }, sort_keys=True, ensure_ascii=True).encode("utf-8")
        global_hash = _hash_bytes(payload)
        return PatternSnapshot(
            snapshot_id=f"patterns-{global_hash[:16]}",
            snapshot_version="1",
            global_hash=global_hash,
            built_at=datetime.now(timezone.utc).isoformat(),
            packs=manifests,
            diagnostics=diagnostics,
            precedence_rules=PrecedenceResolver.rules,
            loader_version=LOADER_VERSION,
            schema_version=SCHEMA_VERSION,
            migrations_version=MIGRATIONS_VERSION,
            patterns=definitions,
            effective=effective or {key: () for key in CATEGORIES},
            definitions_by_id=by_id,
        )


class PatternRegistry:
    def __init__(self, snapshot: PatternSnapshot):
        self.snapshot = snapshot

    def get_by_id(self, canonical_id: str) -> tuple[PatternDefinition, ...]:
        return tuple(self.snapshot.definitions_by_id.get(canonical_id, ()))

    def list_by_domain(self, domain: str) -> tuple[PatternDefinition, ...]:
        return tuple(item for item in self.snapshot.patterns if item.domain == domain)

    def filter_by_state(self, state: str) -> tuple[PatternDefinition, ...]:
        return tuple(item for item in self.snapshot.patterns if item.state == state)

    def effective_category(self, category: str) -> tuple[str, ...]:
        return tuple(self.snapshot.effective.get(category, ()))

    def status(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot.snapshot_id,
            "global_hash": self.snapshot.global_hash,
            "packs": [pack.pack_id for pack in self.snapshot.packs],
            "diagnostics": [diag.to_dict() for diag in self.snapshot.diagnostics],
        }


class ReloadCoordinator:
    _lock = threading.Lock()
    _registry: PatternRegistry | None = None
    _last_failed_snapshot: PatternSnapshot | None = None

    def reload(self, roots: tuple[Path, ...] | None = None) -> PatternRegistry:
        with self._lock:
            candidate = RegistryBuilder().build(roots)
            if any(diag.severity == "fatal" for diag in candidate.diagnostics):
                self._last_failed_snapshot = candidate
                if self._registry is not None:
                    return self._registry
                raise RuntimeError(candidate.diagnostics[0].message)
            self._registry = PatternRegistry(candidate)
            return self._registry

    def registry(self) -> PatternRegistry:
        if self._registry is None:
            return self.reload()
        with self._lock:
            return self._registry

    def last_failure(self) -> PatternSnapshot | None:
        return self._last_failed_snapshot


_COORDINATOR = ReloadCoordinator()


@lru_cache(maxsize=8)
def load_pattern_registry(pattern_dir: str | None = None) -> PatternRegistry:
    if pattern_dir:
        snapshot = RegistryBuilder().build((Path(pattern_dir).resolve(),))
        if any(diag.severity == "fatal" for diag in snapshot.diagnostics):
            raise RuntimeError(snapshot.diagnostics[0].message)
        return PatternRegistry(snapshot)
    roots = None
    return _COORDINATOR.reload(roots)


@lru_cache(maxsize=8)
def load_context_patterns(pattern_dir: str | None = None) -> dict[str, tuple[str, ...]]:
    registry = load_pattern_registry(pattern_dir)
    return {category: registry.effective_category(category) for category in CATEGORIES}

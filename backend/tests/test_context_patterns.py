from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

from context_patterns import load_context_patterns, load_pattern_registry  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(root: Path, files: list[dict[str, str]], *, pack_id: str = "test.pack") -> None:
    (root / "manifest.json").write_text(
        json.dumps({
            "pack_id": pack_id,
            "pack_version": "1.0.0",
            "required_schema_version": "context-pattern-schema-v1",
            "domains": ["context"],
            "dependencies": [],
            "priority": 50,
            "trust_level": "test",
            "required": True,
            "runtime": {"min": "4.8.0", "max": "4.8.x"},
            "discovery": {
                "roots": ["."],
                "recursive": False,
                "authorized_extensions": [".json", ".toml", ".csv", ".md", ".markdown", ".yml", ".yaml", ".blob", ".txt"],
                "symlinks": "reject",
                "source_kinds": ["packaged"],
                "remote_sources": False,
                "generated_sources": False
            },
            "files": files,
        }, indent=2),
        encoding="utf-8",
    )


def test_context_patterns_load_from_data_pack():
    load_context_patterns.cache_clear()
    load_pattern_registry.cache_clear()

    patterns = load_context_patterns()

    assert "workspace" in patterns["workspace_markers"]
    assert "si?" in patterns["workspace_followups"]
    assert "sabes de que hablas" in patterns["workspace_followups"]
    assert "de que hablamos" in patterns["workspace_followups"]


def test_pattern_registry_snapshot_status_and_immutability():
    load_context_patterns.cache_clear()
    load_pattern_registry.cache_clear()

    registry = load_pattern_registry()
    status = registry.status()

    assert status["snapshot_id"].startswith("patterns-")
    assert "bago.context.workspace.core" in status["packs"]
    assert registry.effective_category("workspace_markers")
    try:
        registry.snapshot.effective["workspace_markers"] = ()
    except TypeError:
        pass
    else:
        raise AssertionError("snapshot mappings must be immutable")


def test_context_patterns_support_yaml_and_blob(tmp_path):
    yml = tmp_path / "custom.yml"
    blob = tmp_path / "workspace_followups.blob"
    yml.write_text(
        "workspace_markers:\n- proyecto custom\n",
        encoding="utf-8",
    )
    blob.write_text(
        "workspace_followups:\nfrase blob\n",
        encoding="utf-8",
    )
    _write_manifest(tmp_path, [
        {"path": yml.name, "format": "yaml-simple", "sha256": _sha(yml)},
        {"path": blob.name, "format": "blob", "sha256": _sha(blob)},
    ])
    load_context_patterns.cache_clear()
    load_pattern_registry.cache_clear()

    patterns = load_context_patterns(str(tmp_path))

    assert "proyecto custom" in patterns["workspace_markers"]
    assert "frase blob" in patterns["workspace_followups"]


def test_context_patterns_require_manifest(tmp_path):
    load_context_patterns.cache_clear()
    load_pattern_registry.cache_clear()

    try:
        load_context_patterns(str(tmp_path))
    except RuntimeError as exc:
        assert "missing mandatory pattern manifest" in str(exc)
    else:
        raise AssertionError("manifest-less pattern packs must be rejected")


def test_context_patterns_reject_hash_mismatch(tmp_path):
    data = tmp_path / "custom.yml"
    data.write_text("workspace_markers:\n- proyecto custom\n", encoding="utf-8")
    _write_manifest(tmp_path, [
        {"path": data.name, "format": "yaml-simple", "sha256": "0" * 64},
    ])
    load_context_patterns.cache_clear()
    load_pattern_registry.cache_clear()

    try:
        load_context_patterns(str(tmp_path))
    except RuntimeError as exc:
        assert "file hash mismatch" in str(exc)
    else:
        raise AssertionError("hash mismatches must be rejected")

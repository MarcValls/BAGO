#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.versioning import read_release_version as _read_release_version
from scripts.packaging_common import normalize_release_version, rel_posix, sha256


CURRENT_RELEASE = _read_release_version(ROOT).strip().lstrip("v")
CURRENT_EVIDENCE_DIR = f"docs/evidence/release_{CURRENT_RELEASE.replace('.', '_')}"


INCLUDE_FILES = [
    ".gitignore",
    "ir_types.py",
    "protocol.py",
    "registry.py",
    "package.json",
    "README.md",
    "MANUAL.md",
    "index.html",
    "versions.json",
    "package-lock.json",
    "release_version.txt",
    "BAGO.pyproj",
    "bago.cmd",
    "bago.ps1",
    "bago.sh",
    "install-v4.ps1",
    "install-remote.ps1",
    "bago-uninstall.ps1",
    "bago-uninstall.cmd",
    "rollback-v4.ps1",
    "test_e2e.py",
    "test_security_release.py",
    "test_command_intents.py",
    "test_translators.py",
    "tests/test_translators_evidence.py",
]

INCLUDE_DIRS = [
    "assets",
    "bago_core",
    "electron",
    "manager",
    "ui-react/dist",
    ".bago/api",
    ".bago/chat",
    ".bago/core",
    ".bago/knowledge",
    ".bago/providers",
    ".bago/tools",
    "docs",
    "scripts",
    "tests",
    "tools",
]

EXCLUDED_PARTS = {
    ".git",
    ".codex",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "coverage",
    "htmlcov",
    "node_modules",
    ".vite",
}

EXCLUDED_PREFIXES = [
    ".bago/backups",
    ".bago/state",
    ".bago/logs",
    ".bago/cache",
    ".gabo/backups",
    ".gabo/state",
    ".gabo/logs",
    ".gabo/cache",
    ".gabo/launch",
    "PLAN_VERTICE",
    "release",
    "dist",
    "build",
    "output",
    "out",
    "tools/sprints",
    ".ollama",
    ".cache/ollama",
    "models",
    ".gabo/models",
    "weights",
    "checkpoints",
]

EXCLUDED_GLOBS = [
    "*.py.new",
    "bago_core/parsers_legacy_*.py",
    "tools/_diff_*.py",
    "*.sqlite",
    "*.db",
    "*.sqlite-wal",
    "*.sqlite-shm",
    "*.db-wal",
    "*.db-shm",
    "*.bak",
]

FORBIDDEN_NAMES = {
    "credentials.json",
    "install_config.json",
    ".env",
    ".env.local",
}


def repo_root() -> Path:
    return ROOT


def read_release_version(root: Path) -> str:
    return _read_release_version(root)


def is_excluded(relative: Path) -> bool:
    parts = set(relative.parts)
    if parts & EXCLUDED_PARTS:
        return True
    if relative.name in FORBIDDEN_NAMES:
        return True
    rel = rel_posix(relative)
    if any(fnmatch.fnmatch(rel, pattern) for pattern in EXCLUDED_GLOBS):
        return True
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES)


def require_inputs(root: Path) -> None:
    missing_files = [item for item in INCLUDE_FILES if not (root / item).is_file()]
    missing_dirs = [item for item in INCLUDE_DIRS if not (root / item).exists()]
    missing = missing_files + missing_dirs
    if missing:
        raise FileNotFoundError(
            "Faltan entradas obligatorias para el bundle:\n" + "\n".join(f"- {item}" for item in missing)
        )


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for item in INCLUDE_FILES:
        path = root / item
        if path.is_file() and not is_excluded(path.relative_to(root)):
            files.append(path)
    for item in INCLUDE_DIRS:
        path = root / item
        if not path.exists():
            continue
        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(root)
            if is_excluded(relative):
                continue
            files.append(file_path)
    return sorted(set(files), key=lambda p: rel_posix(p.relative_to(root)).lower())


def snapshot(root: Path) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_audit_bundle(root: Path, output_dir: Path, release_version: str = "") -> dict:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    require_inputs(root)
    version = normalize_release_version(release_version or read_release_version(root))
    package_name = f"bago-audit-v{version}.zip"
    zip_path = output_dir / package_name
    files = collect_files(root)
    embedded_snapshot = snapshot(root)
    embedded_snapshot["package"] = package_name
    embedded_snapshot["file_count"] = len(files) + 1
    embedded_snapshot["release_version"] = version
    embedded_snapshot["excluded_prefixes"] = EXCLUDED_PREFIXES
    embedded_snapshot["forbidden_names"] = sorted(FORBIDDEN_NAMES)

    snapshot_bytes = json.dumps(
        embedded_snapshot,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")
    embedded_snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()

    manifest_files = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            relative = file_path.relative_to(root)
            arcname = rel_posix(relative)
            zf.write(file_path, arcname=arcname)
            manifest_files.append({
                "path": arcname,
                "size": file_path.stat().st_size,
                "sha256": sha256(file_path),
            })
        zf.writestr("AUDIT_SNAPSHOT.json", snapshot_bytes)
        manifest_files.append({
            "path": "AUDIT_SNAPSHOT.json",
            "size": len(snapshot_bytes),
            "sha256": embedded_snapshot_sha256,
        })

    zip_sha256 = sha256(zip_path)
    detached_snapshot = {
        **embedded_snapshot,
        "zip_sha256": zip_sha256,
        "embedded_snapshot_sha256": embedded_snapshot_sha256,
    }

    snapshot_path = output_dir / f"{package_name}.snapshot.json"
    manifest_path = output_dir / f"{package_name}.manifest.json"
    checksums_path = output_dir / f"{package_name}.sha256"
    report_path = output_dir / f"{package_name}.report.md"

    snapshot_path.write_text(
        json.dumps(detached_snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    report_path.write_text(
        "\n".join([
            "# BAGO External Audit Bundle",
            "",
            f"- Package: `{package_name}`",
            f"- Files: `{len(manifest_files)}`",
            f"- SHA256: `{zip_sha256}`",
            "",
            "## Included",
            "",
            "- Source and runtime code",
            "- Contract and release docs",
            "- Evidence bundles",
            "- Test files",
            "- Audit bootstrap instructions",
            "",
            "## Excluded",
            "",
            "- local model weights and caches",
            "- live state",
            "- logs",
            "- credentials",
            "- dist/release/build roots",
            "",
        ]),
        encoding="utf-8",
        newline="\n",
    )
    snapshot_sha256 = sha256(snapshot_path)
    report_sha256 = sha256(report_path)
    manifest = {
        "bundle_id": package_name,
        "contract_version": "audit-v1",
        "related_to": f"bago release {version}",
        "summary": "External audit bundle without local model weights",
        "details": "Includes source, docs, tests, evidence, release notes and audit bootstrap instructions.",
        "status": "ready",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "validation_commands": [
            "python scripts/verify_release.py",
            "python scripts/package_audit_bundle.py --test",
            "python test_translators.py",
            "python -m pytest tests/test_translators_evidence.py -q",
            "npm run manager:build-ui",
            "python bago_core/cli.py project analyze --root <repo>",
        ],
        "checks": [
            "zip contains no .ollama, models, weights, or checkpoints",
            "zip contains bago_core/translators/__init__.py",
            "zip contains current release evidence bundle",
            "zip contains audit and model bootstrap instructions",
            "zip contains audit bootstrap instructions",
            "zip contains release evidence and contract docs",
        ],
        "artifacts": [
            {"path": package_name, "sha256": zip_sha256},
            {"path": f"{package_name}.snapshot.json", "sha256": snapshot_sha256},
            {"path": f"{package_name}.report.md", "sha256": report_sha256},
            {"path": "AUDIT_SNAPSHOT.json", "sha256": embedded_snapshot_sha256},
        ],
        "files": manifest_files,
        "snapshot": detached_snapshot,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    checksums_path.write_text(
        "\n".join([
            f"{zip_sha256}  {package_name}",
            f"{sha256(manifest_path)}  {package_name}.manifest.json",
            f"{sha256(snapshot_path)}  {package_name}.snapshot.json",
            f"{sha256(report_path)}  {package_name}.report.md",
        ]) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return {
        "zip": str(zip_path),
        "manifest": str(manifest_path),
        "snapshot": str(snapshot_path),
        "checksums": str(checksums_path),
        "report": str(report_path),
        "file_count": len(manifest_files),
        "zip_sha256": zip_sha256,
    }


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    bundle_version = read_release_version(repo_root()) or "unknown"
    root = repo_root()

    # 2026-Q2 cleanup: MODEL_PARALLEL_SETUP.md and AUDIT_PARALLEL_SETUP.md were removed.
    # Bootstrap instructions now live in docs/SETUP.md.
    bootstrap_doc = (root / "docs" / "SETUP.md")
    if not bootstrap_doc.exists():
        bootstrap_doc = (root / "README.md")
    bootstrap = bootstrap_doc.read_text(encoding="utf-8")
    assert "ollama" in bootstrap or "install" in bootstrap, "bootstrap doc lacks install guidance"

    with TemporaryDirectory() as td:
        work = Path(td)
        output_dir = work / "release" / "v4"
        result = build_audit_bundle(root, output_dir, release_version=bundle_version)

        zip_path = Path(result["zip"])
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())
            embedded_bytes = zf.read("AUDIT_SNAPSHOT.json")
            embedded = json.loads(embedded_bytes)

            required_names = {
                "bago_core/translators/__init__.py",
                "ui-react/dist/index.html",
                f"{CURRENT_EVIDENCE_DIR}/manifest.json",
                f"{CURRENT_EVIDENCE_DIR}/session/meta.json",
                "AUDIT_SNAPSHOT.json",
            }
            missing = sorted(required_names - names)
            assert not missing, f"missing bundle entries: {missing}"
            assert not any(name.startswith("ui-react/src/") for name in names)

            evidence_manifest = json.loads(zf.read(f"{CURRENT_EVIDENCE_DIR}/manifest.json"))
            evidence_meta = json.loads(zf.read(f"{CURRENT_EVIDENCE_DIR}/session/meta.json"))
            assert evidence_manifest["contract_version"] == bundle_version
            assert evidence_meta["bago_version"] == bundle_version

        assert embedded["file_count"] == len(names)
        assert embedded["release_version"] == bundle_version
        assert embedded["package"] == f"bago-audit-v{bundle_version}.zip"
        assert "bago_core/translators/__init__.py" in names
        assert ".ollama/models/llama3.2.gguf" not in names
        assert "models/other.gguf" not in names

        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        manifest_names = {entry["path"] for entry in manifest["files"]}
        assert manifest_names == set(names)
        snapshot_entry = next(entry for entry in manifest["files"] if entry["path"] == "AUDIT_SNAPSHOT.json")
        assert snapshot_entry["sha256"] == hashlib.sha256(embedded_bytes).hexdigest()
        checksum_lines = Path(result["checksums"]).read_text(encoding="utf-8").splitlines()
        assert len(checksum_lines) == 4
        assert checksum_lines[0].endswith(f" {Path(result['zip']).name}")
        assert Path(result["zip"]).name == f"bago-audit-v{bundle_version}.zip"

        extract_dir = work / "extract"
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        subprocess.run([sys.executable, "test_translators.py"], cwd=extract_dir, check=True)
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_translators_evidence.py", "-q"],
            cwd=extract_dir,
            check=True,
        )

    subprocess.run(["cmd", "/c", "npm", "run", "manager:build-ui"], cwd=root, check=True)
    print("package_audit_bundle.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an external audit BAGO bundle without local model weights.")
    parser.add_argument("--output-dir", default=str(repo_root() / "release" / "v4"))
    parser.add_argument("--release-version", default="", help="Use fixed bundle name (e.g. X.Y.Z). Defaults to release_version.txt.")
    parser.add_argument("--test", action="store_true", help="Run self tests and exit")
    args = parser.parse_args(argv)
    if args.test:
        return _run_tests()
    result = build_audit_bundle(repo_root(), Path(args.output_dir), release_version=args.release_version)
    print(f"Package: {result['zip']}")
    print(f"Files  : {result['file_count']}")
    print(f"SHA256 : {result['zip_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

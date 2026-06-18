#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


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
    "ui-react/package.json",
    "ui-react/package-lock.json",
    "ui-react/index.html",
    "ui-react/vite.config.js",
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
    "MODEL_PARALLEL_SETUP.md",
    "AUDIT_PARALLEL_SETUP.md",
    "test_e2e.py",
    "test_security_release.py",
    "test_command_intents.py",
    "test_translators.py",
    "test_translators_evidence.py",
]

INCLUDE_DIRS = [
    "assets",
    "bago_core",
    "electron",
    "manager",
    "ui-react/src",
    ".bago/core",
    ".bago/chat",
    ".bago/knowledge",
    ".bago/providers",
    ".bago/api",
    ".bago/tools",
    "docs",
    "scripts",
    "tests",
    "tools",
]

EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".vite",
}

EXCLUDED_PREFIXES = [
    ".bago/state",
    ".bago/logs",
    ".bago/launch",
    ".bago/tools/.bago",
    "PLAN_VERTICE",
    "release",
    "dist",
    "build",
    ".ollama",
    ".cache/ollama",
    "models",
    ".bago/models",
    "weights",
    "checkpoints",
]

EXCLUDED_GLOBS = [
    "*.py.new",
    "bago_core/parsers_legacy_*.py",
    "tools/_diff_*.py",
]

FORBIDDEN_NAMES = {
    "credentials.json",
    "install_config.json",
    ".env",
    ".env.local",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def rel_posix(path: Path) -> str:
    return path.as_posix()


def read_release_version(root: Path) -> str:
    release_version_file = root / "release_version.txt"
    if release_version_file.exists():
        value = release_version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    return "4.6.3"


def normalize_release_version(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not normalized:
        raise ValueError("release_version vacío")
    allowed = set("0123456789.-")
    if any(ch not in allowed for ch in normalized):
        raise ValueError(f"release_version inválido: {value}")
    return normalized


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


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, shell=False, timeout=20)
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def snapshot(root: Path) -> dict:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], root) or "(no git)"
    commit = _git(["rev-parse", "--short", "HEAD"], root) or "(no commit)"
    status = _git(["status", "--short"], root)
    dirty = [line for line in status.splitlines() if line.strip()] if status else []
    return {
        "branch": branch,
        "commit": commit,
        "dirty_count": len(dirty),
        "dirty_files": dirty[:200],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_audit_bundle(root: Path, output_dir: Path, release_version: str = "") -> dict:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    version = normalize_release_version(release_version or read_release_version(root))
    package_name = f"bago-audit-v{version}.zip"
    zip_path = output_dir / package_name
    files = collect_files(root)
    audit_snapshot = snapshot(root)
    audit_snapshot["package"] = package_name
    audit_snapshot["file_count"] = len(files)
    audit_snapshot["release_version"] = version
    audit_snapshot["excluded_prefixes"] = EXCLUDED_PREFIXES
    audit_snapshot["forbidden_names"] = sorted(FORBIDDEN_NAMES)

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
        snapshot_bytes = json.dumps(audit_snapshot, indent=2, ensure_ascii=False).encode("utf-8")
        zf.writestr("AUDIT_SNAPSHOT.json", snapshot_bytes)
        manifest_files.append({
            "path": "AUDIT_SNAPSHOT.json",
            "size": len(snapshot_bytes),
            "sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        })

    audit_snapshot["zip_sha256"] = sha256(zip_path)
    audit_snapshot["file_count"] = len(manifest_files)

    snapshot_path = output_dir / f"{package_name}.snapshot.json"
    manifest_path = output_dir / f"{package_name}.manifest.json"
    checksums_path = output_dir / f"{package_name}.sha256"
    report_path = output_dir / f"{package_name}.report.md"

    manifest = {
        "bundle_id": package_name,
        "contract_version": "audit-v1",
        "related_to": f"bago release {version}",
        "summary": "External audit bundle without local model weights",
        "details": "Includes source, docs, tests, evidence, release notes and audit bootstrap instructions.",
        "status": "ready",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "validation_commands": [
            "python scripts/verify_release_463.py",
            "python scripts/package_audit_bundle.py --test",
            "python bago_core/cli.py project analyze --root <repo>",
        ],
        "checks": [
            "zip contains no .ollama, models, weights, or checkpoints",
            "zip contains audit bootstrap instructions",
            "zip contains release evidence and contract docs",
        ],
        "artifacts": [
            {"path": package_name, "sha256": audit_snapshot["zip_sha256"]},
            {"path": f"{package_name}.sha256", "sha256": None},
            {"path": f"{package_name}.manifest.json", "sha256": None},
            {"path": f"{package_name}.snapshot.json", "sha256": None},
            {"path": "AUDIT_SNAPSHOT.json", "sha256": hashlib.sha256(json.dumps(audit_snapshot, indent=2, ensure_ascii=False).encode("utf-8")).hexdigest()},
        ],
        "files": manifest_files,
        "snapshot": audit_snapshot,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    snapshot_path.write_text(json.dumps(audit_snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    checksums_path.write_text(f"{audit_snapshot['zip_sha256']}  {package_name}\n", encoding="utf-8")
    report_path.write_text(
        "\n".join([
            "# BAGO External Audit Bundle",
            "",
            f"- Package: `{package_name}`",
            f"- Files: `{len(manifest_files)}`",
            f"- Branch: `{audit_snapshot['branch']}`",
            f"- Commit: `{audit_snapshot['commit']}`",
            f"- SHA256: `{audit_snapshot['zip_sha256']}`",
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
    )

    return {
        "zip": str(zip_path),
        "manifest": str(manifest_path),
        "snapshot": str(snapshot_path),
        "checksums": str(checksums_path),
        "report": str(report_path),
        "file_count": len(manifest_files),
        "zip_sha256": audit_snapshot["zip_sha256"],
    }


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "bago_core").mkdir()
        (root / "bago_core" / "x.py").write_text("x=1\n", encoding="utf-8")
        (root / "docs" / "evidence" / "sample").mkdir(parents=True)
        (root / "docs" / "evidence" / "sample" / "report.md").write_text("audit\n", encoding="utf-8")
        (root / "AUDIT_PARALLEL_SETUP.md").write_text("bootstrap\n", encoding="utf-8")
        (root / ".ollama" / "models").mkdir(parents=True)
        (root / ".ollama" / "models" / "llama3.2.gguf").write_text("no\n", encoding="utf-8")
        (root / "models").mkdir()
        (root / "models" / "other.gguf").write_text("no\n", encoding="utf-8")
        result = build_audit_bundle(root, root / "release" / "v4", release_version="4.6.3")
        with zipfile.ZipFile(result["zip"], "r") as zf:
            names = set(zf.namelist())
        assert "bago_core/x.py" in names
        assert "docs/evidence/sample/report.md" in names
        assert "AUDIT_PARALLEL_SETUP.md" in names
        assert "AUDIT_SNAPSHOT.json" in names
        assert ".ollama/models/llama3.2.gguf" not in names
        assert "models/other.gguf" not in names
        assert Path(result["zip"]).name == "bago-audit-v4.6.3.zip"
    print("package_audit_bundle.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an external audit BAGO bundle without local model weights.")
    parser.add_argument("--output-dir", default=str(repo_root() / "release" / "v4"))
    parser.add_argument("--release-version", default="", help="Use fixed bundle name (e.g. 4.6.3). Defaults to release_version.txt.")
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

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.versioning import read_release_version
from scripts.packaging_common import normalize_release_version, rel_posix, sha256


CURRENT_RELEASE = read_release_version(ROOT).strip().lstrip("v")
PACKAGE_PROVENANCE_CONTRACT = "bago.package-provenance.v1"
PROVENANCE_PATH = "audit/bago-provenance.json"
INCLUDE_FILES = [
    ".gitignore",
    ".bago/core/context_store.py",
    ".bago/core/session_manager.py",
    ".bago/tools/orchestrator_v4.py",
    ".bago/seed.py",
    ".bago/tools.manifest.json",
    "ir_types.py",
    "protocol.py",
    "registry.py",
    "README.md",
    "manual.md",
    "index.html",
    "versions.json",
    "package-lock.json",
    "package.json",
    "release_version.txt",
    "bago.pyproj",
    "open-ui-bago.cmd",
    "open-electron-bago.cmd",
    "bago.cmd",
    "bago",
    "bago.ps1",
    "bago.sh",
    "install-v4.ps1",
    "install-assistant.ps1",
    "install-remote.ps1",
    "uninstall-bago.ps1",
    "uninstall-bago.cmd",
    "rollback-bago.ps1",
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
    ".bago/api",
    ".bago/chat",
    ".bago/core",
    ".bago/knowledge",
    ".bago/providers",
    ".bago/roles",
    ".bago/tools",
    "docs",
    "scripts",
    "tests",
    "tools",
    "ui-react/dist",
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
    "docs/archive",
    "tools/sprints",
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

ALLOWED_LEGACY_PATHS = {
    ".bago/core/context_store.py",
    ".bago/core/session_manager.py",
    ".bago/tools/orchestrator_v4.py",
    ".bago/seed.py",
    ".bago/tools.manifest.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def candidate_provenance(root: Path) -> dict:
    """Return the Git identity that produced this package without guessing.

    Package generation also supports exported source trees that do not contain
    `.git`; those packages state that their candidate is unavailable instead of
    claiming an arbitrary clean commit.
    """
    def git_text(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    candidate = git_text("rev-parse", "HEAD")
    if not candidate:
        return {
            "contract": PACKAGE_PROVENANCE_CONTRACT,
            "candidate_sha": None,
            "dirty": None,
            "source": "git-unavailable",
        }
    return {
        "contract": PACKAGE_PROVENANCE_CONTRACT,
        "candidate_sha": candidate,
        "dirty": bool(git_text("status", "--porcelain=v1", "--untracked-files=all")),
        "source": "git",
    }


def provenance_bytes(provenance: dict) -> bytes:
    return (json.dumps(provenance, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def provenance_manifest_entry(payload: bytes) -> dict:
    return {
        "path": PROVENANCE_PATH,
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def is_excluded(relative: Path) -> bool:
    rel = rel_posix(relative)
    if rel in ALLOWED_LEGACY_PATHS:
        return False
    parts = set(relative.parts)
    if parts & EXCLUDED_PARTS:
        return True
    if relative.name in FORBIDDEN_NAMES:
        return True
    if any(fnmatch.fnmatch(rel, pattern) for pattern in EXCLUDED_GLOBS):
        return True
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES)


def require_inputs(root: Path) -> None:
    missing_files = [item for item in INCLUDE_FILES if not (root / item).is_file()]
    # Directories are optional (e.g. ui-react/dist requires a UI build step).
    # Only fail for missing required files.
    if missing_files:
        raise FileNotFoundError(
            "Faltan entradas obligatorias para el bundle:\n" + "\n".join(f"- {item}" for item in missing_files)
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


def _manifest_entries(root: Path, files: list[Path]) -> list[dict]:
    entries = []
    for file_path in files:
        relative = file_path.relative_to(root)
        entries.append({
            "path": rel_posix(relative),
            "size": file_path.stat().st_size,
            "sha256": sha256(file_path),
        })
    return entries


def _tree_digest(entries: list[dict]) -> str:
    h = hashlib.sha256()
    for entry in entries:
        h.update(str(entry["path"]).encode("utf-8"))
        h.update(b"\0")
        h.update(str(entry["sha256"]).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def build_install_tree(root: Path, output_dir: Path, release_version: str = "") -> dict:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    require_inputs(root)
    version = normalize_release_version(release_version or read_release_version(root))
    tree_root = output_dir / "current"
    if tree_root.exists():
        shutil.rmtree(tree_root)
    files = collect_files(root)
    manifest_files = _manifest_entries(root, files)
    provenance = candidate_provenance(root)
    provenance_payload = provenance_bytes(provenance)
    manifest_files.append(provenance_manifest_entry(provenance_payload))

    for file_path in files:
        relative = file_path.relative_to(root)
        destination = tree_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, destination)
    provenance_path = tree_root / PROVENANCE_PATH
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_bytes(provenance_payload)

    manifest = {
        "package": "current",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": "<repo>",
        "tree_root": "current",
        "release_version": version,
        "file_count": len(manifest_files),
        "tree_sha256": _tree_digest(manifest_files),
        "provenance": provenance,
        "included_files": manifest_files,
        "excluded_prefixes": EXCLUDED_PREFIXES,
        "forbidden_names": sorted(FORBIDDEN_NAMES),
    }

    manifest_path = output_dir / "current.manifest.json"
    checksums_path = output_dir / "current.sha256"
    report_path = output_dir / "current.report.md"

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    checksums_path.write_text(f"{manifest['tree_sha256']}  current\n", encoding="utf-8")
    report_path.write_text(
        "\n".join([
            "# BAGO v4 Install Tree Report",
            "",
            f"- Tree: `current`",
            f"- Version: `v{version}`",
            f"- Files: `{len(manifest_files)}`",
            f"- SHA256: `{manifest['tree_sha256']}`",
            f"- Candidate: `{provenance['candidate_sha'] or 'unavailable'}`",
            f"- Dirty: `{provenance['dirty']}`",
            "",
            "## Layout",
            "",
            "- Directory payload for the thin wizard.",
            "- The executable only needs to point at this folder.",
            "",
            "## Exclusions",
            "",
            "- live state",
            "- logs",
            "- credentials",
            "- node_modules",
            "- PLAN_VERTICE execution artifacts",
            "- root dist/build folders",
            "",
        ]),
        encoding="utf-8",
    )

    return {
        "tree": str(tree_root),
        "manifest": str(manifest_path),
        "checksums": str(checksums_path),
        "report": str(report_path),
        "file_count": len(manifest_files),
        "tree_sha256": manifest["tree_sha256"],
    }


def build_package(root: Path, output_dir: Path, release_version: str = "") -> dict:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    require_inputs(root)
    version = normalize_release_version(release_version or read_release_version(root))
    tree_result = build_install_tree(root, output_dir, release_version=release_version)
    if release_version:
        package_name = f"bago-v{version}.zip"
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        package_name = f"bago-v4-local-{stamp}.zip"
    zip_path = output_dir / package_name
    files = collect_files(root)
    manifest_files = _manifest_entries(root, files)
    provenance = candidate_provenance(root)
    provenance_payload = provenance_bytes(provenance)
    manifest_files.append(provenance_manifest_entry(provenance_payload))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path, entry in zip(files, manifest_files):
            relative = file_path.relative_to(root)
            arcname = entry["path"]
            zf.write(file_path, arcname=arcname)
        zf.writestr(PROVENANCE_PATH, provenance_payload)

    manifest = {
        "package": package_name,
        "release_version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": "<repo>",
        "file_count": len(manifest_files),
        "zip_sha256": sha256(zip_path),
        "provenance": provenance,
        "included_files": manifest_files,
        "excluded_prefixes": EXCLUDED_PREFIXES,
        "forbidden_names": sorted(FORBIDDEN_NAMES),
    }

    manifest_path = output_dir / f"{package_name}.manifest.json"
    checksums_path = output_dir / f"{package_name}.sha256"
    report_path = output_dir / f"{package_name}.report.md"

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    checksums_path.write_text(f"{manifest['zip_sha256']}  {package_name}\n", encoding="utf-8")
    report_path.write_text(
        "\n".join([
            "# BAGO v4 Local Package Report",
            "",
            f"- Package: `{package_name}`",
            f"- Files: `{len(manifest_files)}`",
            f"- SHA256: `{manifest['zip_sha256']}`",
            f"- Candidate: `{provenance['candidate_sha'] or 'unavailable'}`",
            f"- Dirty: `{provenance['dirty']}`",
            "",
            "## Exclusions",
            "",
            "- live state",
            "- logs",
            "- credentials",
            "- node_modules",
            "- PLAN_VERTICE execution artifacts",
            "- root dist/build folders",
            "",
        ]),
        encoding="utf-8",
    )

    return {
        "zip": str(zip_path),
        "tree": tree_result["tree"],
        "manifest": str(manifest_path),
        "checksums": str(checksums_path),
        "report": str(report_path),
        "file_count": len(manifest_files),
        "zip_sha256": manifest["zip_sha256"],
        "tree_sha256": tree_result["tree_sha256"],
    }


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    bundle_version = read_release_version(repo_root()) or "unknown"
    root = repo_root()
    with TemporaryDirectory() as td:
        output_dir = Path(td) / "release" / "v4"
        result = build_package(root, output_dir, release_version=bundle_version)
        tree_root = Path(result["tree"])
        assert tree_root.exists()
        assert (tree_root / "install-v4.ps1").exists()
        assert (tree_root / "install-assistant.ps1").exists()
        assert (tree_root / "bago_core" / "launcher.py").exists()
        tree_manifest = json.loads((output_dir / "current.manifest.json").read_text(encoding="utf-8"))
        assert tree_manifest["release_version"] == bundle_version
        assert tree_manifest["tree_sha256"] == result["tree_sha256"]
        with zipfile.ZipFile(result["zip"], "r") as zf:
            names = set(zf.namelist())
            required_names = {
                "bago_core/translators/__init__.py",
                "install-assistant.ps1",
                ".bago/core/session_manager.py",
                ".bago/chat/commands.py",
                ".bago/api/bridge.py",
                ".bago/providers/ollama_local.py",
                ".bago/tools/orchestrator_v4.py",
                ".bago/tools/tool_registry.py",
                "docs/contracts/bago_v4_runtime_contract.json",
                "docs/contracts/bago_v4_repl_contract.md",
                "docs/contracts/bago_v4_evidence_contract.md",
                "docs/contracts/bago_v4_knowledge_contract.md",
                "docs/contracts/bago_v4_governance_contract.md",
                "docs/contracts/bago_v4_engineering_contract.md",
                "ui-react/dist/index.html",
            }
            missing = sorted(required_names - names)
            assert not missing, f"missing bundle entries: {missing}"
            assert ".gabo/state/context.json" not in names
            assert not any(name.startswith("ui-react/src/") for name in names)
            leaked = sorted(
                name for name in names
                if name.startswith(("release/", "dist/", "build/", "node_modules/"))
                or "release/v4/current" in name
                or name.startswith("tools/sprints/")
                or "win-unpacked/resources" in name
            )
            assert not leaked, f"recursive/build artifacts leaked into package: {leaked[:5]}"
            assert not any(name.startswith("docs/archive/") for name in names)
        zip_manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        assert zip_manifest["release_version"] == bundle_version
        extract_dir = Path(td) / "extract"
        with zipfile.ZipFile(result["zip"], "r") as zf:
            zf.extractall(extract_dir)
        subprocess.run([sys.executable, "test_translators.py"], cwd=extract_dir, check=True)
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_translators_evidence.py", "-q"],
            cwd=extract_dir,
            check=True,
        )
        assert Path(result["zip"]).name == f"bago-v{bundle_version}.zip"
    print("package_v4.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build clean BAGO v4 local package.")
    parser.add_argument("--output-dir", default=str(repo_root() / "release" / "v4"))
    parser.add_argument("--release-version", default="", help="Use fixed release bundle name (e.g. X.Y.Z).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = build_package(repo_root(), Path(args.output_dir), release_version=args.release_version)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Package: {result['zip']}")
        print(f"Files  : {result['file_count']}")
        print(f"SHA256 : {result['zip_sha256']}")
        print(f"Report : {result['report']}")
    return 0


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(main())

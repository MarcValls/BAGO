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
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.versioning import read_release_version as _read_release_version


INCLUDE_FILES = [
    ".gitignore",
    "ir_types.py",
    "protocol.py",
    "registry.py",
    "README.md",
    "MANUAL.md",
    "index.html",
    "versions.json",
    "package-lock.json",
    "package.json",
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
    ".bago/core",
    ".bago/chat",
    ".bago/knowledge",
    ".bago/providers",
    ".bago/api",
    ".bago/tools",
    "docs",
    "tools",
    "ui-react/dist",
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
    return ROOT


def rel_posix(path: Path) -> str:
    return path.as_posix()


def read_release_version(root: Path) -> str:
    return _read_release_version(root)


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


def build_user_bundle(root: Path, output_dir: Path, release_version: str = "") -> dict:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    require_inputs(root)
    version = normalize_release_version(release_version or read_release_version(root))
    package_name = f"bago-user-v{version}.zip"
    zip_path = output_dir / package_name
    files = collect_files(root)

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

    manifest = {
        "package": package_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": "<repo>",
        "file_count": len(manifest_files),
        "zip_sha256": sha256(zip_path),
        "included_files": manifest_files,
        "excluded_prefixes": EXCLUDED_PREFIXES,
        "forbidden_names": sorted(FORBIDDEN_NAMES),
        "bootstrap_instructions": "MODEL_PARALLEL_SETUP.md",
    }

    manifest_path = output_dir / f"{package_name}.manifest.json"
    checksums_path = output_dir / f"{package_name}.sha256"
    report_path = output_dir / f"{package_name}.report.md"

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    checksums_path.write_text(f"{manifest['zip_sha256']}  {package_name}\n", encoding="utf-8")
    report_path.write_text(
        "\n".join([
            "# BAGO User Bundle Report",
            "",
            f"- Package: `{package_name}`",
            f"- Files: `{len(manifest_files)}`",
            f"- SHA256: `{manifest['zip_sha256']}`",
            "",
            "## Bootstrap",
            "",
            "- Local model weights are intentionally excluded.",
            "- See `MODEL_PARALLEL_SETUP.md` for the parallel local-model setup.",
            "",
            "## Exclusions",
            "",
            "- live state",
            "- logs",
            "- credentials",
            "- node_modules",
            "- local model caches and weights",
            "- root dist/build/release folders",
            "",
        ]),
        encoding="utf-8",
    )

    return {
        "zip": str(zip_path),
        "manifest": str(manifest_path),
        "checksums": str(checksums_path),
        "report": str(report_path),
        "file_count": len(manifest_files),
        "zip_sha256": manifest["zip_sha256"],
    }


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    bundle_version = read_release_version(repo_root()) or "unknown"
    root = repo_root()
    with TemporaryDirectory() as td:
        output_dir = Path(td) / "release" / "v4"
        result = build_user_bundle(root, output_dir, release_version=bundle_version)
        with zipfile.ZipFile(result["zip"], "r") as zf:
            names = set(zf.namelist())
            required_names = {
                "bago_core/translators/__init__.py",
                "MODEL_PARALLEL_SETUP.md",
                "ui-react/dist/index.html",
                "docs/evidence/release_4_6_4/manifest.json",
                "docs/evidence/release_4_6_4/session/meta.json",
            }
            missing = sorted(required_names - names)
            assert not missing, f"missing bundle entries: {missing}"
            assert any(name.startswith("ui-react/dist/") for name in names)
            evidence_manifest = json.loads(zf.read("docs/evidence/release_4_6_4/manifest.json"))
            evidence_meta = json.loads(zf.read("docs/evidence/release_4_6_4/session/meta.json"))
            assert evidence_manifest["contract_version"] == bundle_version
            assert evidence_meta["bago_version"] == bundle_version
        extract_dir = Path(td) / "extract"
        with zipfile.ZipFile(result["zip"], "r") as zf:
            zf.extractall(extract_dir)
        subprocess.run([sys.executable, "test_translators.py"], cwd=extract_dir, check=True)
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_translators_evidence.py", "-q"],
            cwd=extract_dir,
            check=True,
        )
        assert Path(result["zip"]).name == f"bago-user-v{bundle_version}.zip"
    print("package_user_bundle.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a user-facing BAGO bundle without local model weights.")
    parser.add_argument("--output-dir", default=str(repo_root() / "dist" / "user-bundle"))
    parser.add_argument("--release-version", default="", help="Use fixed bundle name (e.g. X.Y.Z). Defaults to release_version.txt.")
    parser.add_argument("--test", action="store_true", help="Run self tests and exit")
    args = parser.parse_args(argv)
    if args.test:
        return _run_tests()
    result = build_user_bundle(repo_root(), Path(args.output_dir), release_version=args.release_version)
    print(f"Package: {result['zip']}")
    print(f"Files  : {result['file_count']}")
    print(f"SHA256 : {result['zip_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

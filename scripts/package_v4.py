#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


INCLUDE_FILES = [
    ".gitignore",
    "README.md",
    "MANUAL.md",
    "index.html",
    "package.json",
    "versions.json",
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
    "scripts",
    "tests",
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


def validate_release_identity(root: Path, requested_version: str) -> str:
    expected = normalize_release_version(requested_version)
    release_version = normalize_release_version((root / "release_version.txt").read_text(encoding="utf-8"))
    versions_current = normalize_release_version(
        json.loads((root / "versions.json").read_text(encoding="utf-8"))["current"]
    )
    package_version = normalize_release_version(
        json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
    )
    tag_path = root / "bago_core" / "tags" / f"v{expected}.json"
    tag_version = ""
    if tag_path.is_file():
        tag_version = normalize_release_version(
            json.loads(tag_path.read_text(encoding="utf-8"))["version"]
        )
    observed = {
        "release_version.txt": release_version,
        "versions.json": versions_current,
        "package.json": package_version,
        str(tag_path.relative_to(root)): tag_version or "missing",
    }
    drift = {name: value for name, value in observed.items() if value != expected}
    if drift:
        details = ", ".join(f"{name}={value}" for name, value in drift.items())
        raise ValueError(f"release identity drift: expected={expected}; {details}")
    return expected


def verify_archive_identity(zip_path: Path, expected_version: str) -> None:
    expected = normalize_release_version(expected_version)
    with zipfile.ZipFile(zip_path, "r") as zf:
        release_version = normalize_release_version(zf.read("release_version.txt").decode("utf-8"))
        versions_current = normalize_release_version(json.loads(zf.read("versions.json"))["current"])
        package_version = normalize_release_version(json.loads(zf.read("package.json"))["version"])
        tag_version = normalize_release_version(
            json.loads(zf.read(f"bago_core/tags/v{expected}.json"))["version"]
        )
    if len({expected, release_version, versions_current, package_version, tag_version}) != 1:
        raise ValueError(
            "archive release identity drift: "
            f"expected={expected}, release={release_version}, versions={versions_current}, "
            f"package={package_version}, tag={tag_version}"
        )


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


def build_package(root: Path, output_dir: Path, release_version: str = "") -> dict:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if release_version:
        release_version = validate_release_identity(root, release_version)
        package_name = f"bago-v{release_version}.zip"
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        package_name = f"bago-v4-local-{stamp}.zip"
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

    if release_version:
        verify_archive_identity(zip_path, release_version)

    manifest = {
        "package": package_name,
        "release_version": release_version or "local",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": ".",
        "file_count": len(manifest_files),
        "zip_sha256": sha256(zip_path),
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
        "manifest": str(manifest_path),
        "checksums": str(checksums_path),
        "report": str(report_path),
        "file_count": len(manifest_files),
        "zip_sha256": manifest["zip_sha256"],
    }


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "bago_core").mkdir()
        (root / "bago_core" / "x.py").write_text("x=1\n", encoding="utf-8")
        (root / "bago_core" / "parsers_legacy_123.py").write_text("no\n", encoding="utf-8")
        (root / "tools").mkdir()
        (root / "tools" / "_diff_parsers.py").write_text("no\n", encoding="utf-8")
        (root / ".bago" / "core").mkdir(parents=True)
        (root / ".bago" / "core" / "safe.py").write_text("ok\n", encoding="utf-8")
        (root / ".bago" / "tools" / ".bago").mkdir(parents=True)
        (root / ".bago" / "tools" / ".bago" / "config.json").write_text("no\n", encoding="utf-8")
        (root / ".bago" / "state").mkdir(parents=True)
        (root / ".bago" / "state" / "secret.txt").write_text("no\n", encoding="utf-8")
        (root / "ui-react" / "dist").mkdir(parents=True)
        (root / "ui-react" / "dist" / "index.html").write_text("ui\n", encoding="utf-8")
        (root / "PLAN_VERTICE").mkdir()
        (root / "PLAN_VERTICE" / "events.jsonl").write_text("no\n", encoding="utf-8")
        (root / "release_version.txt").write_text("4.5.0\n", encoding="utf-8")
        (root / "versions.json").write_text(json.dumps({"current": "4.5.0"}), encoding="utf-8")
        (root / "package.json").write_text(json.dumps({"version": "4.5.0"}), encoding="utf-8")
        (root / "bago_core" / "tags").mkdir()
        (root / "bago_core" / "tags" / "v4.5.0.json").write_text(
            json.dumps({"version": "4.5.0"}), encoding="utf-8"
        )
        result = build_package(root, root / "release" / "v4")
        with zipfile.ZipFile(result["zip"], "r") as zf:
            names = "\n".join(zf.namelist())
        assert "bago_core/x.py" in names
        assert "bago_core/parsers_legacy_123.py" not in names
        assert "tools/_diff_parsers.py" not in names
        assert ".bago/core/safe.py" in names
        assert "ui-react/dist/index.html" in names
        assert ".bago/state" not in names
        assert ".bago/tools/.bago" not in names
        assert "PLAN_VERTICE" not in names
        fixed = build_package(root, root / "release" / "v4", release_version="v4.5.0")
        assert Path(fixed["zip"]).name == "bago-v4.5.0.zip"
        (root / "release_version.txt").write_text("4.5.1\n", encoding="utf-8")
        try:
            build_package(root, root / "release" / "v4", release_version="v4.5.0")
        except ValueError as exc:
            assert "release identity drift" in str(exc)
        else:
            raise AssertionError("release identity drift was not rejected")
    print("package_v4.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build clean BAGO v4 local package.")
    parser.add_argument("--output-dir", default=str(repo_root() / "release" / "v4"))
    parser.add_argument("--release-version", default="", help="Release version; defaults to release_version.txt.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root()
    release_version = args.release_version or (root / "release_version.txt").read_text(encoding="utf-8").strip()
    result = build_package(root, Path(args.output_dir), release_version=release_version)
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

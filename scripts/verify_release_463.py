#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_release_463.py
Gate de verificación pre-publicación para BAGO v4.6.3.

Comprueba que el EXE, el ZIP oficial, el manifiesto y el checksum del bundle
son coherentes entre sí. También valida que el ZIP incluya package-lock.json,
porque el instalador lo usa en sus tests de drift.

Retorna 0 si todo está bien, 1 si hay discrepancias (bloqueante).
"""
from __future__ import annotations

import base64
import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL_DIR = ROOT / "release" / "v4"
DIST_DIR = ROOT / "dist"
DEFAULT_ASSETS_DIR = Path(
    os.environ.get("BAGO_RELEASE_ASSETS", ROOT.parent / "bago-release-v4.6.3")
).resolve()

VERSION = "4.6.3"
EXE_NAME = f"BAGO-Installation-Manager-{VERSION}-win-x64.exe"
ZIP_NAME = f"bago-v{VERSION}.zip"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha512_file_b64(p: Path) -> str:
    h = hashlib.sha512()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def _read_sha256_file(p: Path) -> str:
    return p.read_text(encoding="utf-8").split()[0].lower()


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"[OK]   {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _read_latest_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def _resolve_path(value: str | None, default: Path) -> Path:
    if value:
        return Path(value)
    return default


def run_checks(
    *,
    exe_path: Path | None = None,
    zip_path: Path | None = None,
    manifest_path: Path | None = None,
    zip_sha256_path: Path | None = None,
    latest_yml_path: Path | None = None,
) -> int:
    errors = 0

    exe_dist = exe_path or (DEFAULT_ASSETS_DIR / EXE_NAME)
    zip_path = zip_path or (DEFAULT_ASSETS_DIR / ZIP_NAME)
    zip_sha256_file = zip_sha256_path or (DEFAULT_ASSETS_DIR / f"{ZIP_NAME}.sha256")
    manifest_path = manifest_path or (DEFAULT_ASSETS_DIR / f"{ZIP_NAME}.manifest.json")
    dist_latest = latest_yml_path or (DEFAULT_ASSETS_DIR / "latest.yml")

    print(f"\n=== BAGO {VERSION} release gate ===\n")

    if not exe_dist.exists():
        _fail(f"EXE no encontrado: {exe_dist}")
        errors += 1
    else:
        _ok(f"EXE encontrado ({exe_dist.stat().st_size:,} bytes)")
    if not dist_latest.exists():
        _fail(f"dist/latest.yml no encontrado: {dist_latest}")
        errors += 1
    elif exe_dist.exists():
        latest = _read_latest_yaml(dist_latest)
        if latest.get("version") == VERSION:
            _ok(f"dist/latest.yml version == {VERSION}")
        else:
            _fail(f"dist/latest.yml version mismatch: {latest.get('version')} != {VERSION}")
            errors += 1
        if latest.get("path") == EXE_NAME:
            _ok("dist/latest.yml apunta al EXE correcto")
        else:
            _fail(f"dist/latest.yml path mismatch: {latest.get('path')} != {EXE_NAME}")
            errors += 1
        if latest.get("size"):
            yml_size = int(latest["size"])
            actual_size = exe_dist.stat().st_size
            if yml_size == actual_size:
                _ok(f"dist/latest.yml size coincide: {yml_size:,}")
            else:
                _fail(f"dist/latest.yml size mismatch: yml={yml_size:,} actual={actual_size:,}")
                errors += 1
        else:
            _fail("dist/latest.yml size ausente")
            errors += 1
        if latest.get("sha512"):
            actual_sha512 = _sha512_file_b64(exe_dist)
            if actual_sha512 == latest["sha512"]:
                _ok("dist/latest.yml sha512 coincide con el EXE")
            else:
                _fail("dist/latest.yml sha512 NO coincide con el EXE")
                errors += 1
        else:
            _fail("dist/latest.yml sha512 ausente")
            errors += 1

    if not zip_path.exists():
        _fail(f"ZIP no encontrado: {zip_path}")
        errors += 1
    else:
        _ok(f"ZIP encontrado ({zip_path.stat().st_size:,} bytes)")
        if zip_sha256_file.exists():
            actual_zip_sha256 = _sha256_file(zip_path)
            expected_zip_sha256 = _read_sha256_file(zip_sha256_file)
            if actual_zip_sha256 == expected_zip_sha256:
                _ok(f"ZIP SHA256 coincide: {actual_zip_sha256[:16]}...")
            else:
                _fail(f"ZIP SHA256 mismatch:\n  actual:   {actual_zip_sha256}\n  expected: {expected_zip_sha256}")
                errors += 1
        else:
            _fail(f".sha256 no encontrado: {zip_sha256_file}")
            errors += 1

    if not manifest_path.exists():
        _fail(f"manifest no encontrado: {manifest_path}")
        errors += 1
    elif zip_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with zipfile.ZipFile(zip_path, "r") as zf:
            zip_names = set(zf.namelist())
        manifest_names = {e["path"] for e in manifest.get("included_files", [])}
        missing_in_zip = manifest_names - zip_names
        extra_in_zip = zip_names - manifest_names
        if not missing_in_zip and not extra_in_zip:
            _ok(f"Manifest cubre {len(manifest_names)} archivos; ZIP contiene exactamente los mismos")
        else:
            if missing_in_zip:
                _fail(f"Archivos en manifest pero NO en ZIP: {sorted(missing_in_zip)[:5]}")
                errors += 1
            if extra_in_zip:
                _fail(f"Archivos en ZIP pero NO en manifest: {sorted(extra_in_zip)[:5]}")
                errors += 1
        if "package-lock.json" in zip_names:
            _ok("package-lock.json incluido en el ZIP")
        else:
            _fail("package-lock.json no está incluido en el ZIP")
            errors += 1

    print()
    if errors == 0:
        print(f"=== GATE PASS: BAGO {VERSION} release listo para distribución ===")
        return 0
    print(f"=== GATE FAIL: {errors} error(s) encontrados — corregir antes de publicar ===")
    return 1


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        dist = root / "dist"
        rel = root / "release" / "v4"
        dist.mkdir(parents=True)
        rel.mkdir(parents=True)
        exe = dist / EXE_NAME
        exe.write_bytes(b"exe")
        zip_path = rel / ZIP_NAME
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("package-lock.json", "{}")
        sha_path = rel / f"{ZIP_NAME}.sha256"
        sha_path.write_text(f"{_sha256_file(zip_path)}  {ZIP_NAME}\n", encoding="utf-8")
        manifest_path = rel / f"{ZIP_NAME}.manifest.json"
        manifest_path.write_text(json.dumps({"included_files": [{"path": "package-lock.json"}]}), encoding="utf-8")
        latest = dist / "latest.yml"
        latest.write_text(
            "\n".join([
                f"version: {VERSION}",
                "path: " + EXE_NAME,
                f"size: {exe.stat().st_size}",
                "sha512: " + _sha512_file_b64(exe),
            ]),
            encoding="utf-8",
        )
        result = run_checks(
            exe_path=exe,
            zip_path=zip_path,
            manifest_path=manifest_path,
            zip_sha256_path=sha_path,
            latest_yml_path=latest,
        )
        assert result == 0
    print("verify_release_463.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a release gate for BAGO v4.6.3.")
    parser.add_argument("--exe-path", default="", help="Path to the Windows installer EXE")
    parser.add_argument("--zip-path", default="", help="Path to the official release ZIP")
    parser.add_argument("--manifest-path", default="", help="Path to the ZIP manifest JSON")
    parser.add_argument("--zip-sha256-path", default="", help="Path to the ZIP SHA256 sidecar")
    parser.add_argument("--latest-yml-path", default="", help="Path to dist/latest.yml metadata")
    parser.add_argument("--test", action="store_true", help="Run self tests and exit")
    args = parser.parse_args(argv)
    if args.test:
        return _run_tests()
    if not any([args.exe_path, args.zip_path, args.manifest_path, args.zip_sha256_path, args.latest_yml_path]) and not DEFAULT_ASSETS_DIR.exists():
        _fail(
            "Directorio de artefactos no encontrado. Define BAGO_RELEASE_ASSETS "
            f"o crea: {DEFAULT_ASSETS_DIR}"
        )
        return 2
    return run_checks(
        exe_path=_resolve_path(args.exe_path, DEFAULT_ASSETS_DIR / EXE_NAME),
        zip_path=_resolve_path(args.zip_path, DEFAULT_ASSETS_DIR / ZIP_NAME),
        manifest_path=_resolve_path(args.manifest_path, DEFAULT_ASSETS_DIR / f"{ZIP_NAME}.manifest.json"),
        zip_sha256_path=_resolve_path(args.zip_sha256_path, DEFAULT_ASSETS_DIR / f"{ZIP_NAME}.sha256"),
        latest_yml_path=_resolve_path(args.latest_yml_path, DEFAULT_ASSETS_DIR / "latest.yml"),
    )


if __name__ == "__main__":
    raise SystemExit(main())

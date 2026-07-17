#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import shutil
import subprocess
import sys
import shutil as _shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FALLBACK_STAGING_ROOT = Path(tempfile.gettempdir()) / "BAGO" / "installer"
ARTIFACTS_OUT = ROOT / "dist" / "installer"
ALLOWED_REMOVE_ROOTS = {ROOT.resolve(), Path(tempfile.gettempdir()).resolve()}


def _safe_remove(path: Path) -> None:
    resolved = path.resolve()
    if not any(allowed in resolved.parents or resolved == allowed for allowed in ALLOWED_REMOVE_ROOTS):
        raise RuntimeError(f"Refusing to remove outside workspace: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _make_staging_root() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return FALLBACK_STAGING_ROOT / stamp


def _run(args: list[str]) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def _exe(name: str) -> str:
    resolved = _shutil.which(name)
    if resolved:
        return resolved
    if not name.endswith(".cmd"):
        resolved = _shutil.which(f"{name}.cmd")
        if resolved:
            return resolved
    return name


def main() -> int:
    staging_root = _make_staging_root()
    _safe_remove(staging_root)
    RELEASE_OUT = staging_root / "release" / "v4"
    DIST_OUT = staging_root / "dist"
    RELEASE_OUT.mkdir(parents=True, exist_ok=True)
    DIST_OUT.mkdir(parents=True, exist_ok=True)

    ui_dist = ROOT / "ui-react" / "dist" / "index.html"
    try:
        subprocess.run([_exe("npm"), "run", "manager:build-ui"], cwd=ROOT, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError:
        if not ui_dist.exists():
            raise
        print("UI build failed, reusing existing ui-react/dist")
    _run([
        sys.executable,
        "scripts/package_v4.py",
        "--output-dir",
        str(RELEASE_OUT),
        "--json",
    ])
    _run([
        _exe("npx"),
        "electron-builder",
        "--win",
        "nsis",
        "--config.directories.output=" + str(DIST_OUT),
    ])

    ARTIFACTS_OUT.mkdir(parents=True, exist_ok=True)
    for item in DIST_OUT.iterdir():
        target = ARTIFACTS_OUT / item.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    print(f"Staging root: {staging_root}")
    print(f"Release tree: {RELEASE_OUT}")
    print(f"Installer out: {DIST_OUT}")
    print(f"Artifacts out: {ARTIFACTS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

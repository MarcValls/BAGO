"""tests/test_packaging.py — Packaging smoke tests for BAGO CI.

Verifies that the ZIP produced by build_pack.py meets basic requirements.
Requires the pack to be built before running:
    python3 .bago/tools/build_pack.py --out dist/ --clean
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"


def _latest_zip() -> Path | None:
    zips = sorted(DIST_DIR.glob("bago-v*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


@pytest.fixture(scope="module")
def pack_zip():
    z = _latest_zip()
    if z is None:
        pytest.skip("No bago-v*.zip in dist/ — run build_pack.py first")
    return z


def test_zip_exists(pack_zip):
    assert pack_zip.exists()
    assert pack_zip.stat().st_size > 0


def test_zip_manifest_exists(pack_zip):
    manifest = Path(str(pack_zip) + ".manifest.json")
    assert manifest.exists(), f"Manifest not found: {manifest}"


def test_zip_manifest_version_matches_release(pack_zip):
    manifest = json.loads(Path(str(pack_zip) + ".manifest.json").read_text(encoding="utf-8"))
    rv = (REPO_ROOT / "release_version.txt").read_text(encoding="utf-8").strip()
    manifest_version = manifest.get("version") or manifest.get("release_version")
    assert manifest_version == rv, (
        f"Manifest version {manifest_version!r} != release_version.txt {rv!r}"
    )


def test_zip_sha256_file_exists(pack_zip):
    sha_file = Path(str(pack_zip) + ".sha256")
    assert sha_file.exists(), f"SHA256 file not found: {sha_file}"


def test_zip_contains_release_version_txt(pack_zip):
    with zipfile.ZipFile(pack_zip) as zf:
        names = zf.namelist()
    assert "release_version.txt" in names, "release_version.txt missing from ZIP"


def test_zip_contains_bago_core(pack_zip):
    with zipfile.ZipFile(pack_zip) as zf:
        names = zf.namelist()
    core_files = [n for n in names if n.startswith("bago_core/")]
    assert len(core_files) > 0, "bago_core/ missing from ZIP"


def test_electron_builder_does_not_embed_current_release_tree():
    package_json = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    resources = package_json.get("build", {}).get("extraResources", [])
    forbidden = []
    for item in resources:
        if isinstance(item, dict):
            from_value = str(item.get("from", "")).replace("\\", "/").strip("/")
            to_value = str(item.get("to", "")).replace("\\", "/").strip("/")
            if from_value == "release/v4/current" or to_value == "release/v4/current":
                forbidden.append(item)
        elif str(item).replace("\\", "/").strip("/") == "release/v4/current":
            forbidden.append(item)
    assert not forbidden, f"Recursive extraResources entries: {forbidden}"


def test_zip_excludes_recursive_release_and_build_outputs(pack_zip):
    with zipfile.ZipFile(pack_zip) as zf:
        names = zf.namelist()
    leaked = [
        name for name in names
        if name.startswith(("release/", "dist/", "build/", "node_modules/"))
        or "release/v4/current" in name
        or "win-unpacked/resources" in name
    ]
    assert not leaked, f"Recursive/build artifacts in ZIP: {leaked[:5]}"


def test_zip_excludes_state(pack_zip):
    with zipfile.ZipFile(pack_zip) as zf:
        names = zf.namelist()
    # Exclude .bago/state/ (live runtime state) but allow .bago/state.example/ (template)
    state_files = [n for n in names if "/.bago/state/" in ("/" + n) or n.startswith(".bago/state/")]
    assert len(state_files) == 0, f"Live state files in ZIP: {state_files[:3]}"


def test_zip_excludes_bago_backups(pack_zip):
    with zipfile.ZipFile(pack_zip) as zf:
        names = zf.namelist()
    leaked = [n for n in names if n.startswith(".bago/backups/") or "/.bago/backups/" in ("/" + n)]
    assert len(leaked) == 0, f"Backups leaked into ZIP: {leaked[:3]}"


def test_zip_excludes_common_generated_junk(pack_zip):
    with zipfile.ZipFile(pack_zip) as zf:
        names = zf.namelist()
    leaked = [
        n for n in names
        if n.startswith((
            ".codex/",
            ".idea/",
            ".vscode/",
            ".mypy_cache/",
            ".ruff_cache/",
            ".cache/",
            "coverage/",
            "htmlcov/",
            "output/",
            "out/",
        ))
        or "/.gabo/backups/" in ("/" + n)
        or "/.gabo/cache/" in ("/" + n)
        or "/.gabo/logs/" in ("/" + n)
    ]
    assert len(leaked) == 0, f"Generated junk leaked into ZIP: {leaked[:5]}"


def test_zip_excludes_credentials(pack_zip):
    import re
    with zipfile.ZipFile(pack_zip) as zf:
        for name in zf.namelist():
            if name.endswith((".py", ".json", ".md", ".txt")):
                try:
                    content = zf.read(name).decode("utf-8", errors="ignore")
                    assert not re.search(r"sk-[A-Za-z0-9]{32,}", content), (
                        f"Possible API key in ZIP/{name}"
                    )
                except Exception:
                    pass

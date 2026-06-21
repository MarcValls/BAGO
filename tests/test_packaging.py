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
    assert manifest["version"] == rv, (
        f"Manifest version {manifest['version']!r} != release_version.txt {rv!r}"
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


def test_zip_excludes_state(pack_zip):
    with zipfile.ZipFile(pack_zip) as zf:
        names = zf.namelist()
    state_files = [n for n in names if ".bago/state" in n]
    assert len(state_files) == 0, f"State files in ZIP: {state_files[:3]}"


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

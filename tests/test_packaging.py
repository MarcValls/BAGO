"""test_packaging.py — PR-08 gate: pack builder contract.

Rules (from PR-05):
- Pack does not include .bago/dist entries
- Pack does not include .bago/state/sessions entries
- Pack is extractable to a temp directory
- Required top-level files are present in the pack

NOTE: Building a pack from USB storage is slow (~3-5min).
  - By default, uses an existing dist/*.zip if one is present.
  - Set env BAGO_FORCE_BUILD=1 to always build fresh.
  - In CI, packs are built in gate-package before tests run.
"""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parent.parent
BUILD_PACK  = REPO_ROOT / ".bago" / "tools" / "build_pack.py"
VALIDATE_PACK = REPO_ROOT / ".bago" / "tools" / "validate_pack_contents.py"
DIST_DIR    = REPO_ROOT / "dist"


def _find_or_build_pack(tmp_path_factory) -> Path:
    """Return a zip pack for testing.

    Uses an existing dist/*.zip if available (and BAGO_FORCE_BUILD is not set).
    Otherwise builds a fresh one (slow on USB — allow up to 5 min).
    """
    force_build = os.environ.get("BAGO_FORCE_BUILD", "").strip() == "1"

    if not force_build and DIST_DIR.exists():
        existing = sorted(DIST_DIR.glob("*.zip"))
        if existing:
            return existing[-1]  # most recent

    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, str(BUILD_PACK), "--out", str(out), "--clean"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        timeout=600,  # USB can be slow — allow 10 min
    )
    assert result.returncode == 0, \
        f"build_pack.py failed:\n{result.stdout}\n{result.stderr}"
    zips = list(out.glob("*.zip"))
    assert zips, "build_pack.py produced no zip file"
    return zips[0]


@pytest.fixture(scope="module")
def built_pack(tmp_path_factory) -> Path:
    """Provide a zip pack for all packaging tests."""
    return _find_or_build_pack(tmp_path_factory)


def test_pack_builds_successfully(built_pack):
    """Smoke: a zip pack exists and is non-empty."""
    assert built_pack.exists()
    assert built_pack.stat().st_size > 0


def test_pack_no_dist_inside(built_pack):
    """The pack must not contain .bago/dist entries (recursive pollution)."""
    with zipfile.ZipFile(built_pack) as zf:
        bad = [n for n in zf.namelist() if ".bago/dist" in n or "/.bago/dist" in n]
    assert not bad, f"Pack contains .bago/dist entries: {bad[:5]}"


def test_pack_no_runtime_state(built_pack):
    """The pack must not contain .bago/state/sessions (user runtime data)."""
    with zipfile.ZipFile(built_pack) as zf:
        bad = [n for n in zf.namelist() if ".bago/state/sessions" in n]
    assert not bad, f"Pack contains runtime session data: {bad[:5]}"


def test_pack_no_git(built_pack):
    """The pack must not contain .git/ entries."""
    with zipfile.ZipFile(built_pack) as zf:
        bad = [n for n in zf.namelist() if "/.git/" in n or n.startswith(".git/")]
    assert not bad, f"Pack contains .git entries: {bad[:5]}"


def test_pack_has_required_files(built_pack):
    """Pack must include the launcher, README, and pyproject.toml."""
    with zipfile.ZipFile(built_pack) as zf:
        names = set(zf.namelist())
    required_suffixes = ["bago", "README.md", "pyproject.toml"]
    for req in required_suffixes:
        found = any(n.endswith(req) or n.endswith("/" + req) for n in names)
        assert found, f"Required file '{req}' not found in pack"


def test_pack_is_extractable(built_pack, tmp_path):
    """The zip must be fully extractable without errors."""
    with zipfile.ZipFile(built_pack) as zf:
        zf.extractall(tmp_path)
    extracted = list(tmp_path.rglob("*"))
    assert len(extracted) > 5, "Extracted pack contains almost nothing"


def test_validate_pack_passes(built_pack):
    """validate_pack_contents.py must exit 0 on the pack."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_PACK), str(built_pack)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    assert result.returncode == 0, \
        f"validate_pack_contents.py failed:\n{result.stdout}\n{result.stderr}"



def test_pack_builds_successfully(built_pack):
    """Smoke: build_pack.py produces a zip file."""
    assert built_pack.exists()
    assert built_pack.stat().st_size > 0


def test_pack_no_dist_inside(built_pack):
    """The pack must not contain .bago/dist entries (recursive pollution)."""
    with zipfile.ZipFile(built_pack) as zf:
        bad = [n for n in zf.namelist() if ".bago/dist" in n or "/.bago/dist" in n]
    assert not bad, f"Pack contains .bago/dist entries: {bad[:5]}"


def test_pack_no_runtime_state(built_pack):
    """The pack must not contain .bago/state/sessions (user runtime data)."""
    with zipfile.ZipFile(built_pack) as zf:
        bad = [n for n in zf.namelist() if ".bago/state/sessions" in n]
    assert not bad, f"Pack contains runtime session data: {bad[:5]}"


def test_pack_no_git(built_pack):
    """The pack must not contain .git/ entries."""
    with zipfile.ZipFile(built_pack) as zf:
        bad = [n for n in zf.namelist() if "/.git/" in n or n.startswith(".git/")]
    assert not bad, f"Pack contains .git entries: {bad[:5]}"


def test_pack_has_required_files(built_pack):
    """Pack must include the launcher, README, and pyproject.toml."""
    with zipfile.ZipFile(built_pack) as zf:
        names = set(zf.namelist())
    required_suffixes = ["bago", "README.md", "pyproject.toml"]
    for req in required_suffixes:
        found = any(n.endswith(req) or n.endswith("/" + req) for n in names)
        assert found, f"Required file '{req}' not found in pack"


def test_pack_is_extractable(built_pack, tmp_path):
    """The zip must be fully extractable without errors."""
    with zipfile.ZipFile(built_pack) as zf:
        zf.extractall(tmp_path)
    extracted = list(tmp_path.rglob("*"))
    assert len(extracted) > 5, "Extracted pack contains almost nothing"


def test_validate_pack_passes(built_pack):
    """validate_pack_contents.py must exit 0 on the built pack."""
    result = subprocess.run(
        [sys.executable, str(VALIDATE_PACK), str(built_pack)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    assert result.returncode == 0, \
        f"validate_pack_contents.py failed:\n{result.stdout}\n{result.stderr}"

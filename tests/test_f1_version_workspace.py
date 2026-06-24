"""test_f1_version_workspace.py — Regression tests for F1: version/workspace unification.

Covers:
- bago_core.__version__ is not hardcoded to 4.7.0
- SessionDB schema has workspace_root column
- SessionManager.save() persists workspace_root in session JSON
- SessionManager.load() restores workspace_root when it exists
- No '4.7.0' fallbacks remain in ui-react/src/**/*.{js,jsx}
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"
if str(_BAGO_CORE) not in sys.path:
    sys.path.insert(0, str(_BAGO_CORE))


# ── 1. bago_core.__version__ is dynamic ──────────────────────────────

def test_bago_core_version_not_hardcoded_47():
    """bago_core.__init__.py must not contain a hardcoded 4.7.0 string."""
    init_file = REPO_ROOT / "bago_core" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    assert "4.7.0" not in content, (
        "bago_core/__init__.py still has hardcoded 4.7.0 — must use versioning.current()"
    )


def test_bago_core_version_matches_release():
    """bago_core.__version__ must equal release_version.txt."""
    from bago_core.versioning import current
    rv = (REPO_ROOT / "release_version.txt").read_text(encoding="utf-8").strip()
    assert current() == rv, f"versioning.current()={current()!r} != release_version.txt={rv!r}"


# ── 2. SessionDB has workspace_root column ───────────────────────────

def test_session_db_schema_has_workspace_root():
    """SessionDB schema must include workspace_root column."""
    schema_file = REPO_ROOT / ".bago" / "core" / "session_db.py"
    content = schema_file.read_text(encoding="utf-8")
    assert "workspace_root" in content, (
        "session_db.py must reference workspace_root in schema and upsert"
    )


def test_session_db_upsert_accepts_workspace_root():
    """SessionDB.upsert() must accept workspace_root as a field."""
    from session_db import SessionDB
    with tempfile.TemporaryDirectory() as td:
        db = SessionDB(td)
        db.upsert("test-sid", last_provider="ollama-local", workspace_root="/tmp/fake-ws")
        row = db.get("test-sid")
        assert row is not None
        assert row["workspace_root"] == "/tmp/fake-ws"


# ── 3. SessionManager persists workspace_root ───────────────────────

def test_session_manager_save_persists_workspace_root():
    """SessionManager.save() must include workspace_root in session JSON."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f1-save",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.save()
            session_path = Path(td) / "sessions" / "test-f1-save.json"
            data = json.loads(session_path.read_text(encoding="utf-8"))
            assert data.get("workspace_root") == ws, (
                f"workspace_root in JSON = {data.get('workspace_root')!r}, expected {ws!r}"
            )
        finally:
            mgr.close()


def test_session_manager_load_restores_workspace_root():
    """SessionManager.load() must restore workspace_root when the path exists."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f1-load",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.save()
        finally:
            mgr.close()

        # Load from a different CWD — should restore workspace_root, not use cwd
        other_cwd = tempfile.mkdtemp()
        os.chdir(other_cwd)
        try:
            loaded = SessionManager.load("test-f1-load", state_root=td)
            try:
                assert str(loaded.base_path) == ws, (
                    f"loaded.base_path = {loaded.base_path!r}, expected {ws!r}"
                )
            finally:
                loaded.close()
        finally:
            os.chdir(ws)  # restore


# ── 4. No 4.7.0 fallbacks in UI React ───────────────────────────────

def test_no_47_fallbacks_in_ui_react():
    """ui-react/src/**/*.{js,jsx} must not contain '4.7.0' fallbacks."""
    ui_dir = REPO_ROOT / "ui-react" / "src"
    if not ui_dir.exists():
        pytest.skip("ui-react/src not found")
    offenders = []
    for f in ui_dir.rglob("*"):
        if f.suffix not in (".js", ".jsx"):
            continue
        content = f.read_text(encoding="utf-8", errors="replace")
        if "4.7.0" in content:
            offenders.append(str(f.relative_to(REPO_ROOT)))
    assert not offenders, (
        f"Files still contain '4.7.0': {offenders}"
    )


def test_no_47_fallbacks_in_legacy_manager():
    """manager/js/legacy-manager.js must not contain '4.7' version strings."""
    legacy = REPO_ROOT / "manager" / "js" / "legacy-manager.js"
    if not legacy.exists():
        pytest.skip("legacy-manager.js not found")
    content = legacy.read_text(encoding="utf-8")
    # Look for version:"4.7" or '4.7' patterns (not 4.7.2 path references)
    matches = re.findall(r'version["\']?\s*[:=]\s*["\']4\.7[^.]', content)
    assert not matches, f"legacy-manager.js still has version 4.7 references: {matches}"
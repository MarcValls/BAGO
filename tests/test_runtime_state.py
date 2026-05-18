"""test_runtime_state.py — PR-08 gate: runtime.py resolver contract.

Rules (from PR-06):
- get_root() returns a directory containing .bago/
- get_state_dir() returns <root>/.bago/state by default
- BAGO_STATE_DIR env var overrides the state directory
- BAGO_ROOT env var overrides the repo root
- state_path(*parts) joins correctly against state dir
- ensure_state_dir() creates required subdirectories
- init_state_from_example() populates state from template when empty
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from runtime import get_root, get_state_dir, state_path, ensure_state_dir, init_state_from_example

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_get_root_finds_bago_dir():
    """get_root() must return a directory that contains .bago/."""
    root = get_root()
    assert (root / ".bago").is_dir(), f"get_root() returned {root!r} which has no .bago/"


def test_get_root_env_override(monkeypatch, tmp_path):
    """BAGO_ROOT env var overrides auto-detection."""
    # Create a fake root with .bago/ so it's technically valid
    fake_root = tmp_path / "fake_bago"
    (fake_root / ".bago").mkdir(parents=True)
    monkeypatch.setenv("BAGO_ROOT", str(fake_root))
    assert get_root() == fake_root


def test_get_state_dir_default(monkeypatch):
    """Default state dir is <root>/.bago/state."""
    # Explicitly unset BAGO_STATE_DIR to test the true default
    # (test_findings_engine.py sets this env var at module level for isolation)
    monkeypatch.delenv("BAGO_STATE_DIR", raising=False)
    root = get_root()
    expected = root / ".bago" / "state"
    assert get_state_dir() == expected


def test_get_state_dir_env_override(monkeypatch, tmp_path):
    """BAGO_STATE_DIR env var overrides the default."""
    custom = tmp_path / "my_state"
    monkeypatch.setenv("BAGO_STATE_DIR", str(custom))
    assert get_state_dir() == custom


def test_state_path_joins_correctly():
    """state_path() must join parts relative to state_dir."""
    result = state_path("global_state.json")
    assert result == get_state_dir() / "global_state.json"

    result2 = state_path("sessions", "foo")
    assert result2 == get_state_dir() / "sessions" / "foo"


def test_ensure_state_dir_creates_subdirs(monkeypatch, tmp_path):
    """ensure_state_dir() creates sessions/, changes/, evidences/ under state dir."""
    monkeypatch.setenv("BAGO_STATE_DIR", str(tmp_path / "state"))
    state = ensure_state_dir()
    for sub in ("sessions", "changes", "evidences"):
        assert (state / sub).is_dir(), f"ensure_state_dir() did not create {sub}/"


def test_init_state_from_example_copies_template(monkeypatch, tmp_path):
    """init_state_from_example() populates state/ from state.example/ when empty."""
    # Point state dir to an empty tmp dir
    state_dir = tmp_path / "state"
    monkeypatch.setenv("BAGO_STATE_DIR", str(state_dir))
    # Point root to real repo (so state.example/ exists)
    monkeypatch.setenv("BAGO_ROOT", str(REPO_ROOT))

    copied = init_state_from_example()
    assert copied is True, "init_state_from_example() should return True for fresh install"
    assert (state_dir / "global_state.json").exists(), \
        "global_state.json not copied from state.example/"


def test_init_state_skips_if_already_initialized(monkeypatch, tmp_path):
    """init_state_from_example() returns False if global_state.json already exists."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "global_state.json").write_text("{}")
    monkeypatch.setenv("BAGO_STATE_DIR", str(state_dir))
    monkeypatch.setenv("BAGO_ROOT", str(REPO_ROOT))

    result = init_state_from_example()
    assert result is False, "Should skip init when state already exists"

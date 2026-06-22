#!/usr/bin/env python3
"""Robust regression tests for `bago init` seeding."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

BAGO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BAGO_ROOT / "bago_core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))

from bago_core.commands.cmd_init import cmd_init, _resolve_source, DOT_BAGO_SEED_DIRS, OPTIONAL_SEED_DIRS


class Argv:
    """Minimal argparse Namespace for cmd_init."""

    def __init__(
        self,
        target: str,
        dry_run: bool = False,
        force: bool = False,
        with_knowledge: bool = False,
    ) -> None:
        self.target = target
        self.dry_run = dry_run
        self.force = force
        self.with_knowledge = with_knowledge


def _run_init(project_root: Path, **kwargs) -> None:
    cmd_init(Argv(str(project_root), **kwargs))


@pytest.fixture
def workspace() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="bago-init-test-"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_source_resolution_finds_dot_bago() -> None:
    source = _resolve_source()
    assert source.exists()
    assert (source / "AGENT_START.md").exists()
    assert (source / "BOOTSTRAP.md").exists()


def test_init_creates_canonical_seed(workspace: Path) -> None:
    _run_init(workspace)
    bago_dir = workspace / ".bago"

    assert bago_dir.is_dir()
    for name in DOT_BAGO_SEED_DIRS:
        assert (bago_dir / name).exists(), f"missing seed: {name}"

    assert (bago_dir / "state").is_dir()
    assert (bago_dir / "state" / "sessions").is_dir()
    assert (bago_dir / "logs").is_dir()


def test_init_skips_runtime_artifacts(workspace: Path) -> None:
    _run_init(workspace)
    bago_dir = workspace / ".bago"

    assert not list(bago_dir.rglob("__pycache__"))
    assert not list(bago_dir.rglob("*.pyc"))
    assert not list(bago_dir.rglob("*.pyo"))
    assert not list(bago_dir.rglob("*.db"))
    assert not (bago_dir / "state" / "credentials.json").exists()
    assert not (bago_dir / "config.json").exists()
    assert not (bago_dir / "session-credentials.json").exists()


def test_init_does_not_overwrite_by_default(workspace: Path) -> None:
    _run_init(workspace)
    (workspace / ".bago" / "BOOTSTRAP.md").write_text("custom", encoding="utf-8")

    _run_init(workspace)
    assert (workspace / ".bago" / "BOOTSTRAP.md").read_text(encoding="utf-8") == "custom"


def test_init_force_overwrites(workspace: Path) -> None:
    _run_init(workspace)
    (workspace / ".bago" / "BOOTSTRAP.md").write_text("custom", encoding="utf-8")

    _run_init(workspace, force=True)
    assert "custom" not in (workspace / ".bago" / "BOOTSTRAP.md").read_text(encoding="utf-8")


def test_init_dry_run_does_not_write(workspace: Path) -> None:
    _run_init(workspace, dry_run=True)
    assert not (workspace / ".bago").exists()


def test_init_with_knowledge(workspace: Path) -> None:
    _run_init(workspace, with_knowledge=True)
    bago_dir = workspace / ".bago"

    for name in OPTIONAL_SEED_DIRS:
        assert (bago_dir / name).exists(), f"missing optional seed: {name}"


def test_init_state_from_example(workspace: Path) -> None:
    source = _resolve_source()
    has_example = (source / "state.example").exists()

    _run_init(workspace)
    bago_dir = workspace / ".bago"

    if has_example:
        assert (bago_dir / "state").is_dir()
        assert (bago_dir / "state" / "sessions").is_dir()
    else:
        assert (bago_dir / "state" / "sessions").is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

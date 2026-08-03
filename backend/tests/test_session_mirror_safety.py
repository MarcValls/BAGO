from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


session_manager = importlib.import_module("session_manager")


def test_workspace_size_prunes_excluded_directories(tmp_path, monkeypatch):
    project = tmp_path / "project"
    source = project / "src"
    excluded = project / "node_modules" / "nested"
    source.mkdir(parents=True)
    excluded.mkdir(parents=True)
    (source / "app.py").write_bytes(b"123")
    (excluded / "dependency.bin").write_bytes(b"x" * 1024)

    real_walk = os.walk
    visited: list[Path] = []

    def tracked_walk(*args, **kwargs):
        for item in real_walk(*args, **kwargs):
            visited.append(Path(item[0]))
            yield item

    monkeypatch.setattr(session_manager.os, "walk", tracked_walk)

    assert session_manager.SessionManager._workspace_size_bytes(project) == 3
    assert not any("node_modules" in path.parts for path in visited)


def test_validate_project_root_rejects_home_and_drive_root():
    with pytest.raises(RuntimeError, match="perfil completo"):
        session_manager.SessionManager._validate_project_root(Path.home())

    home = Path.home().resolve()
    drive_root = Path(home.anchor)
    with pytest.raises(RuntimeError, match="raíz completa"):
        session_manager.SessionManager._validate_project_root(drive_root)


def test_validate_project_root_requires_a_marker(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(RuntimeError, match="No se ha detectado"):
        session_manager.SessionManager._validate_project_root(
            project,
            require_identity=True,
        )

    (project / ".gabo").mkdir()
    assert session_manager.SessionManager._validate_project_root(
        project,
        require_identity=True,
    ) == project.resolve()


def test_validate_project_root_rejects_protected_system_paths(tmp_path, monkeypatch):
    protected_root = tmp_path / "Windows"
    protected_root.mkdir()
    system32 = protected_root / "System32"
    system32.mkdir()

    monkeypatch.setattr(session_manager, "SYSTEM_ROOT", protected_root)
    monkeypatch.setattr(session_manager, "PROGRAM_FILES_ROOT", tmp_path / "Program Files")
    monkeypatch.setattr(session_manager, "PROGRAM_FILES_X86_ROOT", tmp_path / "Program Files (x86)")

    with pytest.raises(RuntimeError, match="ruta protegida"):
        session_manager.SessionManager._validate_project_root(system32)


def test_prepare_session_mirror_stops_at_size_limit(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "large.bin").write_bytes(b"12345")

    manager = object.__new__(session_manager.SessionManager)
    manager.session_id = "mirror-limit-test"
    session_root = tmp_path / "sessions" / manager.session_id

    monkeypatch.setenv("BAGO_SESSION_MIRROR", "1")
    monkeypatch.setattr(session_manager, "MAX_MIRROR_BYTES", 4)
    monkeypatch.setattr(
        session_manager.SessionManager,
        "_mirror_session_root",
        staticmethod(lambda _session_id: session_root),
    )

    result = manager._prepare_session_mirror(project)

    assert result["ok"] is False
    assert "workspace too large" in result["error"]
    assert result["required_bytes"] == 10
    assert not session_root.exists()


def test_prepare_session_mirror_can_be_disabled(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    manager = object.__new__(session_manager.SessionManager)
    manager.session_id = "mirror-disabled-test"

    monkeypatch.setenv("BAGO_SESSION_MIRROR", "0")
    result = manager._prepare_session_mirror(project)

    assert result["ok"] is False
    assert result["mirror_root"] == project
    assert "disabled" in result["error"]

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
    manager.project_root = project.resolve()
    session_root = tmp_path / "BAGO" / "sessions" / manager.session_id

    monkeypatch.setenv("BAGO_SESSION_MIRROR", "1")
    monkeypatch.setattr(session_manager, "MAX_MIRROR_BYTES", 4)
    monkeypatch.setattr(session_manager.tempfile, "gettempdir", lambda: str(tmp_path))
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


def test_prepare_session_mirror_materializes_via_gateway_adapter(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('mirror')", encoding="utf-8")
    manager = object.__new__(session_manager.SessionManager)
    manager.session_id = "mirror-gateway-test"
    manager.project_root = project.resolve()
    session_root = tmp_path / "BAGO" / "sessions" / manager.session_id

    monkeypatch.setenv("BAGO_SESSION_MIRROR", "1")
    monkeypatch.setattr(session_manager.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        session_manager.SessionManager,
        "_mirror_session_root",
        staticmethod(lambda _session_id: session_root),
    )

    result = manager._prepare_session_mirror(project)

    assert result["ok"] is True
    assert result["mirror_root"] == session_root / "workspace"
    assert (result["mirror_root"] / "main.py").read_text(encoding="utf-8") == "print('mirror')"
    assert result["effect_id"] == "workspace.mirror.prepare"
    assert result["receipt_id"].startswith("workspace-mirror:mirror-gateway-test:")


def test_prepare_session_mirror_blocks_changed_project_before_copy(tmp_path, monkeypatch):
    project = tmp_path / "requested-project"
    active_project = tmp_path / "active-project"
    project.mkdir()
    active_project.mkdir()
    manager = object.__new__(session_manager.SessionManager)
    manager.session_id = "mirror-mismatch-test"
    manager.project_root = active_project.resolve()
    session_root = tmp_path / "BAGO" / "sessions" / manager.session_id
    calls: list[str] = []

    def unexpected_copy(*_args, **_kwargs):
        calls.append("copy")
        raise AssertionError("copy must be blocked before the material effect")

    monkeypatch.setenv("BAGO_SESSION_MIRROR", "1")
    monkeypatch.setattr(session_manager.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(session_manager.shutil, "copytree", unexpected_copy)
    monkeypatch.setattr(
        session_manager.SessionManager,
        "_mirror_session_root",
        staticmethod(lambda _session_id: session_root),
    )

    result = manager._prepare_session_mirror(project)

    assert result["ok"] is False
    assert "workspace_mirror_project_mismatch" in result["error"]
    assert calls == []
    assert not session_root.exists()


def test_prepare_session_mirror_blocks_noncanonical_destination_before_delete(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    manager = object.__new__(session_manager.SessionManager)
    manager.session_id = "mirror-target-test"
    manager.project_root = project.resolve()
    outside_root = tmp_path / "BAGO" / "outside" / manager.session_id
    calls: list[str] = []

    def unexpected_delete(*_args, **_kwargs):
        calls.append("delete")
        raise AssertionError("delete must be blocked before the material effect")

    monkeypatch.setenv("BAGO_SESSION_MIRROR", "1")
    monkeypatch.setattr(session_manager.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(session_manager.shutil, "rmtree", unexpected_delete)
    monkeypatch.setattr(
        session_manager.SessionManager,
        "_mirror_session_root",
        staticmethod(lambda _session_id: outside_root),
    )

    result = manager._prepare_session_mirror(project)

    assert result["ok"] is False
    assert "workspace_mirror_target_out_of_scope" in result["error"]
    assert calls == []
    assert not outside_root.exists()


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

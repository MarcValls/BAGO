from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from api_state import resolve_state_root as resolve_api_state_root
from bago_core.user_state_paths import (
    STATE_ROOT_ENV,
    USER_ROOT_ENV,
    backup_prune_candidates,
    backups_root,
    cache_root,
    ensure_user_roots,
    legacy_user_root,
    runtime_root,
    state_root,
    user_root,
)
from state_paths import resolve_state_root


def test_state_root_precedence_without_eager_creation(monkeypatch, tmp_path: Path) -> None:
    user = tmp_path / "user"
    environment_state = tmp_path / "environment-state"
    explicit_state = tmp_path / "explicit-state"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.setenv(STATE_ROOT_ENV, str(environment_state))

    assert state_root() == environment_state.resolve()
    assert resolve_state_root() == environment_state.resolve()
    assert not environment_state.exists()
    assert resolve_state_root(explicit_state) == explicit_state.resolve()
    assert not explicit_state.exists()


def test_user_root_supplies_state_when_state_override_is_absent(
    monkeypatch, tmp_path: Path
) -> None:
    user = tmp_path / "user"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)

    expected = user.resolve() / "state"
    assert state_root() == expected
    assert resolve_state_root() == expected
    assert not expected.exists()


def test_default_and_legacy_user_roots_are_distinct(
    monkeypatch, tmp_path: Path
) -> None:
    local_app_data = tmp_path / "local-app-data"
    home = tmp_path / "home"
    monkeypatch.delenv(USER_ROOT_ENV, raising=False)
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert user_root() == local_app_data.resolve() / "BAGO"
    assert state_root() == local_app_data.resolve() / "BAGO" / "state"
    assert legacy_user_root() == home / ".bago"


def test_ensure_user_roots_materializes_only_canonical_roots(monkeypatch, tmp_path: Path) -> None:
    user = tmp_path / "BAGO"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)

    ensure_user_roots()

    assert user.is_dir()
    assert runtime_root().is_dir()
    assert state_root().is_dir()
    assert cache_root().is_dir()
    assert backups_root().is_dir()


def test_ensure_user_roots_honors_explicit_state_root(monkeypatch, tmp_path: Path) -> None:
    user = tmp_path / "BAGO"
    explicit_state = tmp_path / "external-state"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.setenv(STATE_ROOT_ENV, str(explicit_state))

    ensure_user_roots()

    assert state_root() == explicit_state.resolve()
    assert explicit_state.is_dir()
    assert (user / "runtime").is_dir()


def test_directory_gateway_blocks_noncanonical_target_before_creation(monkeypatch, tmp_path: Path) -> None:
    from bago_core.server_effects import ensure_user_directory

    user = tmp_path / "BAGO"
    outside = tmp_path / "unapproved-directory"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)

    with pytest.raises(Exception) as blocked:
        ensure_user_directory(outside, trusted_root=user)

    assert getattr(blocked.value, "code", "") == "server_state_directory_invalid"
    assert not outside.exists()


def test_startup_never_deletes_backup_prune_candidates(monkeypatch, tmp_path: Path) -> None:
    user = tmp_path / "BAGO"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    monkeypatch.setenv("BAGO_BACKUP_KEEP_COUNT", "0")
    monkeypatch.setenv("BAGO_BACKUP_KEEP_DAYS", "0")
    monkeypatch.setenv("BAGO_BACKUP_MAX_FILE_GB", "0")

    ensure_user_roots()
    backup = backups_root() / "old.zip"
    sidecar = backup.with_name("old.zip.sha256")
    backup.write_bytes(b"old backup")
    sidecar.write_text("digest", encoding="utf-8")

    assert set(backup_prune_candidates()) == {backup, sidecar}
    ensure_user_roots()
    assert backup.read_bytes() == b"old backup"
    assert sidecar.read_text(encoding="utf-8") == "digest"


def test_api_keeps_session_precedence(monkeypatch, tmp_path: Path) -> None:
    manager_state = tmp_path / "manager-state"
    context_state = tmp_path / "context-state"
    context = ModuleType("session_context")
    context.current_state_root = lambda: context_state  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "session_context", context)

    handler = SimpleNamespace(session_mgr=SimpleNamespace(state_root=manager_state))
    assert resolve_api_state_root(handler) == manager_state


def test_api_fallback_uses_canonical_environment_contract(
    monkeypatch, tmp_path: Path
) -> None:
    environment_state = tmp_path / "api-state"
    context = ModuleType("session_context")

    def unavailable_context() -> Path:
        raise RuntimeError("no active session context")

    context.current_state_root = unavailable_context  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "session_context", context)
    monkeypatch.setenv(STATE_ROOT_ENV, str(environment_state))
    monkeypatch.setenv(USER_ROOT_ENV, str(tmp_path / "ignored-user-root"))

    assert (
        resolve_api_state_root(SimpleNamespace(session_mgr=None))
        == environment_state.resolve()
    )
    assert not environment_state.exists()

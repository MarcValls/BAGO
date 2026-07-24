from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from api_state import resolve_state_root as resolve_api_state_root
from bago_core.user_state_paths import (
    STATE_ROOT_ENV,
    USER_ROOT_ENV,
    legacy_user_root,
    state_root,
    user_root,
)
from state_paths import resolve_state_root


def test_state_root_precedence_and_creation(monkeypatch, tmp_path: Path) -> None:
    user = tmp_path / "user"
    environment_state = tmp_path / "environment-state"
    explicit_state = tmp_path / "explicit-state"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.setenv(STATE_ROOT_ENV, str(environment_state))

    assert state_root() == environment_state.resolve()
    assert resolve_state_root() == environment_state.resolve()
    assert environment_state.is_dir()
    assert resolve_state_root(explicit_state) == explicit_state.resolve()
    assert explicit_state.is_dir()


def test_user_root_supplies_state_when_state_override_is_absent(
    monkeypatch, tmp_path: Path
) -> None:
    user = tmp_path / "user"
    monkeypatch.setenv(USER_ROOT_ENV, str(user))
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)

    expected = user.resolve() / "state"
    assert state_root() == expected
    assert resolve_state_root() == expected
    assert expected.is_dir()


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

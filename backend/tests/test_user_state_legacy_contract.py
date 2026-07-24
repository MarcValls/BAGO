from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

from bago_core.user_state_paths import (
    STATE_ROOT_ENV,
    USER_ROOT_ENV,
    logs_root,
    secrets_root,
    state_read_roots,
    state_root,
)


def _isolate_user_roots(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    local = tmp_path / "local"
    canonical_user = local / "BAGO"
    home.mkdir()
    local.mkdir()
    monkeypatch.delenv(USER_ROOT_ENV, raising=False)
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home, canonical_user, canonical_user / "state"


def test_canonical_mutable_roots_and_override_isolation(monkeypatch, tmp_path: Path) -> None:
    home, canonical_user, canonical_state = _isolate_user_roots(monkeypatch, tmp_path)

    assert state_root() == canonical_state
    assert logs_root() == canonical_user / "logs"
    assert secrets_root() == canonical_user / "secrets"
    assert state_read_roots() == (canonical_state, home / ".bago" / "state")

    isolated = tmp_path / "isolated-state"
    monkeypatch.setenv(STATE_ROOT_ENV, str(isolated))
    assert state_read_roots() == (isolated.resolve(),)


def test_legacy_config_readers_do_not_migrate_on_read(monkeypatch, tmp_path: Path) -> None:
    home, _, canonical_state = _isolate_user_roots(monkeypatch, tmp_path)
    legacy_config = home / ".bago" / "state" / "config.json"
    legacy_config.parent.mkdir(parents=True)
    legacy_config.write_text(
        json.dumps({"legacy_marker": "visible", "providers": {"ollama-local": {"enabled": True}}}),
        encoding="utf-8",
    )

    providers = importlib.import_module("handlers_providers")
    vision = importlib.import_module("handlers_vision")
    auto = importlib.import_module("auto_configurator")
    config_manager = importlib.import_module("config_manager")

    assert providers._load_config()["legacy_marker"] == "visible"
    assert vision._load_config()["legacy_marker"] == "visible"
    assert auto._read_state_json("config.json")["legacy_marker"] == "visible"
    manager = config_manager.ConfigManager(base_path=str(tmp_path / "project"))
    assert manager.get("legacy_marker") == "visible"
    assert manager.config_source_path == legacy_config
    assert not (canonical_state / "config.json").exists()


def test_secret_and_other_legacy_readers_keep_writes_canonical(monkeypatch, tmp_path: Path) -> None:
    home, canonical_user, canonical_state = _isolate_user_roots(monkeypatch, tmp_path)
    legacy_state = home / ".bago" / "state"
    legacy_state.mkdir(parents=True)
    (legacy_state / "model_blacklist.json").write_text(
        json.dumps({"version": 1, "models": ["legacy:model"], "reasons": {}}),
        encoding="utf-8",
    )
    active = legacy_state / "active_models"
    active.mkdir()
    (active / "ollama-local.json").write_text('["legacy:model"]', encoding="utf-8")
    (legacy_state / "last_auto_config.json").write_text(
        json.dumps({"status": "done", "legacy": True}), encoding="utf-8"
    )
    (legacy_state / "intent_examples.json").write_text(
        json.dumps({"chat": [{"user": "legacy fixture", "assistant": "ok"}]}),
        encoding="utf-8",
    )
    legacy_selection = home / ".bago" / "install_selection.json"
    legacy_selection.write_text('{"version": 1}', encoding="utf-8")

    secret_store = importlib.import_module("secret_store")
    monkeypatch.setattr(secret_store, "_is_windows", lambda: False)
    legacy_secrets = home / ".bago" / "secrets"
    legacy_secrets.mkdir()
    (legacy_secrets / "fixture.bin").write_bytes(secret_store._fallback_protect(b"legacy-value"))

    blacklist = importlib.import_module("blacklist_models")
    providers = importlib.import_module("handlers_providers")
    auto = importlib.import_module("auto_configurator")
    intent = importlib.import_module("intent_engine")
    commands = importlib.import_module("commands")

    assert secret_store.SecretStore().get_secret("fixture") == "legacy-value"
    secret_store.SecretStore().set_secret("canonical", "new-value")
    assert (canonical_user / "secrets" / "canonical.bin").is_file()
    assert blacklist.get_blacklist()["models"] == ["legacy:model"]
    assert providers._load_active_models("ollama-local") == ["legacy:model"]
    assert auto._load_last_job()["legacy"] is True
    assert any(row["user"] == "legacy fixture" for row in intent._load_examples()["chat"])
    assert commands._install_roles_read_path() == legacy_selection
    assert not (canonical_state / "model_blacklist.json").exists()


def test_legacy_flat_session_loads_without_copying_record(monkeypatch, tmp_path: Path) -> None:
    home, _, canonical_state = _isolate_user_roots(monkeypatch, tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    legacy_state = home / ".bago" / "state"

    session_manager = importlib.import_module("session_manager")
    original = session_manager.SessionManager(
        session_id="legacy-session",
        provider="ollama-local",
        model="fixture-model",
        base_path=str(project),
        state_root=str(legacy_state),
    )
    original.save()
    original.close()

    canonical_record = canonical_state / "sessions" / "legacy-session.json"
    assert not canonical_record.exists()
    loaded = session_manager.SessionManager.load("legacy-session", base_path=str(project))
    try:
        assert loaded.session_id == "legacy-session"
        assert loaded.state_root == canonical_state
        assert not canonical_record.exists()
    finally:
        loaded.close()


def test_mutable_state_modules_do_not_construct_direct_home_bago_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    targets = (
        ".bago/api/structured_log.py",
        ".bago/api/secret_store.py",
        ".bago/api/handlers_providers.py",
        ".bago/api/handlers_vision.py",
        ".bago/api/auto_configurator.py",
        ".bago/api/blacklist_models.py",
        ".bago/core/intent_engine.py",
        ".bago/chat/commands.py",
    )
    direct_home = re.compile(r"Path\.home\(\)[^\n]{0,160}[\"']\.bago[\"']")
    duplicate_env = re.compile(r"os\.environ\.get\([\"']BAGO_(?:USER|STATE)_ROOT[\"']")

    violations: list[str] = []
    for relative in targets:
        source = (root / relative).read_text(encoding="utf-8")
        if direct_home.search(source) or duplicate_env.search(source):
            violations.append(relative)
    assert violations == []

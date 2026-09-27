from __future__ import annotations

import json
from pathlib import Path

import config_manager
from config_manager import ConfigManager


def test_config_manager_defers_empty_root_creation_until_owner_write(tmp_path, monkeypatch):
    legacy_config = tmp_path / "legacy-config.json"
    legacy_config.write_text(json.dumps({"default_model": "legacy-model"}), encoding="utf-8")
    state_root = tmp_path / "deferred-state"
    monkeypatch.setattr(config_manager, "state_read_candidates", lambda _name: [legacy_config])
    monkeypatch.setattr(config_manager, "resolve_state_root", lambda _root: state_root)

    manager = ConfigManager()

    assert manager.default_model == "legacy-model"
    assert not state_root.exists()

    manager.set("default_model", "updated-model")
    assert json.loads((state_root / "config.json").read_text(encoding="utf-8"))["default_model"] == "updated-model"

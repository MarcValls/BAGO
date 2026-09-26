from __future__ import annotations

import json
import importlib


def test_android_layers_projection_uses_server_state_writer(tmp_path, monkeypatch) -> None:
    from bago_core import atomic_json
    cmd_android = importlib.import_module("bago_core.commands.cmd_android")

    target_seen = []
    original = atomic_json.write_json_atomic

    def capture(path, payload):
        target_seen.append((path, payload))
        return original(path, payload)

    monkeypatch.setattr(atomic_json, "write_json_atomic", capture)
    payload = {"ok": True, "selected_provider": "codex", "layers": {"runtime": {"ok": True}}}

    target = cmd_android._write_layers_state(tmp_path, payload)

    assert target == tmp_path / cmd_android.ANDROID_LAYERS_STATE
    assert target_seen == [(target, payload)]
    assert json.loads(target.read_text(encoding="utf-8")) == payload

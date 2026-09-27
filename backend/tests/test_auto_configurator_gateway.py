from __future__ import annotations

import json
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1] / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import auto_configurator


def test_terminal_job_persistence_uses_state_write_owner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(auto_configurator, "state_root", lambda: tmp_path)
    job = auto_configurator.AutoConfigJob(
        status="done", generated_config={"default_model": "m"},
    )
    monkeypatch.setattr(auto_configurator, "JOB", job)

    auto_configurator._persist_last_job()

    saved = json.loads((tmp_path / "last_auto_config.json").read_text(encoding="utf-8"))
    assert saved["status"] == "done"
    assert saved["generated_config"] == {"default_model": "m"}


def test_apply_generated_config_uses_config_write_owner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(auto_configurator, "state_root", lambda: tmp_path)
    monkeypatch.setattr(auto_configurator, "_read_state_json", lambda _relative: {"kept": True})
    job = auto_configurator.AutoConfigJob(
        status="done",
        generated_config={
            "default_model": "model-x",
            "translation_middleware": {"enabled": True, "translator_model": "translator-y"},
            "blacklist": [],
            "model_quality": {"model-x": 8.0},
        },
    )
    monkeypatch.setattr(auto_configurator, "JOB", job)

    result = auto_configurator.apply_generated_config()

    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert saved["kept"] is True
    assert saved["default_model"] == "model-x"
    assert saved["providers"]["ollama-local"]["default_model"] == "model-x"
    assert saved["translation_middleware"]["translator_model"] == "translator-y"

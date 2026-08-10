from __future__ import annotations

import json
from pathlib import Path

from handlers_router import restore_session_model, restore_session_reasoning


class FakeManager:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.provider = "ollama-local"
        self.model = "llama3.2:3b"
        self.reasoning_depth = "normal"
        self.reasoning_effort = "low"
        self.switches: list[tuple[str, str, bool]] = []

    def switch(self, provider: str, model: str, force: bool = False):
        self.switches.append((provider, model, force))
        self.provider = provider
        self.model = model
        return {"ok": True}


def test_restore_session_model_reapplies_persisted_provider_and_model(tmp_path: Path):
    (tmp_path / ".bago_session_model.json").write_text(
        json.dumps({"model": "copilot/gpt-5.4-mini"}), encoding="utf-8",
    )
    manager = FakeManager(tmp_path)

    report = restore_session_model(manager)

    assert report["ok"] is True
    assert report["restored"] is True
    assert manager.switches == [("copilot", "gpt-5.4-mini", True)]
    assert (manager.provider, manager.model) == ("copilot", "gpt-5.4-mini")


def test_restore_session_reasoning_reapplies_persisted_depth(tmp_path: Path):
    (tmp_path / ".bago_reasoning_depth.json").write_text(
        json.dumps({"depth": "maxima"}), encoding="utf-8",
    )
    manager = FakeManager(tmp_path)

    report = restore_session_reasoning(manager)

    assert report["ok"] is True
    assert report["restored"] is True
    assert manager.reasoning_depth == "maxima"
    assert manager.reasoning_effort == "xhigh"

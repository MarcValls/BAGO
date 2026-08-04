from __future__ import annotations

import json
from pathlib import Path

from handlers_router import restore_session_model


class FakeManager:
    def __init__(self, state_root: Path):
        self.state_root = state_root
        self.session_id = "session-model-test"
        self.provider = "ollama-local"
        self.model = "llama3.2:3b"
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
    assert not (tmp_path / ".bago_session_model.json").exists()
    assert (tmp_path / "session-models" / "session-model-test.json").exists()

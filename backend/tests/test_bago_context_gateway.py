from __future__ import annotations

import json
from pathlib import Path

import pytest

import bago_context as bago_context_module
from bago_context import BagoContext
import effect_sink_inventory as inventory


def test_context_flush_replaces_event_queue_through_state_gateway(tmp_path, monkeypatch):
    root = tmp_path
    event_path = root / ".bago" / "state" / "events.jsonl"
    event_path.parent.mkdir(parents=True)
    expected = {"event": "dispatch:after", "data": {"returncode": 0}}
    event_path.write_text(json.dumps(expected) + "\n", encoding="utf-8")
    monkeypatch.setattr(bago_context_module, "_EVENTS_PATH", event_path)
    context = BagoContext()
    context.root = root

    events = context.flush_events()

    assert events == [expected]
    assert event_path.exists()
    assert event_path.read_text(encoding="utf-8") == ""
    assert inventory.scan_python(Path(inventory.REPO_ROOT / "backend/.bago/core/bago_context.py")) == []


def test_retired_context_tool_runner_fails_closed():
    with pytest.raises(RuntimeError, match="ExecutionGateway"):
        BagoContext().run_tool("status")

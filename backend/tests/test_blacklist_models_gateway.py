from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def test_blacklist_state_writer_uses_gateway_and_creates_its_parent(tmp_path) -> None:
    blacklist = importlib.import_module("blacklist_models")
    root = tmp_path / "isolated" / "state"
    target = root / "model_blacklist.json"
    payload = {"version": 1, "models": ["fixture:model"], "reasons": {}}

    blacklist._write_atomic(target, payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert list(root.glob("*.tmp")) == []

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import bago_utils


def test_save_json_uses_server_owned_gateway_and_binds_to_project_bago_root(tmp_path):
    bago_root = tmp_path / ".bago"
    target = bago_root / "state" / "sample.json"

    assert bago_utils.save_json(target, {"owner": "gateway", "count": 2})

    assert json.loads(target.read_text(encoding="utf-8")) == {"owner": "gateway", "count": 2}


def test_save_json_rejects_targets_without_project_bago_root(tmp_path):
    assert not bago_utils.save_json(tmp_path / "outside.json", {"x": 1})
    assert not (tmp_path / "outside.json").exists()


def test_get_state_dir_resolves_without_creating_it(monkeypatch, tmp_path):
    root = tmp_path / ".bago"
    monkeypatch.setattr(bago_utils, "get_bago_root", lambda: root)

    assert bago_utils.get_state_dir() == root / "state"
    assert not root.exists()


def test_inventory_has_no_direct_json_writer_sinks():
    from effect_sink_inventory import build_inventory

    inventory = build_inventory()
    findings = [item for item in inventory["findings"] if item["path"] == "backend/.bago/tools/bago_utils.py"]

    assert findings == []

#!/usr/bin/env python3
"""Repair routing_runtime.json to match the canonical balanced contract."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
preset_path = ROOT / "docs" / "contracts" / "bago_v4_routing_presets.json"
runtime_path = ROOT / ".gabo" / "routing_runtime.json"

with open(preset_path, "r", encoding="utf-8") as f:
    p = json.load(f)
with open(runtime_path, "r", encoding="utf-8") as f:
    r = json.load(f)

expected = p["presets"]["balanced"]["contract"]["text"]
r["active_preset"] = "balanced"
r["contract"] = {
    "text": expected,
    "source": "file:docs/contracts/bago_v4_routing_presets.json#balanced",
}

with open(runtime_path, "w", encoding="utf-8") as f:
    json.dump(r, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("runtime_path updated, len:", len(expected))

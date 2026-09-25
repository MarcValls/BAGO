from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / ".bago" / "core"
AGENTS = ROOT / ".bago" / "agents"
for candidate in (str(ROOT), str(CORE), str(AGENTS)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from execution_adapter_contract import ExecutionGatewayError
from bago_core import server_effects


@pytest.fixture
def isolated_agent_factory(tmp_path, monkeypatch):
    state_root = tmp_path / ".bago" / "state"
    monkeypatch.setattr(server_effects, "_agent_definition_state_root", lambda: state_root)
    factory = importlib.import_module("agent_factory")
    monkeypatch.setattr(factory, "DYNAMIC_AGENTS_DIR", state_root / "agents")
    monkeypatch.setattr(factory, "DYNAMIC_MANIFEST", state_root / "agents" / "manifest.json")
    return factory, state_root


def test_agent_factory_writes_definition_and_manifest_via_gateway(isolated_agent_factory) -> None:
    factory, state_root = isolated_agent_factory
    assert factory.dynamic_path("alpha") == state_root / "agents" / "alpha.py"

    assert factory.create_agent("alpha", "security", "fixture agent", ["no_global"])

    definition = state_root / "agents" / "alpha.py"
    manifest = state_root / "agents" / "manifest.json"
    assert "class Alpha" in definition.read_text(encoding="utf-8")
    assert json.loads(manifest.read_text(encoding="utf-8"))["agents"]["alpha"]["status"] == "active"
    assert list((state_root / "agents").glob("*.tmp")) == []


def test_agent_definition_owner_rejects_noncanonical_targets_before_write(isolated_agent_factory) -> None:
    _factory, state_root = isolated_agent_factory
    outside_agents = state_root / "other" / "rogue.py"

    with pytest.raises(ExecutionGatewayError, match="Agent definition target"):
        server_effects.write_agent_definition(
            outside_agents,
            "# forbidden",
            trusted_root=state_root,
        )

    assert not outside_agents.exists()

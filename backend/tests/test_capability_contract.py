from __future__ import annotations

import copy
from pathlib import Path

import pytest

from capability_contract import (
    CAPABILITY_ID,
    CapabilityContractError,
    build_capability_snapshot,
    validate_capability,
)


class FakeMgr:
    def __init__(self, root: Path):
        self.root = root

    def status(self):
        return {
            "binding_confirmed": True,
            "project_root": str(self.root),
            "framework_root": str(self.root),
        }


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    for name in ("tools", "agents", "scripts"):
        (tmp_path / name).mkdir()
    (tmp_path / "tools" / "reader.py").write_text('"""Lee el workspace."""\n\ndef run():\n    return True\n', encoding="utf-8")
    (tmp_path / "agents" / "reviewer.py").write_text('def review():\n    return True\n', encoding="utf-8")
    (tmp_path / "scripts" / "verify.py").write_text('print("ok")\n', encoding="utf-8")
    return tmp_path


def test_snapshot_projects_real_inventory_as_read_only_contract(project: Path):
    snapshot = build_capability_snapshot(FakeMgr(project))
    assert snapshot["capability"]["id"] == CAPABILITY_ID
    assert snapshot["source"]["authority"] == "backend"
    assert snapshot["host_binding"]["mode"] == "read_only"
    assert snapshot["runtime_snapshot"]["run_state"] == "not_started"
    assert snapshot["runtime_snapshot"]["receipt_id"] is None
    discovered = snapshot["pieces"][1:-1]
    assert {piece["implementation"]["kind"] for piece in discovered} == {"tool", "agent", "script"}
    assert len(snapshot["routes"]) == 3
    validate_capability(snapshot)


def test_each_route_closes_from_input_to_output(project: Path):
    snapshot = build_capability_snapshot(FakeMgr(project))
    piece_by_id = {piece["id"]: piece for piece in snapshot["pieces"]}
    for route in snapshot["routes"]:
        assert piece_by_id[route["steps"][0]]["type"] == "input"
        assert piece_by_id[route["steps"][-1]]["type"] == "output"


def test_validator_rejects_false_success(project: Path):
    snapshot = build_capability_snapshot(FakeMgr(project))
    invalid = copy.deepcopy(snapshot)
    invalid["runtime_snapshot"]["run_state"] = "succeeded"
    with pytest.raises(CapabilityContractError, match="Éxito sin"):
        validate_capability(invalid)


def test_validator_rejects_mutation_in_read_only(project: Path):
    snapshot = build_capability_snapshot(FakeMgr(project))
    invalid = copy.deepcopy(snapshot)
    invalid["governance"]["action_policy"]["allowed"].append({"id": "write", "kind": "mutation", "label": "Guardar"})
    with pytest.raises(CapabilityContractError, match="Mutación permitida"):
        validate_capability(invalid)


def test_validator_rejects_broken_route(project: Path):
    snapshot = build_capability_snapshot(FakeMgr(project))
    invalid = copy.deepcopy(snapshot)
    invalid["routes"][0]["steps"][-1] = "missing-piece"
    with pytest.raises(CapabilityContractError, match="referencias de ruta"):
        validate_capability(invalid)


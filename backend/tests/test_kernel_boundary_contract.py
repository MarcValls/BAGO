from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "backend" / ".bago" / "contracts" / "bago.kernel-boundary.v1.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_kernel_boundary_contract_declares_backend_authority() -> None:
    contract = _contract()

    assert contract["contract"] == "bago.kernel-boundary.v1"
    assert contract["version"] == "1.0.0"
    assert contract["status"] == "active"
    assert contract["authority"] == {
        "session_state": "backend/.bago/core",
        "canonical_decisions": "backend/.bago/core",
        "execution_policy": "backend/.bago/api",
        "evidence_receipts": "backend/.bago/core",
    }


def test_capability_and_ui_surfaces_do_not_claim_kernel_authority() -> None:
    contract = _contract()
    enforcement = contract["enforcement"]
    assert isinstance(enforcement, dict)
    capability_patterns = enforcement["forbidden_capability_patterns"]
    ui_patterns = enforcement["forbidden_ui_patterns"]
    assert isinstance(capability_patterns, list)
    assert isinstance(ui_patterns, list)

    extension_boundary = contract["extension_boundary"]
    assert isinstance(extension_boundary, dict)
    capability_paths = extension_boundary["capability_paths"]
    assert isinstance(capability_paths, list)
    for relative_path in capability_paths:
        source = (ROOT / str(relative_path)).read_text(encoding="utf-8")
        for pattern in capability_patterns:
            assert not re.search(str(pattern), source), f"{relative_path} claims kernel authority via {pattern!r}"

    ui_root = ROOT / str(contract["ui_boundary"]["root"])
    for path in ui_root.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in ui_patterns:
            assert not re.search(str(pattern), source), f"{path.relative_to(ROOT)} claims kernel authority via {pattern!r}"

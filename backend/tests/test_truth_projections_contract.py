"""AC7: generated truth projections exist, carry provenance, and CI runs their drift checks."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTES = ROOT / "backend" / "contracts" / "api_routes.generated.json"
IMPORT_INVENTORY = ROOT / "backend" / "contracts" / "import_migration_inventory.v1.json"
ROUTING_POLICY = ROOT / "backend" / "contracts" / "model_routing_policy.v1.json"
CI = ROOT / ".github" / "workflows" / "canonical-ci.yml"
GENERATOR = ROOT / "backend" / "scripts" / "generate_api_routes_contract.py"


def test_routes_projection_is_generated_from_canonical_dispatch() -> None:
    contract = json.loads(ROUTES.read_text(encoding="utf-8"))

    assert contract["source"] == "backend/.bago/api/api_dispatch.py"
    assert contract["routes"]
    assert all({"method", "path", "handler_module", "handler_fn"} <= set(route) for route in contract["routes"])
    # Dynamic routes come from DYNAMIC_ROUTE_META, not a hardcoded subset.
    assert len(contract["dynamic_routes"]) > 8
    dynamic_paths = {route["path"] for route in contract["dynamic_routes"]}
    assert "/api/v1/kb/<key>" in dynamic_paths
    assert "/api/v1/capability-packages/<capability_id>/execute" in dynamic_paths
    assert "/schedule/<schedule_id>" in dynamic_paths
    assert "DYNAMIC_ROUTE_META" in GENERATOR.read_text(encoding="utf-8")


def test_import_inventory_and_routing_policy_are_versioned_projections() -> None:
    inventory = json.loads(IMPORT_INVENTORY.read_text(encoding="utf-8"))
    policy = json.loads(ROUTING_POLICY.read_text(encoding="utf-8"))

    assert inventory["contract"] == "bago.import-migration-inventory.v1"
    assert inventory["total_files"] > 0
    assert inventory["generated_from"].startswith("AST scan")
    assert policy["contract"] == "bago.model-routing-policy.v1"
    assert policy["version"] == "1.0.0"
    assert policy["source"] == "repository-policy"


def test_ci_runs_drift_checks_for_generated_projections() -> None:
    ci = CI.read_text(encoding="utf-8")

    assert "Check generated truth projections for drift" in ci
    assert "python backend/scripts/generate_api_routes_contract.py --check" in ci
    assert "test_import_consolidation.py::test_migration_inventory_is_current_and_machine_checkable" in ci
    assert "test_version_drift.py" in ci
    # Drift checks must run after dependencies are installed.
    assert ci.index("Install dependencies") < ci.index("Check generated truth projections for drift")
    drift_block = ci[ci.index("Check generated truth projections"):ci.index("Build, typecheck")]
    assert "working-directory" not in drift_block


def test_routes_generator_supports_check_mode() -> None:
    source = GENERATOR.read_text(encoding="utf-8")

    assert '"--check"' in source
    assert "generated contract differs" in source


def test_import_inventory_generator_supports_check_mode() -> None:
    source = (ROOT / "backend" / "scripts" / "generate_import_migration_inventory.py").read_text(encoding="utf-8")

    assert '"--check"' in source
    assert "drift detected" in source
    assert "add_piece_paths" in source
    assert "sys.path" in source

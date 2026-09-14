"""AC5: Capability API v1 external contract agreement across backend and frontend."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SCHEMA = ROOT / "backend" / ".bago" / "contracts" / "bago.package.v1.schema.json"
CAPABILITY_SCHEMA = ROOT / "backend" / ".bago" / "contracts" / "bago.capability-definition.v1.schema.json"
BACKEND_CORE = ROOT / "backend" / ".bago" / "core" / "capability_packages.py"
BACKEND_HANDLERS = ROOT / "backend" / ".bago" / "api" / "handlers_capability_packages.py"
BACKEND_DISPATCH = ROOT / "backend" / ".bago" / "api" / "api_dispatch.py"
FRONTEND_TYPES = ROOT / "frontend" / "src" / "modules" / "capability-anatomy" / "packageContract.ts"
FRONTEND_CLIENT = ROOT / "frontend" / "src" / "api" / "client.ts"


def test_package_schema_declares_permissions_network_and_receipt_surface() -> None:
    schema = json.loads(PACKAGE_SCHEMA.read_text(encoding="utf-8"))

    assert schema["properties"]["contract_version"]["const"] == "bago.package/v1"
    permission_enum = schema["properties"]["permissions"]["items"]["enum"]
    assert "network" in permission_enum
    assert "process" in permission_enum
    assert set(permission_enum) == {"filesystem.read", "filesystem.write", "network", "process"}


def test_runtime_declares_same_permission_set_and_contract_version() -> None:
    core = BACKEND_CORE.read_text(encoding="utf-8")

    assert 'CONTRACT_VERSION = "bago.capability/v1"' in core
    assert '"network",' in core
    for permission in ("filesystem.read", "filesystem.write", "network", "process"):
        assert f'"{permission}"' in core


def test_execution_requires_enabled_trusted_confirmed_and_approved_permissions() -> None:
    core = BACKEND_CORE.read_text(encoding="utf-8")

    for marker in (
        'code="not_enabled"',
        'code="trust_required"',
        'code="confirmation_required"',
        'code="permission_approval_required"',
        "missing_permissions",
    ):
        assert marker in core


def test_dry_run_inspect_route_exists_without_execution() -> None:
    handlers = BACKEND_HANDLERS.read_text(encoding="utf-8")
    dispatch = BACKEND_DISPATCH.read_text(encoding="utf-8")

    assert '"/api/v1/capability-packages/inspect"' in dispatch
    assert "def handle_inspect" in handlers
    assert "inspect_package" in handlers
    # Inspect must not execute: it calls inspect_package, not execute_package.
    inspect_body = handlers[handlers.index("def handle_inspect"):handlers.index("def handle_export")]
    assert "execute_package" not in inspect_body


def test_frontend_types_mirror_backend_package_and_receipt_contract() -> None:
    types = FRONTEND_TYPES.read_text(encoding="utf-8")

    for field in (
        "permissions: string[]",
        "receipt_id",
        "execution_id",
        "trust_state",
        "trusted_permissions",
    ):
        assert field in types
    assert "'untrusted' | 'trusted'" in types


def test_frontend_client_uses_versioned_capability_package_routes() -> None:
    client = FRONTEND_CLIENT.read_text(encoding="utf-8")

    for route in (
        "/api/v1/capability-packages/inspect",
        "/api/v1/capability-packages/import",
        "/api/v1/capability-packages/receipts",
        "/api/v1/capability-packages/examples",
    ):
        assert route in client
    assert "confirmTrust" in client
    assert "executeCapabilityPackage" in client

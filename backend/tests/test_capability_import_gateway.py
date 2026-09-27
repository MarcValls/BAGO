from __future__ import annotations

import base64
import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / ".bago" / "core"
API = CORE.parent / "api"
sys.path[:0] = [str(CORE), str(API)]
SPEC = importlib.util.spec_from_file_location("capability_import_handler_test", API / "handlers_capability_packages.py")
HANDLER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(HANDLER)


def _archive() -> str:
    from package_contract import canonical_archive, canonical_json

    manifest = {
        "schema_version": "1.0", "contract_version": "bago.package/v1",
        "kind": "capability", "execution_mode": "declarative",
        "id": "local.gateway-import", "name": "Gateway import", "version": "1.0.0",
        "description": "Gateway import fixture", "author": "tests",
        "definition": "definitions/capability.json", "permissions": [],
        "compatibility": {"bago_package": "^1.0"}, "dependencies": [],
    }
    definition = {"id": "local.gateway-import", "input_schema": {"type": "object", "properties": {}}}
    return base64.b64encode(canonical_archive(manifest, {"definitions/capability.json": canonical_json(definition)})).decode("ascii")


def test_http_import_consumes_permit_bound_to_exact_archive(monkeypatch, tmp_path: Path) -> None:
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    manager = SimpleNamespace(session_id="package-import-session")
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setattr(importlib.import_module("capability_packages"), "state_root", lambda: tmp_path / "state")
    content = _archive()
    body = {"file_name": "gateway-import.zip", "content_base64": content, "interaction_id": "import-ui-1"}

    HANDLER.handle_import(handler, {**body, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    HANDLER.handle_import(handler, {**body, "authorization_action": "approve", "challenge_id": challenge["challenge_id"], "user_decision": "approve"})
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    HANDLER.handle_import(handler, {**body, "authorization_action": "execute", "authorization_permit": permit})

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "capability.package.import"
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    assert responses[-1][1]["package"]["id"] == "local.gateway-import"
    assert responses[-1][1]["package"]["enabled"] is False

    example_body = {"interaction_id": "example-ui-1"}
    HANDLER.handle_install_example(handler, "local.text-transform", {**example_body, "authorization_action": "challenge"})
    example_challenge = responses[-1][1]["authorization"]["challenge"]
    HANDLER.handle_install_example(handler, "local.text-transform", {
        **example_body, "authorization_action": "approve",
        "challenge_id": example_challenge["challenge_id"], "user_decision": "approve",
    })
    example_permit = responses[-1][1]["authorization"]["permit"]["token"]
    HANDLER.handle_install_example(handler, "local.text-transform", {
        **example_body, "authorization_action": "execute", "authorization_permit": example_permit,
    })
    assert responses[-1][0] == 200
    assert responses[-1][1]["package"]["id"] == "local.text-transform"


def test_direct_import_entrypoint_fails_before_persistent_mutation(monkeypatch, tmp_path: Path) -> None:
    packages = importlib.import_module("capability_packages")
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")
    try:
        packages.import_package(content_base64=_archive(), file_name="direct.zip")
    except packages.CapabilityPackageError as exc:
        assert exc.code == "authorization_required"
    else:
        raise AssertionError("Direct import bypassed ExecutionGateway")
    assert not (tmp_path / "state" / "capabilities").exists()


def test_capability_process_runs_only_after_execution_gateway_consumes_permit(monkeypatch, tmp_path: Path) -> None:
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    authorization = importlib.import_module("authorization_boundary")
    packages = importlib.import_module("capability_packages")
    manager = SimpleNamespace(session_id="capability-runtime-session")
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")
    monkeypatch.setattr(authorization, "state_root", lambda: tmp_path / "state")

    archive, filename = packages.example_package_archive("local.text-transform")
    import_body = {"file_name": filename, "content_base64": archive, "interaction_id": "runtime-import"}
    HANDLER.handle_import(handler, {**import_body, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    HANDLER.handle_import(handler, {**import_body, "authorization_action": "approve", "challenge_id": challenge["challenge_id"], "user_decision": "approve"})
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    HANDLER.handle_import(handler, {**import_body, "authorization_action": "execute", "authorization_permit": permit})
    packages.set_enabled("local.text-transform", True, confirm_trust=True)

    execute_body = {"input": {"text": "  BAGO   Gateway  "}, "interaction_id": "runtime-execute"}
    HANDLER.handle_execute(handler, "local.text-transform", {**execute_body, "authorization_action": "challenge"})
    execute_challenge = responses[-1][1]["authorization"]["challenge"]
    HANDLER.handle_execute(handler, "local.text-transform", {
        **execute_body, "authorization_action": "approve",
        "challenge_id": execute_challenge["challenge_id"], "user_decision": "approve",
    })
    execute_permit = responses[-1][1]["authorization"]["permit"]["token"]
    HANDLER.handle_execute(handler, "local.text-transform", {
        **execute_body, "authorization_action": "execute", "authorization_permit": execute_permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    assert responses[-1][1]["receipt"]["status"] == "succeeded"
    assert responses[-1][1]["receipt"]["result"]["text"] == "BAGO Gateway"

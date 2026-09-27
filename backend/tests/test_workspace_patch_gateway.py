from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


API = Path(__file__).resolve().parents[1] / ".bago" / "api"
CORE = API.parent / "core"
sys.path[:0] = [str(API), str(CORE)]
SPEC = importlib.util.spec_from_file_location("handlers_project_patch_test", API / "handlers_project_patch.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


DIFF = "--- a/src.py\n+++ b/src.py\n@@ -1,1 +1,1 @@\n-value = 1\n+value = 2\n"


def _setup(monkeypatch, tmp_path: Path):
    auth = importlib.import_module("authorization_boundary")
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "src.py").write_text("value = 1\n", encoding="utf-8")
    manager = SimpleNamespace(session_id="patch-session", project_root=project_root)
    responses: list[tuple[int, dict]] = []
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))
    return handler, manager, responses


def _authorize_apply(handler, responses, payload):
    MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    return responses[-1][1]["authorization"]["permit"]["token"]


def _authorize_rollback(handler, responses, payload):
    MODULE.handle_rollback(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_rollback(handler, {
        **payload,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    return responses[-1][1]["authorization"]["permit"]["token"]


def test_patch_writes_only_after_project_write_permit_and_retains_rollback_receipt(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    payload = {"patches": [DIFF], "interaction_id": "patch-apply-1"}
    permit = _authorize_apply(handler, responses, payload)
    target = manager.project_root / "src.py"
    assert target.read_text(encoding="utf-8") == "value = 1\n"
    snapshots = manager.project_root / ".bago" / "snapshots"
    assert not snapshots.exists() or list(snapshots.iterdir()) == []

    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    receipt = responses[-1][1]
    assert responses[-1][0] == 200
    assert receipt["effect_id"] == "project.write"
    assert receipt["operation"] == "patch"
    assert receipt["authorization"]["state"] == "consumed"
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    snapshot = Path(receipt["result"]["snapshot"])
    assert snapshot.is_dir()
    assert (snapshot / "patch-receipt.v1.json").is_file()


def test_public_atomic_patch_client_dispatches_through_execution_gateway(monkeypatch, tmp_path: Path) -> None:
    from bago_core.codegen.patch_parser import parse_patch
    from bago_core.execution.atomic_patch import apply_patch_atomically

    handler, manager, responses = _setup(monkeypatch, tmp_path)
    payload = {"patches": [DIFF], "interaction_id": "patch-client-1"}
    permit = _authorize_apply(handler, responses, payload)
    result = apply_patch_atomically(
        [parse_patch(DIFF)],
        workspace_root=manager.project_root,
        manager=manager,
        permit_token=permit,
    )

    assert result.ok
    assert result.applied[0].path == "src.py"
    assert (manager.project_root / "src.py").read_text(encoding="utf-8") == "value = 2\n"


def test_patch_target_change_after_approval_blocks_before_snapshot_or_write(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    payload = {"patches": [DIFF], "interaction_id": "patch-change-1"}
    permit = _authorize_apply(handler, responses, payload)
    target = manager.project_root / "src.py"
    target.write_text("value = 1\nother = 9\n", encoding="utf-8")

    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_operation_mismatch"
    assert target.read_text(encoding="utf-8") == "value = 1\nother = 9\n"
    assert not (manager.project_root / ".bago" / "snapshots").exists()


def test_patch_rollback_uses_same_project_write_owner_and_preserves_later_changes(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    apply_payload = {"patches": [DIFF], "interaction_id": "patch-apply-2"}
    permit = _authorize_apply(handler, responses, apply_payload)
    MODULE.handle_apply(handler, {
        **apply_payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })
    snapshot = responses[-1][1]["result"]["snapshot"]
    rollback_payload = {"snapshot": snapshot, "interaction_id": "patch-rollback-1"}
    rollback_permit = _authorize_rollback(handler, responses, rollback_payload)

    MODULE.handle_rollback(handler, {
        **rollback_payload,
        "authorization_action": "execute",
        "authorization_permit": rollback_permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "project.write"
    assert responses[-1][1]["operation"] == "patch.rollback"
    assert (manager.project_root / "src.py").read_text(encoding="utf-8") == "value = 1\n"


def test_forbidden_patch_path_rejects_before_snapshot_creation(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    forbidden = "--- a/.env\n+++ b/.env\n@@ -1,1 +1,1 @@\n-secret\n+changed\n"
    MODULE.handle_apply(handler, {"patches": [forbidden], "authorization_action": "challenge"})

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "workspace_patch_forbidden_path"
    assert not (manager.project_root / ".bago" / "snapshots").exists()


def test_linked_patch_target_rejects_before_snapshot_or_external_write(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    external = tmp_path / "external.py"
    external.write_text("value = 1\n", encoding="utf-8")
    try:
        (manager.project_root / "linked.py").symlink_to(external)
    except OSError as exc:
        import pytest

        pytest.skip(f"file symlink unavailable: {exc}")
    diff = "--- a/linked.py\n+++ b/linked.py\n@@ -1,1 +1,1 @@\n-value = 1\n+value = 2\n"
    MODULE.handle_apply(handler, {"patches": [diff], "authorization_action": "challenge"})

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "workspace_patch_link_forbidden"
    assert external.read_text(encoding="utf-8") == "value = 1\n"
    assert not (manager.project_root / ".bago" / "snapshots").exists()


def test_rollback_rejects_target_changed_after_patch_without_overwriting_it(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    apply_payload = {"patches": [DIFF], "interaction_id": "patch-apply-3"}
    permit = _authorize_apply(handler, responses, apply_payload)
    MODULE.handle_apply(handler, {
        **apply_payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })
    snapshot = responses[-1][1]["result"]["snapshot"]
    target = manager.project_root / "src.py"
    target.write_text("later edit\n", encoding="utf-8")
    rollback_payload = {"snapshot": snapshot, "interaction_id": "patch-rollback-2"}
    rollback_permit = _authorize_rollback(handler, responses, rollback_payload)

    MODULE.handle_rollback(handler, {
        **rollback_payload,
        "authorization_action": "execute",
        "authorization_permit": rollback_permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "workspace_patch_rollback_target_changed"
    assert target.read_text(encoding="utf-8") == "later edit\n"


def test_failed_multi_file_apply_restores_prior_targets_and_removes_snapshot(monkeypatch, tmp_path: Path) -> None:
    storage = importlib.import_module("workspace_patch_storage")
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    second = manager.project_root / "other.py"
    second.write_text("ready = True\n", encoding="utf-8")
    second_diff = "--- a/other.py\n+++ b/other.py\n@@ -1,1 +1,1 @@\n-ready = True\n+ready = False\n"
    payload = {"patches": [DIFF, second_diff], "interaction_id": "patch-partial-1"}
    permit = _authorize_apply(handler, responses, payload)
    actual_replace = storage.os.replace
    calls = 0

    def fail_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated second-file replace failure")
        return actual_replace(source, destination)

    monkeypatch.setattr(storage.os, "replace", fail_second_replace)
    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "workspace_patch_apply_failed"
    assert (manager.project_root / "src.py").read_text(encoding="utf-8") == "value = 1\n"
    assert second.read_text(encoding="utf-8") == "ready = True\n"
    snapshots = manager.project_root / ".bago" / "snapshots"
    assert not snapshots.exists() or list(snapshots.iterdir()) == []

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


API = Path(__file__).resolve().parents[1] / ".bago" / "api"
CORE = API.parent / "core"
sys.path[:0] = [str(API), str(CORE)]
SPEC = importlib.util.spec_from_file_location("handlers_install_source_update_test", API / "handlers_install.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _fixture(monkeypatch, tmp_path: Path):
    auth = importlib.import_module("authorization_boundary")
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    adapter_module = importlib.import_module("execution_adapters.source_update")
    source = tmp_path / "source"
    (source / ".git").mkdir(parents=True)
    responses: list[tuple[int, dict]] = []
    calls: list[tuple[str, ...]] = []

    def git(_root, *args):
        calls.append(tuple(args))
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        if args == ("remote", "get-url", "origin"):
            return "https://github.com/example/bago.git"
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("pull", "--ff-only", "origin", "main"):
            return "Already up to date."
        raise AssertionError(args)

    monkeypatch.setattr(adapter_module.SystemSourceUpdateEffectAdapter, "_git", staticmethod(git))
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: SimpleNamespace(session_id="source-session"))
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    handler = SimpleNamespace(headers={"X-Bago-Channel": "desktop"})
    payload = {"source_root": str(source), "branch": "main", "interaction_id": "source-update-test"}
    return handler, payload, responses, calls


def test_source_update_challenge_is_read_only_and_binds_checkout(monkeypatch, tmp_path: Path) -> None:
    handler, payload, responses, calls = _fixture(monkeypatch, tmp_path)
    MODULE.handle_source_update(handler, {**payload, "authorization_action": "challenge"})

    assert responses[-1][0] == 200
    challenge = responses[-1][1]["authorization"]["challenge"]
    assert challenge["effect_id"] == "system.source.update"
    assert challenge["target"]["expected_head"] == "a" * 40
    assert challenge["target"]["origin_sha256"]
    assert ("pull", "--ff-only", "origin", "main") not in calls


def test_source_update_requires_exact_desktop_permit_and_rechecks_before_pull(monkeypatch, tmp_path: Path) -> None:
    handler, payload, responses, calls = _fixture(monkeypatch, tmp_path)
    MODULE.handle_source_update(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_source_update(handler, {
        **payload, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    MODULE.handle_source_update(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "system.source.update"
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    assert calls.count(("pull", "--ff-only", "origin", "main")) == 1


def test_source_update_rejects_dirty_checkout_before_challenge(monkeypatch, tmp_path: Path) -> None:
    handler, payload, responses, calls = _fixture(monkeypatch, tmp_path)
    adapter_module = importlib.import_module("execution_adapters.source_update")
    original_git = adapter_module.SystemSourceUpdateEffectAdapter._git

    def dirty_git(root, *args):
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return " M tracked.py"
        return original_git(root, *args)

    monkeypatch.setattr(adapter_module.SystemSourceUpdateEffectAdapter, "_git", staticmethod(dirty_git))
    MODULE.handle_source_update(handler, {**payload, "authorization_action": "challenge"})

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "system_source_update_checkout_dirty"
    assert not any(call[0] == "pull" for call in calls)


def test_source_update_checkout_drift_after_approval_blocks_pull(monkeypatch, tmp_path: Path) -> None:
    handler, payload, responses, calls = _fixture(monkeypatch, tmp_path)
    MODULE.handle_source_update(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_source_update(handler, {
        **payload, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    adapter_module = importlib.import_module("execution_adapters.source_update")
    original_git = adapter_module.SystemSourceUpdateEffectAdapter._git

    def changed_git(root, *args):
        if args == ("rev-parse", "HEAD"):
            return "b" * 40
        return original_git(root, *args)

    monkeypatch.setattr(adapter_module.SystemSourceUpdateEffectAdapter, "_git", staticmethod(changed_git))
    MODULE.handle_source_update(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_operation_mismatch"
    assert not any(call[0] == "pull" for call in calls)

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


API = Path(__file__).resolve().parents[1] / ".bago" / "api"
sys.path.insert(0, str(API))
SPEC = importlib.util.spec_from_file_location("handlers_context_attach_test", API / "handlers_context_attach.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _setup(monkeypatch, tmp_path: Path):
    auth = importlib.import_module("authorization_boundary")
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    session_id = "context-attach-session"
    workspace = tmp_path / "sessions" / session_id / "workspace"
    context_root = tmp_path / "sessions" / session_id / "context"
    (workspace / "docs").mkdir(parents=True)
    (workspace / "docs" / "note.txt").write_text("source", encoding="utf-8")
    manager = SimpleNamespace(
        session_id=session_id,
        base_path=workspace,
        workspace_mirror_root=workspace,
        workspace_context_root=context_root,
        workspace_state_root=workspace / ".gabo",
        workspace_mirror_ready=True,
        _resolve_context_selection=lambda paths: [((workspace / paths[0]).resolve())] if paths else [],
        _mirror_ignore=lambda _directory, names: {
            name for name in names if name.casefold() in {".git", ".gabo", "node_modules", "__pycache__"}
        },
    )
    responses: list[tuple[int, dict]] = []
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(
        serializers, "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )
    return handler, manager, responses


def test_http_context_attach_has_no_effect_until_permit_execution(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    common = {"paths": ["docs"], "interaction_id": "context-attach-http"}

    MODULE.handle(handler, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    assert not manager.workspace_context_root.exists()
    MODULE.handle(handler, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    assert not manager.workspace_context_root.exists()

    MODULE.handle(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "workspace.context.attach"
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    assert Path(responses[-1][1]["data"]["bundle_root"], "docs", "note.txt").read_text(encoding="utf-8") == "source"


def test_http_context_attach_source_change_invalidates_permit_before_copy(monkeypatch, tmp_path: Path) -> None:
    handler, manager, responses = _setup(monkeypatch, tmp_path)
    common = {"paths": ["docs"], "interaction_id": "context-attach-source-change"}

    MODULE.handle(handler, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle(handler, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    (manager.base_path / "docs" / "note.txt").write_text("changed", encoding="utf-8")

    MODULE.handle(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_operation_mismatch"
    assert not manager.workspace_context_root.exists()

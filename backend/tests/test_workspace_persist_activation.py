from __future__ import annotations

import sys
import importlib
from pathlib import Path

import authorization_boundary as auth


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import handlers_workspace  # noqa: E402


def _current_workspace_adapter():
    return importlib.import_module("execution_gateway").WorkspaceBindEffectAdapter


class _DummyHandler:
    command = "POST"
    path = "/workspace/persist"

    def __init__(self) -> None:
        self.headers = {"X-Bago-Channel": "ui-react"}


class _DummyMgr:
    def __init__(self, root: Path) -> None:
        self.session_id = "workspace-session"
        self.project_root = root.resolve()
        self.workspace_id = ""
        self.rebound_to: Path | None = None
        self.save_calls = 0

    @staticmethod
    def _validate_project_root(project_root: Path, *, require_identity: bool = False) -> Path:
        from session_manager import SessionManager

        return SessionManager._validate_project_root(project_root, require_identity=require_identity)

    def rebind_project_root(self, new_project_root: str | Path) -> None:
        self.rebound_to = Path(new_project_root).resolve()
        self.project_root = self.rebound_to

    def save(self) -> None:
        self.save_calls += 1

    def workspace_state(self) -> dict[str, str]:
        return {
            "workspace_state_root": str(self.project_root / ".gabo"),
        }


def _capture_response(monkeypatch):
    import api_serializers

    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )
    return responses


def _valid_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "package.json").write_text("{}", encoding="utf-8")
    return workspace


def test_workspace_persist_requires_challenge_before_rebind(tmp_path, monkeypatch):
    workspace = _valid_workspace(tmp_path)
    current = _valid_workspace(tmp_path / "current")
    mgr = _DummyMgr(current)
    handler = _DummyHandler()
    responses = _capture_response(monkeypatch)
    monkeypatch.setattr(handlers_workspace, "_mgr", lambda _handler: mgr)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    published: list[Path] = []
    adapter = _current_workspace_adapter()
    monkeypatch.setattr(
        adapter,
        "_persist_last_workspace",
        staticmethod(lambda target: published.append(target) or {"receipt_id": "test-last-workspace"}),
    )

    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "challenge",
        "interaction_id": "workspace-interaction",
    })

    assert responses[-1][0] == 200
    challenge = responses[-1][1]["authorization"]["challenge"]
    assert mgr.rebound_to is None
    assert mgr.save_calls == 0
    assert published == []

    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "interaction_id": "workspace-interaction",
        "user_decision": "approve",
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["authorization"]["state"] == "authorized"
    assert mgr.rebound_to is None
    assert mgr.save_calls == 0

    permit = responses[-1][1]["authorization"]["permit"]["token"]
    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "execute",
        "interaction_id": "workspace-interaction",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    result = responses[-1][1]
    assert result["ok"] is True
    assert result["effect_id"] == "workspace.bind"
    assert result["rebound"] is True
    assert result["session_json_persisted"] is True
    assert result["last_workspace_persisted"] is True
    assert "last_workspace_receipt:test-last-workspace" in result["evidence"]
    assert result["receipt_id"].startswith("workspace-bind:sha256:")
    assert mgr.rebound_to == workspace.resolve()
    assert mgr.save_calls == 1
    assert published == [workspace.resolve()]

    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "execute",
        "interaction_id": "workspace-interaction",
        "authorization_permit": permit,
    })
    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_permit_replay"
    assert mgr.save_calls == 1


def test_workspace_persist_blocks_invalid_target_before_rebind(tmp_path, monkeypatch):
    current = _valid_workspace(tmp_path / "current")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    mgr = _DummyMgr(current)
    handler = _DummyHandler()
    responses = _capture_response(monkeypatch)
    monkeypatch.setattr(handlers_workspace, "_mgr", lambda _handler: mgr)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")

    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "execute",
        "authorization_permit": "not-a-permit",
    })

    assert responses[-1][0] == 403
    assert responses[-1][1]["code"] == "workspace_bind_target_invalid"
    assert mgr.rebound_to is None
    assert mgr.save_calls == 0


def test_workspace_persist_is_idempotent_for_current_root(tmp_path, monkeypatch):
    workspace = _valid_workspace(tmp_path)
    mgr = _DummyMgr(workspace)
    handler = _DummyHandler()
    responses = _capture_response(monkeypatch)
    monkeypatch.setattr(handlers_workspace, "_mgr", lambda _handler: mgr)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(
        _current_workspace_adapter(),
        "_persist_last_workspace",
        staticmethod(lambda _target: None),
    )

    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "challenge",
        "interaction_id": "workspace-idempotent",
    })
    challenge = responses[-1][1]["authorization"]["challenge"]
    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "interaction_id": "workspace-idempotent",
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    handlers_workspace.handle_persist(handler, {
        "path": str(workspace),
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["rebound"] is False
    assert mgr.rebound_to is None
    assert mgr.save_calls == 1


def test_workspace_handler_does_not_materialize_rebind_directly():
    source = Path(handlers_workspace.__file__).read_text(encoding="utf-8")

    assert "rebind_project_root(" not in source
    assert "ExecutionGateway(boundary).execute(" in source
    assert "authorization_permit" in source

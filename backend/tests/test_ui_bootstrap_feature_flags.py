from __future__ import annotations

from types import SimpleNamespace

import pytest

from capability_contract import FEATURE_FLAG


class _Config:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def get(self, key: str, default=None):
        if key == f"features.{FEATURE_FLAG}":
            return self.enabled
        return default


class _Manager:
    session_id = "session-bootstrap"
    provider = "ollama-local"
    model = "llama3.2:3b"

    def __init__(self, state_root, enabled: bool) -> None:
        self.state_root = state_root
        self.config = _Config(enabled)
        self.store = SimpleNamespace(
            active_conversation_id="main",
            list_conversations=lambda: [],
            get_history=lambda: [],
        )

    def status(self):
        return {
            "workspace_state": {},
            "welcome_state": {},
            "menu_state": {},
            "workspace_state_root": str(self.state_root),
            "authorized_root": str(self.state_root),
            "repo_root": str(self.state_root),
            "repo_branch": "test",
            "binding_confirmed": True,
        }


@pytest.mark.parametrize("enabled", [False, True])
def test_ui_bootstrap_exposes_capability_anatomy_feature_flag(tmp_path, monkeypatch, enabled):
    import api_routes
    import api_serializers
    import api_state
    import handlers_audit
    import handlers_evidence
    import handlers_jobs
    import handlers_providers
    import handlers_router
    import handlers_ui_bootstrap
    import handlers_workspace

    manager = _Manager(tmp_path, enabled)
    captured = {}

    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(api_serializers, "send_json", lambda _handler, status, payload: captured.update(status=status, payload=payload))
    monkeypatch.setattr(api_routes, "all_routes", lambda: [])
    monkeypatch.setattr(handlers_audit, "_bago_audit", lambda *_args: {})
    monkeypatch.setattr(handlers_audit, "_project_audit", lambda: {})
    monkeypatch.setattr(handlers_evidence, "_evidence_items", lambda _mgr: [])
    monkeypatch.setattr(handlers_jobs, "_job_list", lambda _mgr: [])
    monkeypatch.setattr(handlers_jobs, "_scheduled_jobs", lambda _mgr: [])
    monkeypatch.setattr(handlers_jobs, "_job_summary", lambda _mgr: {})
    monkeypatch.setattr(handlers_providers, "build_providers_payload", lambda _mgr: {})
    monkeypatch.setattr(handlers_router, "_policy_payload", lambda _handler: {})
    monkeypatch.setattr(handlers_workspace, "_workspace_payload", lambda _mgr, _status: {})

    handlers_ui_bootstrap.handle(object())

    assert captured["status"] == 200
    assert captured["payload"]["features"] == {FEATURE_FLAG: enabled}

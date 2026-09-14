from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import commands


class _Closeable:
    def close(self) -> None:
        pass


def test_load_uses_project_root_when_workspace_mirror_is_ready(monkeypatch, tmp_path):
    """`/load` must not turn a transient mirror into the workspace authority."""
    project_root = tmp_path / "project"
    mirror_root = tmp_path / "temporary-session-mirror"
    project_root.mkdir()
    mirror_root.mkdir()
    captured: dict[str, str] = {}

    loaded = SimpleNamespace(
        session_id="restored-session",
        provider="mock",
        model="mock-model",
        system_prompt="",
        bago_mode="B",
        active_bridges=[],
        agent_gateway=SimpleNamespace(),
        store=SimpleNamespace(),
        config=SimpleNamespace(),
        credentials=SimpleNamespace(),
        knowledge=_Closeable(),
        embedding_store=_Closeable(),
        rl_pref=SimpleNamespace(),
        rl_feedback=SimpleNamespace(),
        total_tokens=0,
        total_calls=0,
        last_switch_at=0.0,
        switch_log=[],
        _adapter=None,
        _init_info={},
    )

    def load(session_id: str, *, base_path: str):
        captured["session_id"] = session_id
        captured["base_path"] = base_path
        return loaded

    monkeypatch.setattr(commands.SessionManager, "load", staticmethod(load))
    manager = SimpleNamespace(
        session_id="active-session",
        base_path=mirror_root,
        project_root=project_root,
        workspace_mirror_ready=True,
        knowledge=_Closeable(),
        embedding_store=_Closeable(),
        adapters={"mock": object()},
        invalidate_providers_cache=lambda: None,
    )
    engine = SimpleNamespace(adapters={})

    result = commands.cmd_load(manager, engine, ["restored-session"])

    assert result["ok"] is True
    assert captured == {
        "session_id": "restored-session",
        "base_path": str(project_root),
    }
    assert engine.adapters is manager.adapters

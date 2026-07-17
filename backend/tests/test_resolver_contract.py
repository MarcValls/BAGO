from __future__ import annotations

from pathlib import Path

from bago_core.resolver import resolve_piece, workspace_state_root


def test_resolver_resolves_chat_commands() -> None:
    resolution = resolve_piece("chat.commands")
    assert resolution.path.exists()
    assert resolution.path.name == "commands.py"
    assert resolution.piece_id == "chat.commands"


def test_workspace_root_can_be_overridden(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAGO_WORKSPACE_ROOT", str(tmp_path / "custom"))
    assert workspace_state_root() == (tmp_path / "custom").resolve()

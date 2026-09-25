import json
import builtins
import io
import sys
from pathlib import Path

from _path_helper import ensure_tools_path

ensure_tools_path()
from process_monitor import collect_all, generate_html, main


def test_process_monitor_collects_state_and_generates_html(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / ".bago" / "state"
    sessions = state / "sessions" / "abc123"
    orchestrator = state / "orchestrator"
    rewards = state / "rl"
    sessions.mkdir(parents=True)
    orchestrator.mkdir(parents=True)
    rewards.mkdir(parents=True)
    (state / "llm_start.json").write_text(json.dumps({
        "provider": "ollama-local", "model": "llama3.2:3b", "mode": "chat",
        "started_at": "2025-01-01T12:00:00Z",
    }), encoding="utf-8")
    (sessions / "meta.json").write_text(json.dumps({
        "session_id": "abc123", "provider": "codex", "model": "gpt",
        "turn_count": 7, "created_at": "2025-01-01T12:00:00Z", "status": "closed",
    }), encoding="utf-8")
    (orchestrator / "BRF-001.json").write_text(json.dumps({
        "brief": {"brief_id": "BRF-001", "task_description": "Test task", "domain": "Backend"},
        "current_phase": "execution",
    }), encoding="utf-8")
    (rewards / "rewards.jsonl").write_text(json.dumps({
        "action": "accept", "reward": 1.0, "timestamp": "2025-01-01T12:00:00Z",
    }), encoding="utf-8")

    monkeypatch.setenv("BAGO_STATE_ROOT", str(state))
    snapshot = collect_all(tmp_path)
    html = generate_html(snapshot, refresh=5)
    live_html = generate_html(snapshot, refresh=3, live_port=7890)

    assert snapshot["llm"]["provider"] == "ollama-local"
    assert snapshot["sessions"][0]["turns"] == 7
    assert snapshot["orchestrator"][0]["domain"] == "Backend"
    assert snapshot["rl_rewards"][0]["reward"] == 1.0
    assert "BAGO Process Monitor" in html and "<table>" in html
    assert "fetch('/snapshot')" in live_html


def test_process_monitor_generate_requires_cli_permit_and_writes_through_gateway(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    import authorization_boundary

    state = tmp_path / ".bago" / "state"
    state.mkdir(parents=True)
    monkeypatch.setenv("BAGO_STATE_ROOT", str(state))
    monkeypatch.setattr(authorization_boundary, "state_root", lambda: tmp_path / "auth-state")

    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())
    monkeypatch.setattr(builtins, "input", lambda _prompt: "s")
    output = tmp_path / ".bago" / "monitor.html"

    assert main(["generate", "--root", str(tmp_path), "--out", str(output)]) == 0
    rendered = capsys.readouterr().out
    assert "Autorización CLI requerida" in rendered
    assert "huella:" in rendered
    assert "BAGO Process Monitor" in output.read_text(encoding="utf-8")


def test_process_monitor_generate_rejects_out_of_root_before_write(tmp_path: Path, monkeypatch) -> None:
    import authorization_boundary

    state = tmp_path / ".bago" / "state"
    state.mkdir(parents=True)
    monkeypatch.setenv("BAGO_STATE_ROOT", str(state))
    monkeypatch.setattr(authorization_boundary, "state_root", lambda: tmp_path / "auth-state")

    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())
    monkeypatch.setattr(builtins, "input", lambda _prompt: "s")
    output = tmp_path.parent / f"{tmp_path.name}-outside.html"

    assert main(["generate", "--root", str(tmp_path), "--out", str(output)]) == 1
    assert not output.exists()


def test_process_monitor_generate_blocks_target_drift_after_approval(tmp_path: Path, monkeypatch) -> None:
    import authorization_boundary

    state = tmp_path / ".bago" / "state"
    state.mkdir(parents=True)
    monkeypatch.setenv("BAGO_STATE_ROOT", str(state))
    monkeypatch.setattr(authorization_boundary, "state_root", lambda: tmp_path / "auth-state")

    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())
    monkeypatch.setattr(builtins, "input", lambda _prompt: "s")
    output = tmp_path / ".bago" / "monitor.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("prior report", encoding="utf-8")
    approve = authorization_boundary.AuthorizationBoundary.approve_cli_challenge

    def approve_then_change_target(self, **kwargs):
        decision = approve(self, **kwargs)
        output.write_text("concurrent change", encoding="utf-8")
        return decision

    monkeypatch.setattr(authorization_boundary.AuthorizationBoundary, "approve_cli_challenge", approve_then_change_target)

    assert main(["generate", "--root", str(tmp_path), "--out", str(output)]) == 1
    assert output.read_text(encoding="utf-8") == "concurrent change"

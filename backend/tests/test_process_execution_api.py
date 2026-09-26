from __future__ import annotations

from pathlib import Path

import authorization_boundary as auth
from handlers_process import handle_execute


class _Handler:
    def __init__(self, *, manager, headers=None, server=None):
        self.manager = manager
        self.headers = headers or {}
        self.server = server
        self.response = None


def _send_json(handler, status, payload):
    handler.response = (status, payload)


def test_process_execute_http_requires_challenge_desktop_approval_then_consumes_exact_permit(tmp_path, monkeypatch):
    manager = type("Manager", (), {
        "session_id": "desktop-process-session",
        "base_path": str(tmp_path),
        "framework_root": str(Path(__file__).resolve().parents[1]),
    })()
    handler = _Handler(manager=manager, headers={"X-Bago-Channel": "desktop"})
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)

    import subprocess
    real_run = subprocess.run
    calls = []

    def record_run(*args, **kwargs):
        calls.append((args, kwargs))
        return real_run(*args, **kwargs)

    monkeypatch.setattr("execution_adapters.process.subprocess.run", record_run)
    operation = {"operation": "launcher", "argv": ["--help"], "interaction_id": "desktop-process-1"}
    handle_execute(handler, {**operation, "authorization_action": "challenge"})
    assert handler.response[0] == 200
    challenge = handler.response[1]["authorization"]["challenge"]
    assert challenge["target"]["python_module"] == "bago_core.launcher"
    assert challenge["target"]["cwd"] == str(tmp_path)
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    assert handler.response[0] == 200
    permit = handler.response[1]["authorization"]["permit"]["token"]
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "execute", "authorization_permit": permit,
    })
    assert handler.response[0] == 200
    result = handler.response[1]["process_result"]
    assert result["effect_id"] == "process.execute"
    assert result["executed"] is True
    assert result["exit_code"] == 0
    assert "usage:" in result["stdout"].lower()
    assert handler.response[1]["authorization"]["state"] == "consumed"
    assert len(calls) == 1


def test_process_execute_api_rejects_non_desktop_approval(tmp_path, monkeypatch):
    manager = type("Manager", (), {
        "session_id": "desktop-process-session", "base_path": str(tmp_path),
        "framework_root": str(Path(__file__).resolve().parents[1]),
    })()
    handler = _Handler(manager=manager, headers={"X-Bago-Channel": "ui-react"})
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    operation = {"operation": "launcher", "argv": ["--help"], "interaction_id": "desktop-process-2"}
    handle_execute(handler, {**operation, "authorization_action": "challenge"})
    challenge = handler.response[1]["authorization"]["challenge"]

    handle_execute(handler, {
        **operation, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    assert handler.response[0] == 403
    assert handler.response[1]["code"] == "process_execution_desktop_confirmation_required"


def test_process_inspect_api_uses_server_policy_for_fixed_read_only_command(tmp_path, monkeypatch):
    manager = type("Manager", (), {
        "session_id": "desktop-process-session", "base_path": str(tmp_path),
        "framework_root": str(Path(__file__).resolve().parents[1]),
    })()
    handler = _Handler(manager=manager)
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    calls = []
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda *args, **kwargs: calls.append((args, kwargs)) or type(
            "Completed", (), {"returncode": 0, "stdout": '{"state":"ok"}', "stderr": ""}
        )(),
    )

    handle_execute(handler, {
        "operation": "launcher", "argv": ["node", "status", "--json"],
        "interaction_id": "process-inspect-1", "authorization_action": "challenge",
    })

    assert handler.response[0] == 200
    assert handler.response[1]["read_only"] is True
    assert handler.response[1]["authorization"]["state"] == "server_policy"
    assert handler.response[1]["process_result"]["effect_id"] == "process.inspect"
    assert calls and calls[0][0][0][1:3] == ["-m", "bago_core.launcher"]


def test_process_inspect_api_uses_server_policy_for_fixed_github_reads(tmp_path, monkeypatch):
    manager = type("Manager", (), {
        "session_id": "github-inspect-session", "base_path": str(tmp_path),
        "framework_root": str(Path(__file__).resolve().parents[1]),
    })()
    handler = _Handler(manager=manager)
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    calls = []
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda *args, **kwargs: calls.append((args, kwargs)) or type(
            "Completed", (), {"returncode": 0, "stdout": '{"hosts":{}}', "stderr": ""}
        )(),
    )

    handle_execute(handler, {
        "operation": "github_cli", "argv": ["auth", "status", "--json", "hosts"],
        "interaction_id": "github-inspect-1", "authorization_action": "challenge",
    })

    assert handler.response[0] == 200
    assert handler.response[1]["read_only"] is True
    assert handler.response[1]["process_result"]["effect_id"] == "process.inspect"
    assert calls and Path(calls[0][0][0][0]).name.lower() in {"gh", "gh.exe"}


def test_github_process_api_rejects_unlisted_commands_before_process_execution(tmp_path, monkeypatch):
    manager = type("Manager", (), {
        "session_id": "github-inspect-session", "base_path": str(tmp_path),
        "framework_root": str(Path(__file__).resolve().parents[1]),
    })()
    handler = _Handler(manager=manager)
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    calls = []
    monkeypatch.setattr("execution_adapters.process.subprocess.run", lambda *a, **k: calls.append((a, k)))

    handle_execute(handler, {
        "operation": "github_cli", "argv": ["api", "--method=DELETE", "repos/a/b"],
        "interaction_id": "github-invalid-1", "authorization_action": "challenge",
    })

    assert handler.response[0] == 400
    assert calls == []


def test_supervisor_script_process_requires_consumed_desktop_permit_and_binds_source(tmp_path, monkeypatch):
    manager = type("Manager", (), {
        "session_id": "desktop-process-session", "base_path": str(tmp_path),
        "framework_root": str(Path(__file__).resolve().parents[1]),
    })()
    handler = _Handler(manager=manager, headers={"X-Bago-Channel": "desktop"})
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    calls = []
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda *args, **kwargs: calls.append((args, kwargs)) or type(
            "Completed", (), {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""}
        )(),
    )
    operation = {"operation": "supervisor", "argv": ["status", "--json"], "interaction_id": "supervisor-1"}

    handle_execute(handler, {**operation, "authorization_action": "challenge"})
    challenge = handler.response[1]["authorization"]["challenge"]
    assert challenge["target"]["python_script"] == "scripts/bago_supervisor.py"
    assert challenge["target"]["python_module_sha256"]
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = handler.response[1]["authorization"]["permit"]["token"]
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "execute", "authorization_permit": permit,
    })
    assert handler.response[0] == 200
    assert handler.response[1]["authorization"]["state"] == "consumed"
    assert calls and Path(calls[0][0][0][1]).as_posix().endswith("scripts/bago_supervisor.py")


def test_supervisor_script_source_drift_is_denied_before_spawn(tmp_path, monkeypatch):
    framework_root = tmp_path / "runtime"
    script = framework_root / "scripts" / "bago_supervisor.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('approved')\n", encoding="utf-8")
    manager = type("Manager", (), {
        "session_id": "desktop-process-session", "base_path": str(tmp_path),
        "framework_root": str(framework_root),
    })()
    handler = _Handler(manager=manager, headers={"X-Bago-Channel": "desktop"})
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    calls = []
    monkeypatch.setattr("execution_adapters.process.subprocess.run", lambda *args, **kwargs: calls.append(args))
    operation = {"operation": "supervisor", "argv": ["status", "--json"], "interaction_id": "supervisor-drift"}

    handle_execute(handler, {**operation, "authorization_action": "challenge"})
    challenge = handler.response[1]["authorization"]["challenge"]
    handle_execute(handler, {
        **operation, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = handler.response[1]["authorization"]["permit"]["token"]
    script.write_text("print('changed')\n", encoding="utf-8")

    handle_execute(handler, {
        **operation, "authorization_action": "execute", "authorization_permit": permit,
    })
    assert handler.response[0] == 409
    assert handler.response[1]["code"] == "authorization_operation_mismatch"
    assert calls == []


def test_process_cleanup_requires_strong_desktop_permit_and_dispatches_from_gateway(tmp_path, monkeypatch):
    manager = type("Manager", (), {
        "session_id": "cleanup-session", "base_path": str(tmp_path),
        "framework_root": str(Path(__file__).resolve().parents[1]),
        "state_root": str(tmp_path / "state"),
    })()
    handler = _Handler(manager=manager, headers={"X-Bago-Channel": "desktop"})
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return type("Completed", (), {
            "returncode": 0,
            "stdout": '{"ok":true,"cleaned":1,"matched":[{"pid":99}]}',
            "stderr": "",
        })()

    monkeypatch.setattr("execution_adapters.process.subprocess.run", fake_run)
    operation = {"operation": "cleanup_zombies", "argv": [], "interaction_id": "cleanup-1"}
    handle_execute(handler, {**operation, "authorization_action": "challenge"})
    challenge = handler.response[1]["authorization"]["challenge"]
    assert challenge["effect_id"] == "process.terminate"
    assert challenge["target"]["operation"] == "cleanup_zombies"
    assert challenge["target"]["cleanup_roots"] == sorted({manager.framework_root, manager.state_root})
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = handler.response[1]["authorization"]["permit"]["token"]
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "execute", "authorization_permit": permit,
    })
    assert handler.response[0] == 200
    result = handler.response[1]["process_result"]
    assert result["effect_id"] == "process.terminate"
    assert result["executed"] is True
    assert result["cleaned"] == 1
    assert calls and "Stop-Process" in calls[0][0][-1]


def test_webchat_shutdown_uses_gateway_to_schedule_only_the_current_server_termination(tmp_path, monkeypatch):
    import os
    import sys

    framework_root = Path(__file__).resolve().parents[1]
    manager = type("Manager", (), {
        "session_id": "shutdown-session", "base_path": str(tmp_path),
        "framework_root": str(framework_root), "state_root": str(tmp_path / "state"),
    })()
    handler = _Handler(manager=manager, headers={"X-Bago-Channel": "desktop"}, server=type("HTTPServer", (), {"server_port": 8097})())
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr("api_state.get_mgr", lambda _handler: manager)
    monkeypatch.setattr("api_serializers.send_json", _send_json)
    monkeypatch.setattr(sys, "argv", [
        str(framework_root / "bago_core" / "launcher.py"), "--base-path", str(tmp_path),
        "serve", "--host", "127.0.0.1", "--port", "8097", "--ui-dist", str(framework_root / "ui-react" / "dist"),
    ])
    calls = []
    monkeypatch.setattr("execution_adapters.process.subprocess.Popen", lambda *args, **kwargs: calls.append((args, kwargs)) or type("Child", (), {"pid": 700})())
    operation = {"operation": "stop_webchat", "argv": [], "interaction_id": "shutdown-1"}

    handle_execute(handler, {**operation, "authorization_action": "challenge"})
    challenge = handler.response[1]["authorization"]["challenge"]
    assert challenge["effect_id"] == "process.terminate"
    assert challenge["target"]["operation"] == "stop_webchat"
    assert challenge["target"]["process_id"] == os.getpid()
    assert challenge["target"]["port"] == 8097
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = handler.response[1]["authorization"]["permit"]["token"]
    assert calls == []

    handle_execute(handler, {
        **operation, "authorization_action": "execute", "authorization_permit": permit,
    })
    assert handler.response[0] == 200
    result = handler.response[1]["process_result"]
    assert result["effect_id"] == "process.terminate"
    assert result["termination_scheduled"] is True
    assert calls and "Start-Sleep -Milliseconds 700" in calls[0][0][0][-1]

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


API = Path(__file__).resolve().parents[1] / ".bago" / "api"
CORE = API.parent / "core"
sys.path[:0] = [str(API), str(CORE)]
SPEC = importlib.util.spec_from_file_location("handlers_install_test", API / "handlers_install.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _setup(monkeypatch, tmp_path: Path):
    auth = importlib.import_module("authorization_boundary")
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    adapter = importlib.import_module("execution_adapters.system_install")
    source = tmp_path / "source"
    source.mkdir()
    helper = source / "install-v4.ps1"
    helper.write_text("# fixture installer\n", encoding="utf-8")
    manager = SimpleNamespace(session_id="install-session")
    responses: list[tuple[int, dict]] = []
    launches: list[dict] = []
    handler = SimpleNamespace(headers={"X-Bago-Channel": "desktop"})
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "bago-state")
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, payload: responses.append((status, payload)))
    monkeypatch.setattr(adapter.shutil, "which", lambda _name: "powershell.exe")
    def launch(command, **kwargs):
        ticket_path = Path(command[command.index("-AuthorizationTicketPath") + 1])
        ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
        launches.append({"command": command, "ticket": ticket, **kwargs})
        return SimpleNamespace(pid=1234, wait=lambda: 0)

    monkeypatch.setattr(adapter.subprocess, "Popen", launch)
    payload = {
        "action": "install",
        "source_root": str(source),
        "helper_path": str(helper),
        "install_dir": str(tmp_path / "programs" / "BAGO"),
        "mode": "Express",
        "options": {"no_path_update": True},
        "configuration": {
            "providers": {
                "ollama-local": {"enabled": True, "base_url": "http://127.0.0.1:11434", "model": "llama3.2:3b"},
                "codex": {"enabled": False, "base_url": "https://api.openai.com/v1", "api_key": "secret-install-key", "model": "gpt-5.4-mini"},
                "copilot": {"enabled": False, "base_url": "https://api.githubcopilot.com", "api_key": "", "auth_mode": "device-flow", "model": "gpt-4o-copilot"},
                "ollama-cloud": {"enabled": False, "base_url": "", "api_key": "", "auth_mode": "signin", "model": "llama3.2:3b"},
            },
            "knowledge": {"mode": "none", "path": "", "visibility": "private", "git_init": False},
            "credential_store": {"mode": "session", "path": "", "encrypted": False, "scope": "session"},
        },
        "interaction_id": "install-interaction",
    }
    return handler, manager, responses, launches, payload


def test_install_challenge_is_secret_free_and_has_no_process_effect(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, launches, payload = _setup(monkeypatch, tmp_path)
    MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})

    assert responses[-1][0] == 200
    assert responses[-1][1]["authorization"]["challenge"]["effect_id"] == "system.install.apply"
    assert "secret-install-key" not in json.dumps(responses[-1][1])
    assert launches == []
    assert not (tmp_path / "bago-state" / "authorization" / "install-tickets").exists()


def test_install_execute_consumes_exact_permit_and_tickets_helper(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, launches, payload = _setup(monkeypatch, tmp_path)
    MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "system.install.apply"
    assert responses[-1][1]["status"] == "completed"
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    command = launches[-1]["command"]
    ticket = launches[-1]["ticket"]
    assert ticket["effect_id"] == "system.install.apply"
    assert ticket["target"]["helper_sha256"]
    assert ticket["configuration"]["providers"]["codex"]["api_key"] == "secret-install-key"
    assert "secret-install-key" not in json.dumps(ticket["target"])
    assert "-NoPathUpdate" in command
    assert not Path(command[command.index("-AuthorizationTicketPath") + 1]).exists()


def test_install_gateway_supports_electron_lifecycle_actions_before_helper_launch(monkeypatch, tmp_path: Path) -> None:
    for index, action in enumerate(("install", "repair", "reinstall", "new-copy")):
        case_root = tmp_path / str(index)
        case_root.mkdir()
        handler, _manager, responses, launches, payload = _setup(monkeypatch, case_root)
        payload["action"] = action
        MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})
        challenge = responses[-1][1]["authorization"]["challenge"]
        MODULE.handle_apply(handler, {
            **payload,
            "authorization_action": "approve",
            "challenge_id": challenge["challenge_id"],
            "user_decision": "approve",
        })
        permit = responses[-1][1]["authorization"]["permit"]["token"]
        MODULE.handle_apply(handler, {
            **payload,
            "authorization_action": "execute",
            "authorization_permit": permit,
        })
        assert responses[-1][0] == 200
        assert launches[-1]["ticket"]["target"]["action"] == action
        command = launches[-1]["command"]
        assert ("-RepairOnly" in command) is (action == "repair")


def test_install_changed_helper_rejects_before_ticket_or_process(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, launches, payload = _setup(monkeypatch, tmp_path)
    MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    Path(payload["helper_path"]).write_text("# changed helper\n", encoding="utf-8")

    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_operation_mismatch"
    assert launches == []
    assert not (tmp_path / "bago-state" / "authorization" / "install-tickets").exists()


def test_install_nonzero_helper_exit_is_not_reported_as_completed(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, _launches, payload = _setup(monkeypatch, tmp_path)
    MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    adapter = importlib.import_module("execution_adapters.system_install")
    monkeypatch.setattr(
        adapter.subprocess,
        "Popen",
        lambda command, **kwargs: SimpleNamespace(pid=1234, wait=lambda: 7),
    )

    MODULE.handle_apply(handler, {
        **payload,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 500
    assert responses[-1][1]["code"] == "system_install_process_failed"
    ticket_dir = tmp_path / "bago-state" / "authorization" / "install-tickets"
    assert list(ticket_dir.iterdir()) == []


def test_release_install_copies_backup_without_moving_live_configuration(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, _launches, payload = _setup(monkeypatch, tmp_path)
    payload["action"] = "release-job"
    install_dir = Path(payload["install_dir"])
    install_dir.mkdir(parents=True)
    config_path = install_dir / ".bago" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text('{"providers":{"codex":{"enabled":true}}}', encoding="utf-8")
    adapter = importlib.import_module("execution_adapters.system_install")
    launches: list[dict] = []

    def launch(command, **kwargs):
        assert config_path.is_file(), "the live configuration must remain in place through gateway backup"
        backup_path = Path(f"{install_dir}.bago-rollback-{command[command.index('-PermitId') + 1]}")
        assert (backup_path / ".bago" / "config.json").read_bytes() == config_path.read_bytes()
        launches.append({"command": command, "backup_path": backup_path})
        return SimpleNamespace(pid=4321, wait=lambda: 0)

    monkeypatch.setattr(adapter.subprocess, "Popen", launch)
    MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_apply(handler, {
        **payload, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    MODULE.handle_apply(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["backup_path"] == str(launches[-1]["backup_path"])
    assert config_path.is_file()
    assert "-GatewayBackupProvided" in launches[-1]["command"]


def test_failed_release_install_restores_gateway_backup_before_error(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, _launches, payload = _setup(monkeypatch, tmp_path)
    payload["action"] = "release-job"
    install_dir = Path(payload["install_dir"])
    install_dir.mkdir(parents=True)
    config_path = install_dir / ".bago" / "config.json"
    config_path.parent.mkdir()
    original_config = b'{"providers":{"codex":{"enabled":true}}}'
    config_path.write_bytes(original_config)
    adapter = importlib.import_module("execution_adapters.system_install")
    permit_id = ""

    def launch(command, **kwargs):
        nonlocal permit_id
        permit_id = command[command.index("-PermitId") + 1]
        config_path.write_text('{"broken":true}', encoding="utf-8")
        return SimpleNamespace(pid=9876, wait=lambda: 7)

    monkeypatch.setattr(adapter.subprocess, "Popen", launch)
    MODULE.handle_apply(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_apply(handler, {
        **payload, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    MODULE.handle_apply(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })

    failed_path = Path(f"{install_dir}.bago-failed-{permit_id}")
    assert responses[-1][0] == 500
    assert responses[-1][1]["code"] == "system_install_process_failed"
    assert config_path.read_bytes() == original_config
    assert failed_path.exists()
    assert not Path(f"{install_dir}.bago-rollback-{permit_id}").exists()


def test_manual_release_rollback_is_strong_permit_gateway_effect(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, _launches, _payload = _setup(monkeypatch, tmp_path)
    install_dir = tmp_path / "programs" / "BAGO"
    install_dir.mkdir(parents=True)
    (install_dir / "current.txt").write_text("new runtime", encoding="utf-8")
    backup = Path(f"{install_dir}.bago-rollback-permit-install123")
    backup.mkdir()
    (backup / "previous.txt").write_text("old runtime", encoding="utf-8")
    displaced = Path(f"{install_dir}.bago-replaced-job_123")
    payload = {
        "install_dir": str(install_dir),
        "backup_path": str(backup),
        "displaced_path": str(displaced),
        "interaction_id": "rollback-interaction",
    }

    MODULE.handle_rollback(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    assert challenge["effect_id"] == "system.install.rollback"
    assert (install_dir / "current.txt").is_file(), "challenge must not move runtime data"
    assert (backup / "previous.txt").is_file()

    MODULE.handle_rollback(handler, {
        **payload, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    MODULE.handle_rollback(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "system.install.rollback"
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    assert (install_dir / "previous.txt").read_text(encoding="utf-8") == "old runtime"
    assert (displaced / "current.txt").read_text(encoding="utf-8") == "new runtime"
    assert not backup.exists()


def test_release_rollback_rejects_non_gateway_backup_before_effect(monkeypatch, tmp_path: Path) -> None:
    handler, _manager, responses, _launches, _payload = _setup(monkeypatch, tmp_path)
    install_dir = tmp_path / "programs" / "BAGO"
    install_dir.mkdir(parents=True)
    (install_dir / "current.txt").write_text("new runtime", encoding="utf-8")
    backup = tmp_path / "unrelated-backup"
    backup.mkdir()
    payload = {
        "install_dir": str(install_dir),
        "backup_path": str(backup),
        "displaced_path": str(tmp_path / "programs" / "BAGO.bago-replaced-job_456"),
        "interaction_id": "rollback-invalid-interaction",
    }
    MODULE.handle_rollback(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_rollback(handler, {
        **payload, "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"], "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    MODULE.handle_rollback(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })
    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "system_install_rollback_path_invalid"
    assert (install_dir / "current.txt").is_file()
    assert backup.is_dir()


def test_install_helper_rejects_missing_authorization_before_self_elevation() -> None:
    if os.name != "nt":
        return
    powershell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
    if not powershell:
        return
    installer = Path(__file__).resolve().parents[1] / "install-v4.ps1"

    result = subprocess.run(
        [powershell, "-NoProfile", "-File", str(installer)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "requiere autorización de ExecutionGateway" in output

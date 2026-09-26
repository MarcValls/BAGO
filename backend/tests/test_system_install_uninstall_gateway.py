from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

API = Path(__file__).resolve().parents[1] / ".bago" / "api"
CORE = API.parent / "core"
sys.path[:0] = [str(API), str(CORE)]
SPEC = importlib.util.spec_from_file_location("handlers_install_uninstall_test", API / "handlers_install.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _setup(monkeypatch, tmp_path: Path):
    auth = importlib.import_module("authorization_boundary")
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    adapter_module = importlib.import_module("execution_adapters.system_install_uninstall")
    install = tmp_path / "installed-bago"
    (install / "bago_core").mkdir(parents=True)
    (install / "bago_core" / "cli.py").write_text("# fixture cli\n", encoding="utf-8")
    (install / "runtime.py").write_text("payload\n", encoding="utf-8")
    responses: list[tuple[int, dict]] = []
    runs: list[dict] = []
    manager = SimpleNamespace(session_id="uninstall-session")
    handler = SimpleNamespace(headers={"X-Bago-Channel": "desktop"})
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "state")
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setenv("BAGO_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("BAGO_DATA_ROOT", str(tmp_path / "program-data"))
    lifecycle = importlib.import_module("execution_adapters.install_uninstall_lifecycle")
    monkeypatch.setattr(lifecycle, "_remove_install_from_path", lambda _path: "test")
    monkeypatch.setattr(lifecycle, "_remove_bago_explorer_context_menu", lambda: False)

    def run(command, **kwargs):
        ticket = json.loads(Path(command[command.index("--authorization-ticket-path") + 1]).read_text(encoding="utf-8"))
        values = {}
        for index, value in enumerate(command[:-1]):
            if value.startswith("--"):
                values[value[2:].replace("-", "_")] = command[index + 1]
        args = Namespace(**values)
        args.purge_state = "--purge-state" in command
        args.elevated_child = False
        from execution_adapters.install_uninstall_lifecycle import run_authorized_uninstall
        exit_code = run_authorized_uninstall(args)
        runs.append({"command": command, "kwargs": kwargs, "ticket": ticket, "exit_code": exit_code})
        return SimpleNamespace(returncode=exit_code, stdout="Backup creado: fixture.zip", stderr="")

    monkeypatch.setattr(adapter_module.subprocess, "run", run)
    payload = {"install_dir": str(install), "purge_state": False, "interaction_id": "uninstall-interaction"}
    return handler, payload, responses, runs, install


def _approve(handler, payload, responses):
    MODULE.handle_uninstall(handler, {**payload, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    MODULE.handle_uninstall(handler, {
        **payload, "authorization_action": "approve", "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    return responses[-1][1]["authorization"]["permit"]["token"]


def test_uninstall_challenge_is_pre_effect_and_binds_tree_and_purge(monkeypatch, tmp_path: Path) -> None:
    handler, payload, responses, runs, _install = _setup(monkeypatch, tmp_path)
    MODULE.handle_uninstall(handler, {**payload, "authorization_action": "challenge"})

    assert responses[-1][0] == 200
    target = responses[-1][1]["authorization"]["challenge"]["target"]
    assert target["schema"] == "bago.system-install-uninstall-plan.v1"
    assert target["tree_sha256"]
    assert target["cli_sha256"]
    assert target["purge_state"] is False
    assert runs == []


def test_uninstall_consumes_desktop_permit_and_launches_one_use_ticket(monkeypatch, tmp_path: Path) -> None:
    handler, payload, responses, runs, install = _setup(monkeypatch, tmp_path)
    permit = _approve(handler, payload, responses)
    MODULE.handle_uninstall(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "system.install.uninstall"
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    assert runs[0]["ticket"]["effect_id"] == "system.install.uninstall"
    assert runs[0]["ticket"]["target"]["install_dir"] == str(install.resolve())
    assert runs[0]["exit_code"] == 0
    assert not install.exists()
    backups = list((tmp_path / "program-data" / "BAGO" / "backups").glob("*.zip"))
    assert len(backups) == 1
    ticket_path = Path(runs[0]["command"][runs[0]["command"].index("--authorization-ticket-path") + 1])
    assert not ticket_path.exists()


def test_uninstall_target_drift_blocks_before_helper_launch(monkeypatch, tmp_path: Path) -> None:
    handler, payload, responses, runs, install = _setup(monkeypatch, tmp_path)
    permit = _approve(handler, payload, responses)
    (install / "runtime.py").write_text("changed after approval\n", encoding="utf-8")
    MODULE.handle_uninstall(handler, {
        **payload, "authorization_action": "execute", "authorization_permit": permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_operation_mismatch"
    assert runs == []


def test_cli_uninstall_without_gateway_ticket_fails_before_mutation(tmp_path: Path) -> None:
    from bago_core.commands.cmd_lifecycle import cmd_uninstall

    install = tmp_path / "installed-bago"
    install.mkdir()
    sentinel = install / "preserve.txt"
    sentinel.write_text("still here", encoding="utf-8")
    args = Namespace(
        install_dir=str(install), backup_root=str(tmp_path / "backups"),
        user_state_dir=str(tmp_path / "user"), purge_state=False,
        authorization_ticket_path="", authorization_ticket_nonce="",
        authorization_permit_id="", authorization_ledger_path="",
        elevated_child=False,
    )

    assert cmd_uninstall(args) == 1
    assert sentinel.read_text(encoding="utf-8") == "still here"
    assert not (tmp_path / "backups").exists()

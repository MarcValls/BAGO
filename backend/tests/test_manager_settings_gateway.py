from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

CORE = Path(__file__).resolve().parents[1] / ".bago" / "core"
API = CORE.parent / "api"
sys.path[:0] = [str(CORE), str(API)]
_SPEC = importlib.util.spec_from_file_location("manager_settings_handler_test", API / "handlers_manager_settings.py")
_HANDLER_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_HANDLER_MODULE)


def _execute(operation, tmp_path: Path, *, authorized: bool = True):
    from execution_adapter_contract import ExecutionContext
    from execution_adapters.manager_settings import ManagerSettingsWriteEffectAdapter
    from execution_request import build_execution_request

    manager = SimpleNamespace(session_id="manager-settings-session")
    target = ManagerSettingsWriteEffectAdapter.prepare_target(operation)
    request = build_execution_request(
        effect_id="manager.settings.write", actor_kind="user",
        principal_id="interactive-local-user", session_id=manager.session_id,
        source_surface="api.manager.settings.write", target=target,
        arguments=operation, scope="persistent",
    )
    authorization = {
        "state": "consumed", "effect_id": request.effect_id,
        "operation_fingerprint": request.fingerprint, "session_id": request.session_id,
    } if authorized else {}
    result = ManagerSettingsWriteEffectAdapter().execute(
        request, ExecutionContext(manager=manager, services={"_authorization": authorization})
    )
    return result, Path(target["path"])


def test_install_selection_is_written_to_canonical_user_root_after_consumed_permit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    install = tmp_path / "install"
    launcher = install / "bago_core" / "launcher.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("# trusted fixture\n", encoding="utf-8")

    result, target = _execute({"resource": "install_selection", "role": "active", "install_dir": str(install)}, tmp_path)

    import json
    selection = json.loads(target.read_text(encoding="utf-8"))
    assert result["effect_id"] == "manager.settings.write"
    assert selection["roles"]["active"]["path"] == str(install.resolve())


def test_manager_settings_direct_call_without_consumed_permit_fails_before_write(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    install = tmp_path / "install"
    (install / "bago_core").mkdir(parents=True)
    (install / "bago_core" / "launcher.py").write_text("# fixture\n", encoding="utf-8")
    operation = {"resource": "install_selection", "role": "launch", "install_dir": str(install)}

    try:
        _execute(operation, tmp_path, authorized=False)
    except Exception as exc:
        assert getattr(exc, "code", "") == "manager_settings_authorization_required"
    else:
        raise AssertionError("Unauthorised manager settings write was accepted")
    assert not (tmp_path / "user" / "install_selection.json").exists()


def test_chain_registry_digest_binds_persisted_array(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    chains = [{"id": "chain-1", "name": "Review", "stages": [{"id": "stage-1", "steps": []}]}]
    result, target = _execute({"resource": "chain_registry", "chains": chains}, tmp_path)

    import json
    stored = json.loads(target.read_text(encoding="utf-8"))
    assert result["resource"] == "chain_registry"
    assert stored["chains"] == chains


def test_manager_settings_http_flow_consumes_desktop_permit(monkeypatch, tmp_path: Path) -> None:
    api_state = importlib.import_module("api_state")
    serializers = importlib.import_module("api_serializers")
    manager = SimpleNamespace(session_id="manager-settings-api-session")
    handler = SimpleNamespace(headers={"X-Bago-Channel": "desktop"})
    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(api_state, "get_mgr", lambda _handler: manager)
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, body: responses.append((status, body)))
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    monkeypatch.setenv("BAGO_STATE_ROOT", str(tmp_path / "state"))
    install = tmp_path / "install"
    (install / "bago_core").mkdir(parents=True)
    (install / "bago_core" / "launcher.py").write_text("# fixture\n", encoding="utf-8")
    base = {"resource": "install_selection", "role": "active", "install_dir": str(install), "interaction_id": "selection-ui-1"}

    _HANDLER_MODULE.handle_write(handler, {**base, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    _HANDLER_MODULE.handle_write(handler, {
        **base, "authorization_action": "approve", "challenge_id": challenge["challenge_id"], "user_decision": "approve"
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    _HANDLER_MODULE.handle_write(handler, {**base, "authorization_action": "execute", "authorization_permit": permit})

    assert responses[-1][0] == 200
    assert responses[-1][1]["effect_id"] == "manager.settings.write"
    assert responses[-1][1]["authorization"]["state"] == "consumed"
    assert (tmp_path / "user" / "install_selection.json").is_file()

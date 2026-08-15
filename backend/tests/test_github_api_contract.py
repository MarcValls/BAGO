from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def test_connect_persists_repo_atomically(tmp_path, monkeypatch) -> None:
    import api_serializers
    import handlers_github

    captured = {}
    monkeypatch.setattr(handlers_github, "_state", lambda _handler: tmp_path)
    monkeypatch.setattr(handlers_github, "_run_gh", lambda _args: (0, '{"full_name":"openai/bago"}', ""))
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: captured.update(status=status, payload=payload),
    )

    handlers_github.handle_connect(object(), {"repo": "openai/bago"})

    assert captured["status"] == 200
    assert handlers_github._saved_repo(tmp_path) == "openai/bago"
    assert list(tmp_path.glob("*.tmp")) == []


def test_connect_error_has_machine_readable_code(monkeypatch) -> None:
    import api_serializers
    import handlers_github

    captured = {}
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: captured.update(status=status, payload=payload),
    )

    handlers_github.handle_connect(object(), {"repo": "not valid"})

    assert captured["status"] == 400
    assert captured["payload"]["ok"] is False
    assert captured["payload"]["error_code"] == "invalid_repository"


def test_cli_adapter_never_uses_shell(monkeypatch) -> None:
    import github_cli

    seen = {}

    class Process:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    def fake_run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return Process()

    monkeypatch.setattr(github_cli.subprocess, "run", fake_run)
    result = github_cli.GitHubCliAdapter().run(["auth", "status"])

    assert result.stdout == "ok"
    assert seen["command"] == ["gh", "auth", "status"]
    assert seen["kwargs"]["shell"] is False


def test_cli_adapter_reports_missing_executable(monkeypatch) -> None:
    import github_cli

    def missing(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(github_cli.subprocess, "run", missing)
    result = github_cli.GitHubCliAdapter().run(["auth", "status"])
    assert result.returncode == 127
    assert result.stderr == "gh no está instalado"


def test_cli_adapter_reports_timeout(monkeypatch) -> None:
    import github_cli

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["gh"], timeout=30)

    monkeypatch.setattr(github_cli.subprocess, "run", timeout)
    result = github_cli.GitHubCliAdapter().run(["auth", "status"])
    assert result.returncode == 124
    assert "demasiado" in result.stderr


def test_github_handler_finds_per_user_windows_install(tmp_path, monkeypatch) -> None:
    import handlers_github

    executable = tmp_path / "Programs" / "GitHub CLI" / "gh.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    monkeypatch.setattr(handlers_github.shutil, "which", lambda _name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "missing"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "missing-user"))

    assert handlers_github._gh_executable() == str(executable)


def test_github_handler_falls_back_to_home_when_env_is_missing(tmp_path, monkeypatch) -> None:
    import handlers_github

    executable = tmp_path / "AppData" / "Local" / "Programs" / "GitHub CLI" / "gh.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    monkeypatch.setattr(handlers_github.shutil, "which", lambda _name: None)
    monkeypatch.setattr(handlers_github.Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "missing"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "missing-user"))

    assert handlers_github._gh_executable() == str(executable)


def test_api_dispatch_uses_rich_github_auth_contract(monkeypatch) -> None:
    import api_dispatch

    called: list[str] = []
    module = SimpleNamespace(
        handle_github_status=lambda _handler: called.append("status"),
        handle_github_auth_start=lambda _handler, _body: called.append("start"),
        handle_github_auth_refresh=lambda _handler, _body: called.append("refresh"),
        handle_github_auth_logout=lambda _handler, _body: called.append("logout"),
    )
    monkeypatch.setattr(api_dispatch.importlib, "import_module", lambda _name: module)

    api_dispatch.GET_ROUTES["/github/status"](object())
    api_dispatch.POST_ROUTES["/github/auth/start"](object(), {})
    api_dispatch.POST_ROUTES["/github/auth/refresh"](object(), {})
    api_dispatch.POST_ROUTES["/github/auth/logout"](object(), {})

    assert called == ["status", "start", "refresh", "logout"]


def test_connect_maps_auth_failure_to_stable_error(monkeypatch) -> None:
    import api_serializers
    import handlers_github

    captured = {}
    monkeypatch.setattr(handlers_github, "_run_gh", lambda _args: (4, "", "login required"))
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: captured.update(status=status, payload=payload),
    )
    handlers_github.handle_connect(object(), {"repo": "openai/bago"})
    assert captured["status"] == 403
    assert captured["payload"]["error_code"] == "github_repository_unavailable"


def test_connect_rejects_invalid_github_json(monkeypatch) -> None:
    import api_serializers
    import handlers_github

    captured = {}
    monkeypatch.setattr(handlers_github, "_run_gh", lambda _args: (0, "not-json", ""))
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: captured.update(status=status, payload=payload),
    )
    handlers_github.handle_connect(object(), {"repo": "openai/bago"})
    assert captured["status"] == 502
    assert captured["payload"]["error_code"] == "github_invalid_response"

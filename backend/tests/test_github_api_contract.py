from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def test_connect_persists_repo_atomically(tmp_path, monkeypatch) -> None:
    import api_serializers
    import handlers_github

    captured = {}
    state_root = tmp_path / "created-by-state-writer" / "state"
    monkeypatch.setattr(handlers_github, "_state", lambda _handler: state_root)
    monkeypatch.setattr(handlers_github, "_run_gh", lambda _handler, _args: (0, '{"full_name":"openai/bago"}', ""))
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: captured.update(status=status, payload=payload),
    )

    handlers_github.handle_connect(object(), {"repo": "openai/bago"})

    assert captured["status"] == 200
    assert handlers_github._saved_repo(state_root) == "openai/bago"
    assert list(state_root.glob("*.tmp")) == []


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


def test_connect_maps_auth_failure_to_stable_error(monkeypatch) -> None:
    import api_serializers
    import handlers_github

    captured = {}
    monkeypatch.setattr(handlers_github, "_run_gh", lambda _handler, _args: (4, "", "login required"))
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
    monkeypatch.setattr(handlers_github, "_run_gh", lambda _handler, _args: (0, "not-json", ""))
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: captured.update(status=status, payload=payload),
    )
    handlers_github.handle_connect(object(), {"repo": "openai/bago"})
    assert captured["status"] == 502
    assert captured["payload"]["error_code"] == "github_invalid_response"


def test_github_mutation_http_facades_fail_closed_for_desktop_gateway(monkeypatch) -> None:
    import api_serializers
    import handlers_github

    captured = []
    monkeypatch.setattr(api_serializers, "send_json", lambda _handler, status, payload: captured.append((status, payload)))
    handler = object()
    for endpoint in (
        handlers_github.handle_create,
        handlers_github.handle_mcp_create,
        handlers_github.handle_github_auth_start,
        handlers_github.handle_github_auth_logout,
        handlers_github.handle_github_setup_git,
    ):
        endpoint(handler, {})

    assert len(captured) == 5
    assert all(status == 410 for status, _payload in captured)

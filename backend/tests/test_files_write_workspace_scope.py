from __future__ import annotations

from types import SimpleNamespace


def _authorized_write(handle_write, handler, path: str, content: str, responses: list[tuple[int, dict]]):
    interaction_id = "interaction-files-write"
    handle_write(
        handler,
        {
            "path": path,
            "content": content,
            "authorization_action": "challenge",
            "interaction_id": interaction_id,
        },
    )
    challenge = responses[-1][1]["authorization"]["challenge"]
    handle_write(
        handler,
        {
            "path": path,
            "content": content,
            "authorization_action": "approve",
            "challenge_id": challenge["challenge_id"],
            "interaction_id": interaction_id,
            "user_decision": "approve",
        },
    )
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    handle_write(
        handler,
        {
            "path": path,
            "content": content,
            "authorization_action": "execute",
            "authorization_permit": permit,
        },
    )


def test_workspace_namespaced_write_uses_workspace_scope(tmp_path, monkeypatch):
    import api_serializers
    import authorization_boundary as auth
    from handlers_files import handle_write

    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")

    workspace_root = tmp_path / "mirror"
    workspace_root.mkdir()
    manager = SimpleNamespace(
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=workspace_root,
        base_path=workspace_root,
        workspace_id="workspace-test",
        session_id="session-files-test",
    )
    handler = SimpleNamespace(session_mgr=manager, path="/files/write", headers={"X-Bago-Channel": "ui-react"})

    _authorized_write(handle_write, handler, "workspace/note.txt", "hola", responses)

    assert responses[-1][0] == 200
    payload = responses[-1][1]
    assert payload["ok"] is True
    assert payload["path"].endswith("note.txt")
    assert payload["project_root"] == str(workspace_root)
    assert (workspace_root / "note.txt").read_text(encoding="utf-8") == "hola"


def test_plain_write_keeps_explicit_temp_project_root_out_of_runtime_cwd(tmp_path, monkeypatch):
    import api_serializers
    import authorization_boundary as auth
    from handlers_files import handle_write

    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")

    project_root = tmp_path / "selected-project"
    runtime_root = tmp_path / "runtime"
    project_root.mkdir()
    runtime_root.mkdir()
    monkeypatch.chdir(runtime_root)
    manager = SimpleNamespace(
        project_root=project_root,
        workspace_scope_root=project_root,
        workspace_mirror_root=tmp_path / "mirror",
        base_path=project_root,
        workspace_id="workspace-temp-project",
        session_id="session-files-test",
    )
    handler = SimpleNamespace(session_mgr=manager, path="/files/write", headers={"X-Bago-Channel": "ui-react"})

    relative = ".bago/context/context-tree.json"
    _authorized_write(handle_write, handler, relative, "{}", responses)

    assert responses[-1][0] == 200
    assert responses[-1][1]["project_root"] == str(project_root)
    assert (project_root / relative).read_text(encoding="utf-8") == "{}"
    assert not (runtime_root / relative).exists()


def test_write_without_gateway_permit_is_fail_closed(tmp_path, monkeypatch):
    import api_serializers
    import authorization_boundary as auth
    from handlers_files import handle_write

    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    manager = SimpleNamespace(
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=tmp_path,
        base_path=tmp_path,
        session_id="session-files-test",
    )
    handler = SimpleNamespace(session_mgr=manager, path="/files/write", headers={"X-Bago-Channel": "ui-react"})

    handle_write(handler, {"path": "blocked.txt", "content": "no permit"})

    assert responses[-1][0] == 403
    assert responses[-1][1]["code"] == "authorization_permit_required"
    assert not (tmp_path / "blocked.txt").exists()

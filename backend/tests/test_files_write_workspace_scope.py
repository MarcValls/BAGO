from __future__ import annotations

from types import SimpleNamespace


def test_workspace_namespaced_write_uses_workspace_scope(tmp_path, monkeypatch):
    import api_serializers
    from handlers_files import handle_write

    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )

    workspace_root = tmp_path / "mirror"
    workspace_root.mkdir()
    manager = SimpleNamespace(
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=workspace_root,
        base_path=workspace_root,
        workspace_id="workspace-test",
    )
    handler = SimpleNamespace(session_mgr=manager, path="/files/write")

    handle_write(handler, {"path": "workspace/note.txt", "content": "hola"})

    assert responses[-1][0] == 200
    payload = responses[-1][1]
    assert payload["ok"] is True
    assert payload["path"].endswith("note.txt")
    assert payload["project_root"] == str(workspace_root)
    assert (workspace_root / "note.txt").read_text(encoding="utf-8") == "hola"

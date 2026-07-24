from __future__ import annotations

from types import SimpleNamespace


def test_missing_file_is_empty_only_when_explicitly_optional(tmp_path, monkeypatch):
    import api_serializers
    from handlers_files import handle_read

    responses: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        api_serializers,
        "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )
    manager = SimpleNamespace(
        workspace_mirror_root=tmp_path,
        project_root=tmp_path,
        workspace_id="workspace-test",
        config=None,
    )
    handler = SimpleNamespace(
        session_mgr=manager,
        path="/files/read/.bago/context/context-tree.json?optional=1",
    )

    handle_read(handler, ".bago/context/context-tree.json")

    assert responses[-1][0] == 200
    assert responses[-1][1]["ok"] is True
    assert responses[-1][1]["exists"] is False
    assert responses[-1][1]["content"] == ""

    handler.path = "/files/read/.bago/context/context-tree.json"
    handle_read(handler, ".bago/context/context-tree.json")

    assert responses[-1][0] == 404
    assert responses[-1][1]["error_code"] == "FILE_NOT_FOUND"

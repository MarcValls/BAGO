from __future__ import annotations


def test_session_git_info_uses_gateway_read_only_inspections(monkeypatch, tmp_path) -> None:
    from session_persistence_mixin import SessionPersistenceMixin

    calls = []

    def inspect(executable, argv, *, cwd, manager, timeout):
        calls.append((executable, argv, cwd, manager, timeout))
        output = str(tmp_path) if argv[-1] == "--show-toplevel" else "main"
        return {"exit_code": 0, "stdout": output}

    monkeypatch.setattr("session_persistence_mixin.inspect_process", inspect)
    manager = type(
        "Manager",
        (SessionPersistenceMixin,),
        {"base_path": str(tmp_path), "project_root": str(tmp_path), "session_id": "session-git-1"},
    )()

    assert manager._git_info() == (str(tmp_path), "main")
    assert [call[1] for call in calls] == [
        ["rev-parse", "--show-toplevel"],
        ["rev-parse", "--abbrev-ref", "HEAD"],
    ]
    assert all(call[0] == "git" and call[2] == str(tmp_path) and call[3] is manager for call in calls)

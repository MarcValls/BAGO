from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import handlers_workspace  # noqa: E402


class _DummyMgr:
    def __init__(self) -> None:
        self.rebound_to: Path | None = None
        self.save_calls = 0

    def rebind_project_root(self, new_project_root: str | Path) -> None:
        self.rebound_to = Path(new_project_root)

    def save(self) -> None:
        self.save_calls += 1


def test_persist_workspace_rebinds_current_session(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "package.json").write_text("{}", encoding="utf-8")

    saved: dict[str, str] = {}

    def _capture(path: str) -> None:
        saved["path"] = path

    monkeypatch.setattr(handlers_workspace, "_save_last_workspace", _capture)

    mgr = _DummyMgr()
    result = handlers_workspace._persist_workspace(mgr, str(workspace))

    assert result["ok"] is True
    assert result["saved"] == str(workspace.resolve())
    assert mgr.rebound_to == workspace.resolve()
    assert mgr.save_calls == 1
    assert saved["path"] == str(workspace.resolve())


def test_persist_workspace_does_not_publish_last_path_when_save_fails(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "package.json").write_text("{}", encoding="utf-8")

    published: list[str] = []
    monkeypatch.setattr(handlers_workspace, "_save_last_workspace", published.append)

    class _FailingMgr(_DummyMgr):
        def save(self) -> None:
            raise OSError("disk full")

    result = handlers_workspace._persist_workspace(_FailingMgr(), str(workspace))

    assert result["ok"] is False
    assert "no pudo persistirse" in result["error"]
    assert published == []

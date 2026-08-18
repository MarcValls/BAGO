from __future__ import annotations

import sys
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import handlers_workspace  # noqa: E402


class _Handler:
    def __init__(self, path: str, client_address: tuple[str, int], session_mgr) -> None:
        self.path = path
        self.client_address = client_address
        self.session_mgr = session_mgr
        self.wfile = BytesIO()
        self.status = 0

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, *_args) -> None:
        pass

    def _send_cors_headers(self) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def payload(self):
        return json.loads(self.wfile.getvalue().decode("utf-8"))


def test_browse_lists_only_visible_directories(tmp_path):
    (tmp_path / "Alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "readme.txt").write_text("x", encoding="utf-8")
    handler = _Handler(f"/workspace/browse?{urlencode({'path': str(tmp_path)})}", ("127.0.0.1", 43210), SimpleNamespace(project_root=str(tmp_path), base_path=str(tmp_path)))

    handlers_workspace.handle_browse(handler)

    assert handler.status == 200
    payload = handler.payload()
    assert payload["ok"] is True
    assert payload["path"] == str(tmp_path.resolve())
    assert [item["name"] for item in payload["directories"]] == ["Alpha", "beta"]
    assert payload["parent"] == str(tmp_path.resolve().parent)
    assert payload["breadcrumbs"][-1]["path"] == str(tmp_path.resolve())


def test_browse_rejects_non_loopback_clients(tmp_path):
    handler = _Handler(f"/workspace/browse?{urlencode({'path': str(tmp_path)})}", ("192.0.2.10", 43210), SimpleNamespace(project_root=str(tmp_path), base_path=str(tmp_path)))

    handlers_workspace.handle_browse(handler)

    assert handler.status == 403
    assert handler.payload()["error_code"] == "workspace_browse_local_only"

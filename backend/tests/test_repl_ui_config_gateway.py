from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND = Path(__file__).resolve().parents[1]
CHAT = BACKEND / ".bago" / "chat"
CORE = BACKEND / ".bago" / "core"
for path in (str(CHAT), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)

_MENU_PATH = CHAT / "repl_menu.py"
_SPEC = importlib.util.spec_from_file_location("bago_repl_menu_gateway_test", _MENU_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MENU_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MENU_MODULE)


def test_ui_config_menu_saves_through_registered_config_writer(tmp_path, monkeypatch):
    backend_root = tmp_path / "backend"
    monkeypatch.setattr(
        _MENU_MODULE,
        "__file__",
        str(backend_root / ".bago" / "chat" / "repl_menu.py"),
    )
    menu = object.__new__(_MENU_MODULE.BagoReplMenuMixin)
    menu.mgr = SimpleNamespace(session_id="repl-session-1")

    config = {"theme": {"mode": "dark"}, "layout": {"chat": True}}
    menu._ui_save_config(config)

    target = backend_root / "ui-react" / "public" / "ui_config.json"
    assert json.loads(target.read_text(encoding="utf-8")) == config
    assert not list(target.parent.glob(".*.tmp"))

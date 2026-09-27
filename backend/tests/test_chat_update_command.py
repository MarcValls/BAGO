from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND = Path(__file__).resolve().parents[1]
CHAT = BACKEND / ".bago" / "chat"
API = BACKEND / ".bago" / "api"
for path in (BACKEND, CHAT, API):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import commands as chat_commands  # noqa: E402
import types  # noqa: E402


def test_chat_update_prepares_release_without_launching_a_second_installer(monkeypatch) -> None:
    calls: list[str] = []
    fake_updater = types.SimpleNamespace(
        status=lambda: {"status": "idle"},
        start_update=lambda tag: calls.append(tag) or {"ok": True, "status": "queued", "latest": tag},
    )
    monkeypatch.setitem(sys.modules, "update_manager", fake_updater)

    result = chat_commands.cmd_update(SimpleNamespace(), SimpleNamespace(), ["v4.9.2"])

    assert result["ok"] is True
    assert calls == ["v4.9.2"]
    assert "Sistema → Actualización de BAGO" in result["message"]
    assert "Instalar y reiniciar" in result["message"]
    assert result["data"]["status"] == "queued"


def test_chat_update_ready_release_requires_the_visible_apply_confirmation(monkeypatch) -> None:
    fake_updater = types.SimpleNamespace(
        status=lambda: {"status": "ready", "latest": "v4.9.2"},
        start_update=lambda _tag: (_ for _ in ()).throw(
            AssertionError("ready release must not be downloaded again")
        ),
    )
    monkeypatch.setitem(sys.modules, "update_manager", fake_updater)

    result = chat_commands.cmd_update(SimpleNamespace(), SimpleNamespace(), [])

    assert result["ok"] is True
    assert "descargada y verificada" in result["message"]
    assert "confirma «Instalar y reiniciar»" in result["message"]

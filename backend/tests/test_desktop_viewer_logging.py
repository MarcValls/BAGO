from __future__ import annotations

import importlib


class _Handler:
    def __init__(self, address: str = "127.0.0.1") -> None:
        self.client_address = (address, 32100)


def test_viewer_diagnostic_uses_structured_logger(monkeypatch) -> None:
    serializers = importlib.import_module("api_serializers")
    handler_module = importlib.import_module("handlers_desktop")
    structured_log = importlib.import_module("structured_log")
    sent = {}
    records = []

    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, payload: sent.update(status=status, payload=payload))

    class _Logger:
        def info(self, event, **fields):
            records.append((event, fields))

    monkeypatch.setattr(structured_log, "get_logger", lambda: _Logger())
    handler_module.handle_viewer_log(
        _Handler(), {"source": "electron-viewer", "kind": "boot", "message": "backend ready"}
    )

    assert sent == {"status": 200, "payload": {"ok": True}}
    assert records == [(
        "electron_viewer_diagnostic",
        {"source": "electron-viewer", "kind": "boot", "message": "backend ready"},
    )]


def test_viewer_diagnostic_blocks_remote_and_invalid_records_before_logging(monkeypatch) -> None:
    serializers = importlib.import_module("api_serializers")
    handler_module = importlib.import_module("handlers_desktop")
    structured_log = importlib.import_module("structured_log")
    sent = {}
    monkeypatch.setattr(serializers, "send_json", lambda _handler, status, payload: sent.update(status=status, payload=payload))
    monkeypatch.setattr(structured_log, "get_logger", lambda: (_ for _ in ()).throw(AssertionError("must block before logging")))

    handler_module.handle_viewer_log(
        _Handler("192.0.2.4"), {"source": "electron-viewer", "kind": "boot", "message": "ignored"}
    )
    assert sent["status"] == 403
    assert sent["payload"]["code"] == "DESKTOP_LOG_LOCAL_ONLY"

    handler_module.handle_viewer_log(
        _Handler(), {"source": "electron-viewer", "kind": "other", "message": "ignored"}
    )
    assert sent["status"] == 400
    assert sent["payload"]["code"] == "DESKTOP_LOG_RECORD_INVALID"


def test_viewer_log_route_is_dispatchable() -> None:
    dispatch = importlib.import_module("api_dispatch")
    assert "/desktop/viewer-log" in dispatch.POST_ROUTES
    assert "/desktop" in dispatch.API_PREFIXES

from __future__ import annotations

from types import SimpleNamespace


def _http_json(url, token, *, method="GET", body=None):
    import json
    import urllib.request

    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"X-Bago-Token": token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_kv_health_read_write_update_delete_contract(monkeypatch, tmp_path):
    import api_serializers
    import handlers_kv

    responses = []
    monkeypatch.setattr(api_serializers, "send_json", lambda handler, status, payload: responses.append((status, payload)))
    monkeypatch.setattr(handlers_kv, "send_json", lambda handler, status, payload: responses.append((status, payload)))

    handler = SimpleNamespace(
        path="/api/v1/kb?prefix=gestor:",
        session_mgr=SimpleNamespace(state_root=tmp_path),
    )

    handlers_kv.handle_set(handler, {"key": "gestor:contacts", "value": "[]", "tags": ["gestor"]})
    assert responses.pop() == (201, {"ok": True, "entry": {"key": "gestor:contacts", "value": "[]", "tags": ["gestor"]}, "created": True})

    handlers_kv.handle_get(handler, "gestor%3Acontacts")
    assert responses.pop()[1]["value"] == "[]"

    handlers_kv.handle_put(handler, "gestor%3Acontacts", {"value": "[1]", "tags": ["gestor"]})
    status, updated = responses.pop()
    assert status == 200 and updated["created"] is False

    handlers_kv.handle_list(handler)
    status, entries = responses.pop()
    assert status == 200 and entries[0]["value"] == "[1]"

    handlers_kv.handle_delete(handler, "gestor%3Acontacts")
    assert responses.pop() == (200, {"ok": True, "deleted": "gestor:contacts"})

    handlers_kv.handle_get(handler, "gestor%3Acontacts")
    assert responses.pop()[0] == 404


def test_kv_backend_failure_is_explicit_not_empty_collection(monkeypatch, tmp_path):
    import handlers_kv

    responses = []
    monkeypatch.setattr(handlers_kv, "send_json", lambda handler, status, payload: responses.append((status, payload)))
    handler = SimpleNamespace(path="/api/v1/kb", session_mgr=SimpleNamespace(state_root=tmp_path))
    monkeypatch.setattr(handlers_kv, "_load", lambda handler: (_ for _ in ()).throw(PermissionError("denied")))

    handlers_kv.handle_list(handler)

    status, payload = responses.pop()
    assert status == 500
    assert payload["ok"] is False
    assert "denied" in payload["error"]
    assert payload != []


def test_real_http_dispatcher_supports_gestor_crud(tmp_path):
    from bridge import BagoAPIServer

    manager = SimpleNamespace(
        state_root=tmp_path,
        base_path=tmp_path,
        session_id="gestor-contract",
        provider="test",
        model="test",
    )
    server = BagoAPIServer(manager, SimpleNamespace(), port=0, token="contract-token")
    server.start()
    base = f"http://127.0.0.1:{server.port}"
    try:
        assert _http_json(f"{base}/health", "contract-token")[1]["ready"] is True
        created = _http_json(
            f"{base}/api/v1/kb",
            "contract-token",
            method="POST",
            body={"key": "gestor:contacts", "value": "[]", "tags": ["gestor"]},
        )
        assert created[0] == 201
        assert _http_json(f"{base}/api/v1/kb/gestor%3Acontacts", "contract-token")[1]["value"] == "[]"
        updated = _http_json(
            f"{base}/api/v1/kb/gestor%3Acontacts",
            "contract-token",
            method="PUT",
            body={"value": "[1]", "tags": ["gestor"]},
        )
        assert updated[1]["created"] is False
        assert _http_json(f"{base}/api/v1/kb?prefix=gestor%3A", "contract-token")[1][0]["value"] == "[1]"
        assert _http_json(f"{base}/api/v1/kb/gestor%3Acontacts", "contract-token", method="DELETE")[1]["ok"] is True
    finally:
        server.stop()

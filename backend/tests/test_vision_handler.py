"""Contract tests for the vision HTTP handler."""

from __future__ import annotations

import json


def test_vision_handler_returns_model_response(monkeypatch):
    import handlers_vision as vision
    from request_context import RequestContext

    captured = {}
    monkeypatch.setattr(
        vision,
        "_load_config",
        lambda: {"providers": {"ollama-local": {"base_url": "http://127.0.0.1:11434"}}},
    )
    monkeypatch.setattr(vision, "_vision_defaults", lambda *_args: ("bago-eyes:latest", 2.0))

    def fake_call(_url, _image, _prompt, model, _timeout, holder):
        holder.append({"ok": True, "raw": json.dumps({"model": model, "response": "BAGO visible", "eval_count": 3})})

    monkeypatch.setattr(vision, "_call_ollama_vision", fake_call)
    monkeypatch.setattr(
        RequestContext,
        "send_json",
        lambda _self, status, payload: captured.update(status=status, payload=payload),
    )

    vision.handle(object(), {"image_base64": "AAAA", "prompt": "describe"})

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["model"] == "bago-eyes:latest"
    assert captured["payload"]["response"] == "BAGO visible"


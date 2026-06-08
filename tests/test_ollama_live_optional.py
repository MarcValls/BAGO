#!/usr/bin/env python3
"""
Optional live Ollama proof for BAGO.

This test is intentionally skipped when Ollama is not running. It proves the
live path separately from the mandatory smoke gates.
"""

from __future__ import annotations

import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "chat"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "providers"))

from session_manager import SessionManager  # noqa: E402


OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
DEFAULT_MODEL = "llama3.2:3b"


def _ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"SKIP: Ollama local not available: {exc}")
        return []

    models = payload.get("models", [])
    names = [item.get("name", "") for item in models if item.get("name")]
    if not names:
        print("SKIP: Ollama is running but no local models are installed.")
    return names


def run_live_test() -> int:
    models = _ollama_models()
    if not models:
        return 0

    model = DEFAULT_MODEL if DEFAULT_MODEL in models else models[0]
    switch_model = next((candidate for candidate in models if candidate != model), model)

    with tempfile.TemporaryDirectory() as temp_root:
        mgr = SessionManager(base_path=temp_root, provider="ollama-local", model=model)
        response = mgr.send("Responde solo con OK para validar BAGO live.")
        assert response and isinstance(response, str)

        first_session = mgr.session_id
        history = mgr.store.get_history()
        assert len(history) >= 2

        switch = mgr.switch("ollama-local", switch_model, force=True)
        assert switch["ok"]
        assert mgr.session_id == first_session

        mgr.save()
        loaded = SessionManager.load(first_session, base_path=temp_root)
        assert loaded.session_id == first_session
        assert loaded.provider == "ollama-local"
        assert loaded.store.get_history()
        loaded.close()
        mgr.close()

    print(f"OK: live Ollama session persisted and switch path verified with {model}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_live_test())
    except AssertionError as exc:
        print(f"FAIL: live Ollama proof failed: {exc}")
        raise SystemExit(1)

"""Contrato de autenticación y credenciales para BAGO."""
from __future__ import annotations

import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from bago.credentials import auth_state, policy


class _FakeManager:
    PROVIDERS = {
        "github": {"env": "GITHUB_TOKEN", "bago_provider": "copilot", "desc": "GitHub"},
        "openai": {"env": "OPENAI_API_KEY", "bago_provider": "codex", "desc": "OpenAI"},
        "ollama": {"env": None, "bago_provider": "ollama-local", "desc": "Ollama"},
        "opencode": {"env": None, "bago_provider": "opencode", "desc": "OpenCode"},
        "ollama_cloud": {"env": "OLLAMA_CLOUD_API_KEY", "bago_provider": "ollama-cloud", "desc": "Ollama Cloud"},
    }

    def __init__(self):
        self._creds = {"github": "ghp_exampletoken", "opencode_via": "cli"}

    def is_provider_enabled(self, name: str) -> bool:
        return True

    def _ollama_ok(self) -> bool:
        return True

    def _codex_authed(self) -> bool:
        return False


def test_credential_policy_is_centralized():
    assert policy.CREDENTIAL_FILES == (
        "credentials.json",
        "accounts.json",
        "token_log.json",
        "provider_state.json",
    )


def test_active_provider_state_and_views(monkeypatch):
    fake = _FakeManager()
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_exampletoken")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-exampletoken")
    monkeypatch.setenv("BAGO_ENABLE_LOCAL_MODE", "1")
    monkeypatch.delenv("OLLAMA_CLOUD_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    active = auth_state.active_bago_providers(fake)
    assert "copilot" in active
    assert "github-models" in active
    assert "codex" in active
    assert "ollama-local" in active

    login_view = auth_state.build_login_view(fake, "github", fake.PROVIDERS["github"], active)
    status_view = auth_state.build_status_view(fake, "openai", fake.PROVIDERS["openai"])

    assert login_view is not None
    assert login_view.state == "configurado"
    assert login_view.mark == "✓"
    assert status_view is not None
    assert "API key configurada" in status_view.status


def test_manager_wraps_auth_state_helpers():
    manager_path = Path(__file__).resolve().parents[1] / "bago" / "credentials" / "manager.py"
    text = manager_path.read_text(encoding="utf-8")
    assert "_active_bago_providers(self)" in text
    assert "build_login_view(self" in text
    assert "build_status_view(self" in text
    assert "is_valid_api_key" in text


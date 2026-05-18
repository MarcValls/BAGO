"""
Tests para token tracking y scan history (providers.py / session.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".bago" / "tools"))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_session():
    """Crea un BagoSession mínimo para tests (sin credenciales reales)."""
    from bago.session import BagoSession

    creds = MagicMock()
    creds.active_bago_providers.return_value = []
    session = BagoSession(
        provider="ollama-local",
        model_name="qwen25-mini",
        wire_name="qwen25-mini",
        creds=creds,
    )
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Token tracking — BagoSession
# ─────────────────────────────────────────────────────────────────────────────

class TestTokenTracking:

    def test_initial_token_log_empty(self):
        session = _make_session()
        assert session.token_log == {}

    def test_record_tokens_basic(self):
        session = _make_session()
        session.record_tokens("ollama-local", "qwen25-mini", 100, 50)
        assert session.token_log["ollama-local"]["qwen25-mini"]["in"]    == 100
        assert session.token_log["ollama-local"]["qwen25-mini"]["out"]   == 50
        assert session.token_log["ollama-local"]["qwen25-mini"]["calls"] == 1

    def test_record_tokens_accumulates(self):
        session = _make_session()
        session.record_tokens("copilot", "gpt-4o", 200, 80)
        session.record_tokens("copilot", "gpt-4o", 150, 60)
        m = session.token_log["copilot"]["gpt-4o"]
        assert m["in"]    == 350
        assert m["out"]   == 140
        assert m["calls"] == 2

    def test_record_tokens_multiple_providers(self):
        session = _make_session()
        session.record_tokens("ollama-local", "qwen25-mini", 100, 40)
        session.record_tokens("copilot",      "gpt-4o",      200, 80)
        assert "ollama-local" in session.token_log
        assert "copilot"      in session.token_log
        assert session.token_log["ollama-local"]["qwen25-mini"]["calls"] == 1
        assert session.token_log["copilot"]["gpt-4o"]["calls"]          == 1

    def test_record_tokens_none_values(self):
        """record_tokens no debe fallar con None (provider que no reporta usage)."""
        session = _make_session()
        session.record_tokens("ollama-local", "qwen25-mini", None, None)
        m = session.token_log["ollama-local"]["qwen25-mini"]
        assert m["in"]  == 0
        assert m["out"] == 0

    def test_tokens_summary_empty(self):
        session = _make_session()
        summary = session.tokens_summary()
        assert "sin llamadas" in summary

    def test_tokens_summary_shows_total(self):
        session = _make_session()
        session.record_tokens("ollama-local", "qwen25-mini", 100, 50)
        session.record_tokens("copilot",      "gpt-4o",      200, 80)
        summary = session.tokens_summary()
        assert "TOTAL" in summary
        assert "300" in summary.replace(",", "")   # 100+200
        assert "130" in summary.replace(",", "")   # 50+80

    def test_tokens_summary_shows_provider_and_model(self):
        session = _make_session()
        session.record_tokens("copilot", "gpt-4o", 500, 200)
        summary = session.tokens_summary()
        assert "copilot" in summary
        assert "gpt-4o"  in summary

    def test_tokens_summary_shows_call_count(self):
        session = _make_session()
        for _ in range(3):
            session.record_tokens("ollama-local", "qwen25-mini", 100, 40)
        summary = session.tokens_summary()
        assert "3" in summary   # 3 llamadas


# ─────────────────────────────────────────────────────────────────────────────
# Scan history — update_scan_history
# ─────────────────────────────────────────────────────────────────────────────

class TestScanHistory:

    def test_update_creates_file(self, tmp_path):
        health = {
            "ollama-local": {"ok": True,  "models": ["qwen25-mini"], "detail": "OK"},
            "copilot":      {"ok": False, "detail": "sin token"},
        }
        history_file = tmp_path / "scan_history.json"

        from bago import providers as prov_mod
        original = prov_mod.SCAN_HISTORY_FILE
        prov_mod.SCAN_HISTORY_FILE = history_file
        try:
            missing = prov_mod.update_scan_history(health)
        finally:
            prov_mod.SCAN_HISTORY_FILE = original

        assert history_file.exists()
        data = json.loads(history_file.read_text(encoding="utf-8"))
        assert "last_scan" in data
        assert "ollama-local" in data["providers"]

    def test_no_missing_on_first_scan(self, tmp_path):
        """En el primer scan nunca hay MISSING (nada tenía historial ok)."""
        health = {
            "ollama-local": {"ok": False, "detail": "no encontrado"},
            "copilot":      {"ok": False, "detail": "sin token"},
        }
        history_file = tmp_path / "scan_history.json"

        from bago import providers as prov_mod
        original = prov_mod.SCAN_HISTORY_FILE
        prov_mod.SCAN_HISTORY_FILE = history_file
        try:
            missing = prov_mod.update_scan_history(health)
        finally:
            prov_mod.SCAN_HISTORY_FILE = original

        assert missing == {}

    def test_missing_detected_after_ok_scan(self, tmp_path):
        """Un provider que estaba ok y ahora no → aparece en MISSING."""
        history_file = tmp_path / "scan_history.json"

        from bago import providers as prov_mod
        original = prov_mod.SCAN_HISTORY_FILE
        prov_mod.SCAN_HISTORY_FILE = history_file
        try:
            # Scan 1: copilot OK
            prov_mod.update_scan_history({
                "copilot": {"ok": True, "detail": "@user"},
            })
            # Scan 2: copilot KO
            missing = prov_mod.update_scan_history({
                "copilot": {"ok": False, "detail": "401"},
            })
        finally:
            prov_mod.SCAN_HISTORY_FILE = original

        assert "copilot" in missing
        assert "last_ok" in missing["copilot"]

    def test_not_missing_if_still_ok(self, tmp_path):
        """Un provider ok en ambos scans NO debe aparecer en MISSING."""
        history_file = tmp_path / "scan_history.json"

        from bago import providers as prov_mod
        original = prov_mod.SCAN_HISTORY_FILE
        prov_mod.SCAN_HISTORY_FILE = history_file
        try:
            prov_mod.update_scan_history({"copilot": {"ok": True, "detail": "@u"}})
            missing = prov_mod.update_scan_history({"copilot": {"ok": True, "detail": "@u"}})
        finally:
            prov_mod.SCAN_HISTORY_FILE = original

        assert "copilot" not in missing

    def test_missing_stores_last_models(self, tmp_path):
        """MISSING conserva los modelos que tenía el provider cuando estaba ok."""
        history_file = tmp_path / "scan_history.json"
        models = ["qwen2.5-coder:7b", "llama3:8b"]

        from bago import providers as prov_mod
        original = prov_mod.SCAN_HISTORY_FILE
        prov_mod.SCAN_HISTORY_FILE = history_file
        try:
            prov_mod.update_scan_history({
                "ollama-local": {"ok": True, "models": models, "detail": "OK"},
            })
            missing = prov_mod.update_scan_history({
                "ollama-local": {"ok": False, "detail": "no encontrado", "models": []},
            })
        finally:
            prov_mod.SCAN_HISTORY_FILE = original

        assert "ollama-local" in missing
        assert missing["ollama-local"]["last_models"] == models

    def test_known_providers_catalog_complete(self):
        """El catálogo incluye los 7 providers conocidos."""
        from bago.providers import KNOWN_PROVIDERS_CATALOG
        expected = {"ollama-local", "ollama-cloud", "copilot", "github-models", "codex", "anthropic", "openrouter"}
        assert set(KNOWN_PROVIDERS_CATALOG.keys()) == expected

    def test_catalog_entries_have_required_fields(self):
        """Cada entrada del catálogo tiene los campos mínimos."""
        from bago.providers import KNOWN_PROVIDERS_CATALOG
        required = {"label", "description", "setup", "requires", "type"}
        for pname, entry in KNOWN_PROVIDERS_CATALOG.items():
            missing_fields = required - set(entry.keys())
            assert not missing_fields, f"{pname} falta: {missing_fields}"


# ─────────────────────────────────────────────────────────────────────────────
# _check_codex — detección ChatGPT OAuth / API key / CLI sin login
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckCodex:
    """Tests para la detección de credenciales del provider codex/OpenAI."""

    def test_api_key_detected(self, monkeypatch, tmp_path):
        """OPENAI_API_KEY → ok=True con 4 últimos dígitos."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test1234")
        # codex_dir vacío para no mezclar con OAuth
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["codex"]["ok"] is True
        assert "1234" in result["codex"]["detail"]

    def test_oauth_token_detected(self, monkeypatch, tmp_path):
        """~/.codex/auth.json con tokens.access_token → ok=True, ChatGPT OAuth."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "auth.json").write_text(json.dumps({
            "tokens": {"access_token": "chatgpt-oauth-token-xyz"},
            "user": {"email": "marc@example.com"},
        }))
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["codex"]["ok"] is True
        assert "OAuth" in result["codex"]["detail"] or "oauth" in result["codex"]["detail"].lower()

    def test_alternative_token_keys(self, monkeypatch, tmp_path):
        """~/.codex/auth.json con clave access_token directa → ok=True."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "auth.json").write_text(json.dumps({
            "access_token": "direct-token-abc",
        }))
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        # El access_token directo es recogido por _codex_access_token() o el fallback
        assert result["codex"]["ok"] is True

    def test_cli_installed_no_login(self, monkeypatch, tmp_path):
        """codex CLI instalado pero sin auth.json → ok=False con mensaje de login."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # ~/.codex no existe
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        import shutil as _shutil
        real_which = _shutil.which

        def mock_which(name, *a, **kw):
            if name == "codex":
                return "/usr/local/bin/codex"
            return real_which(name, *a, **kw)

        monkeypatch.setattr("shutil.which", mock_which)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["codex"]["ok"] is False
        assert "login" in result["codex"]["detail"].lower()

    def test_nothing_available(self, monkeypatch, tmp_path):
        """Sin API key, sin auth.json, sin CLI → ok=False con instrucciones."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        import shutil as _shutil
        real_which = _shutil.which

        def mock_which(name, *a, **kw):
            if name == "codex":
                return None
            return real_which(name, *a, **kw)

        monkeypatch.setattr("shutil.which", mock_which)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["codex"]["ok"] is False
        # Debe mencionar cómo instalar codex o cómo obtener API key
        detail = result["codex"]["detail"].lower()
        assert "api" in detail or "codex" in detail or "openai" in detail

    def test_api_key_takes_priority_over_oauth(self, monkeypatch, tmp_path):
        """Si hay OPENAI_API_KEY Y auth.json, API key gana."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-prioritykey9999")
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "auth.json").write_text(json.dumps({
            "tokens": {"access_token": "should-not-be-used"},
        }))
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["codex"]["ok"] is True
        assert "9999" in result["codex"]["detail"]
        assert "OAuth" not in result["codex"]["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# _check_github_models — detección GitHub Models (servicio separado de Copilot)
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckGitHubModels:
    """Tests para el provider github-models (models.github.ai)."""

    def test_no_token_returns_not_ok(self, monkeypatch):
        """Sin GITHUB_TOKEN → ok=False con instrucción de login."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["github-models"]["ok"] is False
        assert "gh auth login" in result["github-models"]["detail"] or \
               "GITHUB_TOKEN" in result["github-models"]["detail"]

    def test_valid_token_with_mock_catalog(self, monkeypatch):
        """Token válido + catálogo HTTP 200 → ok=True con lista de modelos."""
        import urllib.request
        import json as _json

        monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken123")

        catalog = [
            {"id": "openai/gpt-4.1"},
            {"id": "openai/gpt-4o"},
            {"id": "meta/llama-3-70b"},
            {"id": "mistral/mistral-large"},
        ]

        class _FakeResponse:
            def read(self):
                return _json.dumps(catalog).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeResponse())

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["github-models"]["ok"] is True
        assert result["github-models"]["models"] == [
            "openai/gpt-4.1", "openai/gpt-4o", "meta/llama-3-70b", "mistral/mistral-large"
        ]
        assert "4 modelos" in result["github-models"]["detail"]

    def test_http_401_returns_not_ok(self, monkeypatch):
        """Token inválido (401) → ok=False con mensaje claro."""
        import urllib.request, urllib.error

        monkeypatch.setenv("GITHUB_TOKEN", "invalid-token")

        def _raise_401(*a, **kw):
            raise urllib.error.HTTPError(None, 401, "Unauthorized", {}, None)

        monkeypatch.setattr(urllib.request, "urlopen", _raise_401)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["github-models"]["ok"] is False
        assert "401" in result["github-models"]["detail"]

    def test_http_403_returns_not_ok(self, monkeypatch):
        """403 → ok=False (cuenta sin permisos)."""
        import urllib.request, urllib.error

        monkeypatch.setenv("GITHUB_TOKEN", "ghp_nopermissions")

        def _raise_403(*a, **kw):
            raise urllib.error.HTTPError(None, 403, "Forbidden", {}, None)

        monkeypatch.setattr(urllib.request, "urlopen", _raise_403)

        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        assert result["github-models"]["ok"] is False
        assert "403" in result["github-models"]["detail"]

    def test_github_models_in_catalog(self):
        """github-models aparece en el catalogo de providers conocidos."""
        from bago.providers import KNOWN_PROVIDERS_CATALOG
        assert "github-models" in KNOWN_PROVIDERS_CATALOG
        entry = KNOWN_PROVIDERS_CATALOG["github-models"]
        assert entry["openai_compat"] is True
        assert "models.github.ai" in entry["endpoint"]

    def test_github_models_separate_from_copilot(self, monkeypatch):
        """github-models y copilot son checks independientes en el resultado."""
        from bago import providers as pmod
        result = pmod.scan_provider_health(None, providers={})
        # Ambos deben estar presentes como claves separadas
        assert "github-models" in result
        assert "copilot" in result
        # No deben ser el mismo objeto
        assert result["github-models"] is not result["copilot"]

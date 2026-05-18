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
        """El catálogo incluye los 6 providers conocidos."""
        from bago.providers import KNOWN_PROVIDERS_CATALOG
        expected = {"ollama-local", "ollama-cloud", "copilot", "codex", "anthropic", "openrouter"}
        assert set(KNOWN_PROVIDERS_CATALOG.keys()) == expected

    def test_catalog_entries_have_required_fields(self):
        """Cada entrada del catálogo tiene los campos mínimos."""
        from bago.providers import KNOWN_PROVIDERS_CATALOG
        required = {"label", "description", "setup", "requires", "type"}
        for pname, entry in KNOWN_PROVIDERS_CATALOG.items():
            missing_fields = required - set(entry.keys())
            assert not missing_fields, f"{pname} falta: {missing_fields}"

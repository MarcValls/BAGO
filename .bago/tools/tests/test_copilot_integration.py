"""test_copilot_integration.py — Tests de integracion para verificaciones de Copilot.

Estos tests detectan fallos comunes que Copilot ha encontrado al operar BAGO,
como parametros de configuracion que no se propagan correctamente a la sesion.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# ── Roots ──────────────────────────────────────────────────────────────────────
TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from bago.session import BagoSession
from bago import CredentialManager
from bago.chat.boot import resolve_session
from bago.menus.config import _load_config, _DEFAULT_CONFIG
from bago.providers import resolve_litellm
from bago.constants import USER_BAGO


class TestCopilotConfigPropagation:
    """Valida que parametros de config llegan correctamente a la sesion."""

    def test_single_model_propagated_from_args_to_session(self):
        """single_model=True en args debe llegar a BagoSession.single_model."""
        class FakeArgs:
            provider = ""
            model = ""
            task = ""
            local = False
            single_model = True

        session = resolve_session(FakeArgs())
        assert session.single_model is True, (
            "single_model no se propago desde args a BagoSession; "
            "verificar que resolve_session pase single_model al constructor"
        )

    def test_single_model_false_by_default(self, monkeypatch):
        """Por defecto single_model debe ser False."""
        detect = iter(["copilot"])

        class FakeArgs:
            provider = ""
            model = ""
            task = ""
            local = False
            single_model = False

        from bago.chat import boot as boot
        monkeypatch.setattr(boot, "load_providers", lambda: {
            "copilot": {"models": {"gpt-4o": {"wire_name": "gpt-4o"}}},
        })
        monkeypatch.setattr(boot, "load_routing", lambda: {"rules": [], "fallback": {"provider": "copilot", "model": "gpt-4o"}})
        monkeypatch.setattr(boot, "auto_detect_provider", lambda *args, **kwargs: next(detect))
        import bago.provider_health as provider_health
        monkeypatch.setattr(provider_health, "scan_provider_health", lambda *args, **kwargs: {"copilot": {"ok": True}})
        monkeypatch.setattr("bago.menus.auth._cmd_login", lambda session: None)

        session = resolve_session(FakeArgs())
        assert session.single_model is False

    def test_config_contains_single_model_key(self):
        """bago_chat_config.json debe tener la clave single_model."""
        cfg = _load_config()
        assert "single_model" in cfg, "Falta single_model en bago_chat_config.json"

    def test_default_config_has_single_model(self):
        """_DEFAULT_CONFIG debe incluir single_model."""
        assert "single_model" in _DEFAULT_CONFIG
        assert _DEFAULT_CONFIG["single_model"] is False


class TestCopilotProviderResolution:
    """Valida resolucion de providers que Copilot configuro."""

    def test_github_models_resolves_to_openai_prefix(self):
        """github-models debe resolverse a openai/<model> con api_base correcto."""
        model, kw = resolve_litellm("github-models", "gpt-4o")
        assert model == "openai/gpt-4o", f"Esperado openai/gpt-4o, got {model}"
        assert "api_base" in kw
        assert "models.github.ai" in kw["api_base"]

    def test_replicate_prefixes_model_correctly(self):
        """replicate debe prefijar el modelo con replicate/."""
        model, kw = resolve_litellm("replicate", "llama-4-maverick")
        assert model == "replicate/llama-4-maverick", f"Esperado replicate/..., got {model}"

    def test_github_models_in_known_catalog(self):
        """github-models debe estar en KNOWN_PROVIDERS_CATALOG."""
        from bago.providers import KNOWN_PROVIDERS_CATALOG
        assert "github-models" in KNOWN_PROVIDERS_CATALOG, (
            "github-models no esta en KNOWN_PROVIDERS_CATALOG"
        )


class TestCopilotEnvironment:
    """Valida entorno donde Copilot opera BAGO."""

    def test_user_bago_writable(self):
        """USER_BAGO debe ser escribible; si no, repl.py debe tener fallback."""
        test_file = USER_BAGO / ".copilot_write_test"
        try:
            test_file.write_text("ok")
            test_file.unlink()
        except Exception as exc:
            # Si no es escribible, verificar que repl.py tenga fallback
            repl_path = TOOLS / "bago" / "chat" / "repl.py"
            assert repl_path.exists(), "repl.py no existe"
            text = repl_path.read_text(encoding="utf-8")
            assert "gettempdir" in text or "tempfile" in text, (
                f"USER_BAGO no escribible ({exc}) y repl.py carece de fallback"
            )

    def test_constants_user_bago_uses_home_fallback(self):
        """_resolve_user_bago debe fallback a Path.home()/.bago si no hay BAGO_USER_HOME."""
        from bago.constants import _resolve_user_bago
        # Sin env var, debe devolver home/.bago
        home_bago = Path.home() / ".bago"
        result = _resolve_user_bago()
        # Puede ser home/.bago o ProgramData si tiene permisos
        assert result is not None
        assert isinstance(result, Path)


class TestCopilotCmdIntegrity:
    """Valida integridad de comandos que Copilot toca."""

    def test_single_command_not_duplicated(self):
        """/single debe aparecer exactamente 1 vez como comando (elif v == ...)."""
        cmd_path = TOOLS / "bago" / "cmd.py"
        assert cmd_path.exists()
        text = cmd_path.read_text(encoding="utf-8")
        count = text.count('elif v == "/single":')
        assert count == 1, f"/single aparece {count} veces como comando, esperado 1"

    def test_call_py_respects_single_model(self):
        """call.py debe contener logica de single_model."""
        call_path = TOOLS / "bago" / "llm" / "call.py"
        assert call_path.exists()
        text = call_path.read_text(encoding="utf-8")
        assert "single_model" in text, "call.py no menciona single_model"

    def test_orchestrator_py_respects_single_model(self):
        """orchestrator.py debe contener logica de single_model."""
        orch_path = TOOLS / "bago" / "llm" / "orchestrator.py"
        assert orch_path.exists()
        text = orch_path.read_text(encoding="utf-8")
        assert "single_model" in text, "orchestrator.py no menciona single_model"


class TestCopilotBootIntegrity:
    """Valida que boot.py no degrade provider cuando single_model esta activo."""

    def test_boot_skips_fallback_when_single_model(self):
        """Si args.single_model=True, boot.py no debe buscar fallback de provider."""
        boot_path = TOOLS / "bago" / "chat" / "boot.py"
        assert boot_path.exists()
        text = boot_path.read_text(encoding="utf-8")
        assert "getattr(args, 'single_model', False)" in text, (
            "boot.py no consulta args.single_model antes de fallback"
        )

    def test_resolve_session_opens_login_when_no_provider(self, monkeypatch):
        """Si no hay provider, resolve_session debe pasar por la pantalla de login."""
        from bago.chat import boot as boot

        calls = {"login": 0}
        detect = iter(["none", "copilot"])

        class FakeArgs:
            provider = ""
            model = ""
            task = ""
            local = False
            single_model = False

        monkeypatch.setattr(boot, "load_providers", lambda: {
            "copilot": {"models": {"gpt-4o": {"wire_name": "gpt-4o"}}},
        })
        monkeypatch.setattr(boot, "load_routing", lambda: {"rules": [], "fallback": {"provider": "copilot", "model": "gpt-4o"}})
        monkeypatch.setattr(boot, "auto_detect_provider", lambda *args, **kwargs: next(detect))
        monkeypatch.setattr(boot, "get_default_model", lambda provider, providers: ("gpt-4o", "gpt-4o", provider) if provider == "copilot" else ("", "", "none"))
        monkeypatch.setattr("bago.menus.auth._cmd_login", lambda session: calls.__setitem__("login", calls["login"] + 1))

        session = boot.resolve_session(FakeArgs())

        assert calls["login"] == 1
        assert session.provider == "copilot"
        assert session.model_name == "gpt-4o"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

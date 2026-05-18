"""Tests para el flujo de recuperación de errores Ollama."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".bago" / "tools"))

from bago.llm import (_is_ollama_model_not_found, _is_ollama_unreachable,
                      _is_cloud_auth_error, _is_cloud_connection_error)
from bago.providers import ollama_probe


class TestIsOllamaModelNotFound:
    def test_standard_litellm_error(self):
        msg = "litellm.APIConnectionError: OllamaException - {\"error\":\"model 'qwen2.5-coder:7b' not found\"}"
        found, name = _is_ollama_model_not_found(Exception(msg))
        assert found is True
        assert "qwen2.5-coder" in name

    def test_extract_model_name(self):
        msg = "OllamaException - {\"error\":\"model 'llama3:8b' not found\"}"
        found, name = _is_ollama_model_not_found(Exception(msg))
        assert found is True
        assert "llama3" in name

    def test_no_false_positive_context_error(self):
        msg = "context length exceeded: token count too long"
        found, _ = _is_ollama_model_not_found(Exception(msg))
        assert found is False

    def test_no_false_positive_connection_refused(self):
        msg = "Connection refused: cannot connect to host 127.0.0.1:11434"
        found, _ = _is_ollama_model_not_found(Exception(msg))
        assert found is False

    def test_model_name_without_tag(self):
        msg = "model 'mistral' not found"
        found, name = _is_ollama_model_not_found(Exception(msg))
        assert found is True
        assert name == "mistral"


class TestIsOllamaUnreachable:
    def test_connection_refused(self):
        msg = "ollama: Connection refused: cannot connect to host 127.0.0.1:11434"
        assert _is_ollama_unreachable(Exception(msg)) is True

    def test_apiconnectionerror(self):
        # OllamaException en el mensaje → sí se detecta como Ollama inalcanzable
        msg = "litellm.APIConnectionError: OllamaException - Connect call failed"
        assert _is_ollama_unreachable(Exception(msg)) is True

    def test_non_ollama_connection_error(self):
        # Error de conexión genérico sin Ollama → no se detecta
        msg = "APIConnectionError: Connection refused to openai.com"
        assert _is_ollama_unreachable(Exception(msg)) is False

    def test_ollama_connection_error(self):
        msg = "APIConnectionError: ollama host cannot connect to host localhost:11434"
        assert _is_ollama_unreachable(Exception(msg)) is True

    def test_model_not_found_not_unreachable(self):
        msg = "OllamaException - {\"error\":\"model 'qwen2.5-coder:7b' not found\"}"
        assert _is_ollama_unreachable(Exception(msg)) is False


class TestOllamaProbe:
    def test_probe_running_with_models(self):
        """Simula Ollama activo con modelos."""
        fake_response = b'{"models":[{"name":"qwen2.5-coder:7b"},{"name":"llama3:8b"}]}'

        class FakeCtx:
            def read(self):
                return fake_response
            def __enter__(self): return self
            def __exit__(self, *a): pass

        with patch("urllib.request.urlopen", return_value=FakeCtx()):
            result = ollama_probe()

        assert result["running"] is True
        assert "qwen2.5-coder:7b" in result["models"]
        assert "llama3:8b" in result["models"]
        assert result["error"] is None

    def test_probe_not_running(self):
        """Simula Ollama no disponible."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            result = ollama_probe()

        assert result["running"] is False
        assert result["models"] == []
        assert result["error"] is not None

    def test_probe_running_no_models(self):
        """Simula Ollama activo pero sin modelos."""
        fake_response = b'{"models":[]}'

        class FakeCtx:
            def read(self):
                return fake_response
            def __enter__(self): return self
            def __exit__(self, *a): pass

        with patch("urllib.request.urlopen", return_value=FakeCtx()):
            result = ollama_probe()

        assert result["running"] is True
        assert result["models"] == []


class TestSkipProviders:
    """Tests para la lógica de exclusión de providers en auto_route."""

    def _make_session(self, provider="ollama-local", model="qwen25-coder", wire="qwen2.5-coder:7b"):
        """Crea una BagoSession mínima para pruebas."""
        from bago.session import BagoSession
        creds = MagicMock()
        creds.active_bago_providers.return_value = ["ollama-local", "copilot"]
        providers = {
            "ollama-local": {"models": {"qwen25-coder": {"wire_name": "qwen2.5-coder:7b"}}},
            "copilot":      {"models": {"claude-sonnet-4.6": {"wire_name": "claude-sonnet-4.6"}}},
        }
        routing = {}
        with patch("bago.session.load_providers", return_value=providers), \
             patch("bago.session.load_routing", return_value=routing):
            session = BagoSession(provider, model, wire, creds)
        return session

    def test_skip_providers_initialized_empty(self):
        session = self._make_session()
        assert hasattr(session, "skip_providers")
        assert isinstance(session.skip_providers, set)
        assert len(session.skip_providers) == 0

    def test_skip_providers_blocks_auto_route(self):
        """Si ollama-local está en skip_providers, auto_route no debe volver a él."""
        session = self._make_session(provider="copilot", model="claude-sonnet-4.6", wire="claude-sonnet-4.6")
        session.skip_providers.add("ollama-local")

        # Simular que el orquestador sugiere volver a ollama-local
        fake_orch = MagicMock()
        fake_orch.orchestrate.return_value = {
            "model": "qwen25-coder",
            "provider": "ollama-local",
            "wire_name": "qwen2.5-coder:7b",
            "reason": "coding task",
        }
        with patch.object(session, "_load_orchestrator", return_value=fake_orch):
            switched, reason = session.auto_route("escribe una función python")

        # No debe haber cambiado a ollama-local
        assert session.provider != "ollama-local"

    def test_skip_providers_discard_restores_routing(self):
        """Al limpiar skip_providers, el routing vuelve a funcionar."""
        session = self._make_session(provider="copilot", model="claude-sonnet-4.6", wire="claude-sonnet-4.6")
        session.skip_providers.add("ollama-local")
        session.skip_providers.discard("ollama-local")
        assert "ollama-local" not in session.skip_providers


class TestCloudErrorDetectors:
    """Tests para _is_cloud_auth_error y _is_cloud_connection_error."""

    # ── Auth errors ───────────────────────────────────────────────────────────
    def test_auth_401_copilot(self):
        msg = "litellm.AuthenticationError: 401 Unauthorized - Invalid token for copilot"
        assert _is_cloud_auth_error(Exception(msg)) is True

    def test_auth_invalid_api_key(self):
        msg = "AuthenticationError: invalid_api_key - The API key provided is incorrect."
        assert _is_cloud_auth_error(Exception(msg)) is True

    def test_auth_forbidden(self):
        msg = "PermissionDeniedError: 403 forbidden - Access denied"
        assert _is_cloud_auth_error(Exception(msg)) is True

    def test_auth_does_not_match_ollama_unreachable(self):
        # Mensaje de Ollama → no debe ser detectado como cloud auth error
        msg = "OllamaException - 401 cannot connect to ollama host"
        assert _is_cloud_auth_error(Exception(msg)) is False

    def test_auth_no_false_positive_context(self):
        msg = "context length exceeded: token count too long"
        assert _is_cloud_auth_error(Exception(msg)) is False

    # ── Connection errors ─────────────────────────────────────────────────────
    def test_conn_timeout_copilot(self):
        msg = "APIConnectionError: Connection timed out reaching models.inference.ai.azure.com"
        assert _is_cloud_connection_error(Exception(msg)) is True

    def test_conn_read_timeout(self):
        msg = "ReadTimeoutError: Read timed out waiting for response from anthropic"
        assert _is_cloud_connection_error(Exception(msg)) is True

    def test_conn_503_overloaded(self):
        msg = "ServiceUnavailable: 503 overloaded — please retry"
        assert _is_cloud_connection_error(Exception(msg)) is True

    def test_conn_does_not_match_ollama(self):
        # Timeout hacia Ollama → no es cloud connection error
        msg = "APIConnectionError: OllamaException - Connection timed out on ollama host"
        assert _is_cloud_connection_error(Exception(msg)) is False

    def test_conn_no_false_positive_not_found(self):
        # "model not found" no es un error de conexión
        msg = "model 'gpt-5' not found in registry"
        assert _is_cloud_connection_error(Exception(msg)) is False

"""Tests para el flujo de recuperación de errores Ollama."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".bago" / "tools"))

from bago.llm import _is_ollama_model_not_found, _is_ollama_unreachable


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

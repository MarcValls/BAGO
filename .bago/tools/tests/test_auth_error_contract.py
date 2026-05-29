"""Contratos de clasificación de errores de autenticacion cloud."""

from __future__ import annotations

from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from bago.llm.errors import _is_cloud_auth_error, classify_provider_error


def test_openai_token_invalidated_counts_as_auth_error():
    msg = "litellm.BadRequestError: OpenAIException - Your authentication token has been invalidated. Please try signing in again"
    assert _is_cloud_auth_error(msg)
    assert classify_provider_error(msg) == "auth"


def test_openai_sign_in_again_phrase_counts_as_auth_error():
    msg = "Please try signing in again"
    assert _is_cloud_auth_error(msg)

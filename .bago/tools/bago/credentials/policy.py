"""Política compartida de credenciales y estado de arranque."""

from __future__ import annotations

CREDENTIAL_FILES = (
    "credentials.json",
    "accounts.json",
    "token_log.json",
    "provider_state.json",
)

CREDENTIAL_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_VIA",
    "CODEx_VIA",
    "CHATGPT_VIA",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "TOGETHER_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
    "PPLX_API_KEY",
    "COHERE_API_KEY",
    "REPLICATE_API_TOKEN",
    "HF_TOKEN",
    "OPENROUTER_API_KEY",
    "OLLAMA_CLOUD_API_KEY",
    "OLLAMA_API_KEY",
)


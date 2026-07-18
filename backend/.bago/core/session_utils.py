#!/usr/bin/env python3
"""session_utils.py — Free functions and constants for SessionManager.

Extracted from session_manager.py during modularization.
Contains adapter registry, BAGO mode definitions, and helper functions
that don't need `self` state.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))
from ollama_local import OllamaLocalAdapter
from ollama_cloud import OllamaCloudAdapter
from copilot import CopilotAdapter
from anthropic import AnthropicAdapter
from codex import CodexAdapter
from openrouter import OpenRouterAdapter
from opencode import OpenCodeAdapter
from provider_adapter import ProviderAdapter

ADAPTER_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "ollama-local": OllamaLocalAdapter,
    "ollama-cloud": OllamaCloudAdapter,
    "copilot": CopilotAdapter,
    "anthropic": AnthropicAdapter,
    "codex": CodexAdapter,
    "openrouter": OpenRouterAdapter,
    "opencode": OpenCodeAdapter,
}

BAGO_MODES: dict[str, str] = {
    "B": "Balanceado: aclara objetivo, alcance, riesgos y criterio de exito.",
    "A": "Adaptativo: inspecciona el estado real y elige estrategia.",
    "G": "Generativo: produce artefactos utiles y verificables.",
    "O": "Organizativo: verifica, registra estado y deja continuidad.",
}


def normalize_bago_mode(mode: str) -> str:
    """Valida y normaliza un modo BAGO a letra mayúscula."""
    normalized = str(mode or "B").strip().upper().strip("[]")
    if normalized not in BAGO_MODES:
        raise ValueError(f"Modo BAGO invalido: {mode}. Usa B, A, G u O.")
    return normalized


def normalize_bridges(providers: list[str], primary: str = "") -> list[str]:
    """Normaliza la lista de bridges: primary primero, sin duplicados."""
    seen: set[str] = set()
    result: list[str] = []
    for p in [primary] + [p for p in providers if p != primary]:
        if p and p not in seen:
            seen.add(p)
            result.append(p)
    return result


def model_quality_key(model_id: str) -> tuple[float, int, int]:
    """Clave de ordenamiento para seleccionar fallback: tamaño → latest → longitud."""
    match = re.search(r"(\d+(?:\.\d+)?)b\b", model_id.lower())
    size_score = float(match.group(1)) if match else 0.0
    latest_bonus = 1 if ":latest" in model_id.lower() else 0
    return (size_score, latest_bonus, len(model_id))


def format_rag_context(fragments: list[dict]) -> str:
    """Formatea los fragmentos RAG como bloque de contexto para el system prompt."""
    if not fragments:
        return ""
    lines = ["CONTEXTO RECUPERADO (RAG)"]
    for i, frag in enumerate(fragments, 1):
        source = frag.get("source", "unknown")
        score = frag.get("score", 0.0)
        content = frag.get("content", "")[:500]
        lines.append(f"[{i}] (origen={source}, score={score:.2f})\n{content}")
    return "\n\n".join(lines)
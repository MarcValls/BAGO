#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
provider_adapter.py — BAGO 4.1.5 Provider Adapter Base

Interfaz unificada para todos los providers de LLM.
Cada provider implementa esta interfaz.
El SessionManager habla con adapters, no con providers directamente.
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class ModelInfo:
    model_id: str
    wire_name: str
    provider: str
    context_tokens: int
    max_output_tokens: int
    best_for: str
    cost: str
    available: bool = True


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 1


@dataclass
class HealthStatus:
    ok: bool = False
    provider: str = ""
    detail: str = ""
    latency_ms: float = 0.0
    models_available: int = 0
    available_tokens: int | None = None
    token_source: str = ""
    token_limited: bool = False


@dataclass
class ProviderResponse:
    content: str = ""
    model_used: str = ""
    provider: str = ""
    finish_reason: str = ""
    usage: TokenUsage = None
    metadata: dict = None
    tool_calls: list[dict] = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = TokenUsage()
        if self.metadata is None:
            self.metadata = {}
        if self.tool_calls is None:
            self.tool_calls = []


class ProviderAdapter(ABC):
    """Interfaz base para todos los adapters de provider."""

    def __init__(self, provider_name: str, config: dict | None = None):
        self.provider_name = provider_name
        self.config = config or {}
        self._last_error: str = ""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        """Envía mensajes al provider y retorna respuesta normalizada."""
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Lista modelos disponibles en este provider."""
        ...

    @abstractmethod
    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        """Verifica si el provider está accesible."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Verifica si el provider tiene credenciales/configuración válida."""
        ...

    @abstractmethod
    def supports_tools(self) -> bool:
        """True si este provider/modelo soporta tool calls."""
        ...

    @abstractmethod
    def supports_streaming(self) -> bool:
        """True si soporta streaming de respuestas."""
        ...

    def supports_embeddings(self) -> bool:
        """True si soporta generar embeddings localmente/remotamente."""
        return False

    def chat_stream(
        self,
        messages: list[dict],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ):
        """Fallback: no streaming real. Llama a chat() y yield el contenido completo."""
        resp = self.chat(
            messages, model, system=system, temperature=temperature,
            max_tokens=max_tokens, stream=False, tools=tools,
        )
        if resp.content:
            yield resp.content

    def get_last_error(self) -> str:
        return self._last_error

    def _set_error(self, msg: str) -> None:
        self._last_error = msg

    def availability_snapshot(self, timeout: float = 5.0) -> dict[str, Any]:
        """Describe whether the provider is currently usable for auto-routing."""
        health = self.health_check(timeout=timeout)
        available_tokens = getattr(health, "available_tokens", None)
        token_limited = bool(getattr(health, "token_limited", False))
        configured = False
        try:
            configured = self.is_configured()
        except Exception:
            configured = False
        return {
            "provider": self.provider_name,
            "configured": configured,
            "healthy": bool(getattr(health, "ok", False)),
            "detail": str(getattr(health, "detail", "") or ""),
            "models_available": int(getattr(health, "models_available", 0) or 0),
            "available_tokens": int(available_tokens) if isinstance(available_tokens, int) and available_tokens >= 0 else None,
            "token_source": str(getattr(health, "token_source", "") or ""),
            "token_limited": token_limited,
            "usable": configured and bool(getattr(health, "ok", False)) and not token_limited,
        }

    def embed(self, texts: list[str], *, model: str = "") -> list[list[float]]:
        raise NotImplementedError(f"{self.provider_name} no soporta embeddings")


def _run_tests() -> int:
    print("provider_adapter.py --test: PASS (abstract base)")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

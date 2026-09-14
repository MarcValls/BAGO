"""Versioned provider-facing contracts.

Identity, observed capabilities and routing policy are deliberately separate:
providers report identity/availability, observations carry provenance, and
policy remains a versioned BAGO decision rather than a discovered fact.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator


CONTRACT_VERSION = "bago.provider-contracts/v1"


@dataclass(frozen=True)
class ModelIdentity:
    provider: str
    model_id: str
    wire_name: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider, self.model_id)


@dataclass(frozen=True)
class ObservedCapabilities:
    context_tokens: int | None = None
    max_output_tokens: int | None = None
    best_for: str | None = None
    available: bool = False
    source: str = "unknown"
    observed_at: str | None = None


@dataclass(frozen=True)
class RoutingPolicy:
    tier: str | None = None
    reasoning: str | None = None
    coding: str | None = None
    source: str = "none"
    version: str = "1"


@dataclass
class ModelInfo:
    """Compatibility DTO returned by provider adapters.

    Existing positional construction remains stable. The properties expose the
    separated v1 representations without fabricating data for unknown models.
    """

    model_id: str
    wire_name: str
    provider: str
    context_tokens: int
    max_output_tokens: int
    best_for: str
    cost: str
    available: bool = True
    capability_source: str = "provider-declared"
    observed_at: str | None = None

    @property
    def identity(self) -> ModelIdentity:
        return ModelIdentity(self.provider, self.model_id, self.wire_name)

    @property
    def observed_capabilities(self) -> ObservedCapabilities:
        return ObservedCapabilities(
            context_tokens=self.context_tokens,
            max_output_tokens=self.max_output_tokens,
            best_for=self.best_for,
            available=self.available,
            source=self.capability_source,
            observed_at=self.observed_at,
        )


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
    usage: TokenUsage | None = None
    metadata: dict | None = None
    tool_calls: list[dict] | None = None

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = TokenUsage()
        if self.metadata is None:
            self.metadata = {}
        if self.tool_calls is None:
            self.tool_calls = []


class ProviderAdapter(ABC):
    """Stable interface implemented by every provider adapter."""

    def __init__(self, provider_name: str, config: dict | None = None):
        self.provider_name = provider_name
        self.config = config or {}
        self._last_error = ""

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
    ) -> ProviderResponse: ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    def health_check(self, timeout: float = 5.0) -> HealthStatus: ...

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def supports_tools(self) -> bool: ...

    @abstractmethod
    def supports_streaming(self) -> bool: ...

    def supports_embeddings(self) -> bool:
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
    ) -> Iterator[str]:
        response = self.chat(
            messages,
            model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            tools=tools,
        )
        if response.content:
            yield response.content

    def get_last_error(self) -> str:
        return self._last_error

    def _set_error(self, message: str) -> None:
        self._last_error = message

    def availability_snapshot(self, timeout: float = 5.0) -> dict[str, Any]:
        health = self.health_check(timeout=timeout)
        available_tokens = getattr(health, "available_tokens", None)
        token_limited = bool(getattr(health, "token_limited", False))
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

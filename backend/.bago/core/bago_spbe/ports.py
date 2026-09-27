from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .model import (
    BoundResource,
    CapabilityCandidate,
    IntentRoot,
    ResourceBindingAttempt,
    SemanticInterpretation,
)


class SemanticInterpreterPort(Protocol):
    """Interpret user language; implementation is host-owned (LLM/rules/etc.)."""
    def interpret(self, intent_root: IntentRoot) -> SemanticInterpretation: ...


class SemanticNormalizerPort(Protocol):
    """Normalize without replacing IntentRoot authority."""
    def normalize(self, interpretation: SemanticInterpretation) -> SemanticInterpretation: ...


class CapabilityDiscoveryPort(Protocol):
    """Read-only discovery of capabilities actually exposed by the host."""
    def discover(self, interpretation: SemanticInterpretation) -> tuple[CapabilityCandidate, ...]: ...


class ResourceBindingPort(Protocol):
    """Read-only semantic-to-resource binding. Binding never grants authorization."""
    def bind(self, interpretation: SemanticInterpretation) -> tuple[tuple[ResourceBindingAttempt, ...], tuple[BoundResource, ...]]: ...


@dataclass(frozen=True)
class IdentityNormalizer:
    def normalize(self, interpretation: SemanticInterpretation) -> SemanticInterpretation:
        return interpretation


@dataclass(frozen=True)
class StaticCapabilityDiscovery:
    candidates: tuple[CapabilityCandidate, ...]
    def discover(self, interpretation: SemanticInterpretation) -> tuple[CapabilityCandidate, ...]:
        return self.candidates


@dataclass(frozen=True)
class NoopResourceBinder:
    def bind(self, interpretation: SemanticInterpretation):
        return (), ()

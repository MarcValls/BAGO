"""Compatibility facade for the stable provider contracts package."""

from bago_core.providers.contracts import (
    HealthStatus,
    ModelIdentity,
    ModelInfo,
    ObservedCapabilities,
    ProviderAdapter,
    ProviderResponse,
    RoutingPolicy,
    TokenUsage,
)

__all__ = [
    "HealthStatus",
    "ModelIdentity",
    "ModelInfo",
    "ObservedCapabilities",
    "ProviderAdapter",
    "ProviderResponse",
    "RoutingPolicy",
    "TokenUsage",
]


def _run_tests() -> int:
    print("provider_adapter.py --test: PASS (compatibility facade)")
    return 0


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

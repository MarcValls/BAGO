"""rate_limit.py — Token-bucket rate limiter per provider for the BAGO API bridge.

Limits the rate of requests to each provider (ollama-local, anthropic, openai,
etc.) to prevent saturation. Configurable via environment variables:

  BAGO_RATE_LIMIT_CAPACITY  — max tokens per bucket (default: 5)
  BAGO_RATE_LIMIT_REFILL_S  — tokens refilled per second (default: 1.0)

Thread-safe. Designed to be called from the bridge's do_POST before
dispatching to /chat or /switch.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    """One token bucket per provider."""
    capacity: float
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimiter:
    """Per-provider token-bucket rate limiter.

    Usage:
        limiter = RateLimiter()
        allowed, detail = limiter.check("ollama-local")
        if not allowed:
            return 429
    """

    def __init__(
        self,
        capacity: float | None = None,
        refill_per_s: float | None = None,
    ):
        self.capacity = float(
            capacity
            if capacity is not None
            else os.environ.get("BAGO_RATE_LIMIT_CAPACITY", 5)
        )
        self.refill_per_s = float(
            refill_per_s
            if refill_per_s is not None
            else os.environ.get("BAGO_RATE_LIMIT_REFILL_S", 1.0)
        )
        self._buckets: dict[str, _Bucket] = {}
        self._global_lock = threading.Lock()

    def _get_bucket(self, provider: str) -> _Bucket:
        with self._global_lock:
            if provider not in self._buckets:
                self._buckets[provider] = _Bucket(capacity=self.capacity, tokens=self.capacity)
            return self._buckets[provider]

    def check(self, provider: str) -> tuple[bool, str]:
        """Try to consume one token. Returns (allowed, detail)."""
        if self.capacity <= 0 or self.refill_per_s <= 0:
            # Rate limiting disabled
            return True, "rate_limit_disabled"

        bucket = self._get_bucket(provider)
        with bucket.lock:
            now = time.monotonic()
            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                bucket.capacity,
                bucket.tokens + elapsed * self.refill_per_s,
            )
            bucket.last_refill = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, f"tokens_remaining={bucket.tokens:.1f}"

            wait_s = (1.0 - bucket.tokens) / self.refill_per_s
            return False, f"rate_limited retry_after={wait_s:.1f}s"

    def status(self) -> dict:
        """Snapshot of all buckets for diagnostics."""
        out = {}
        for provider, bucket in self._buckets.items():
            with bucket.lock:
                out[provider] = {
                    "tokens": round(bucket.tokens, 2),
                    "capacity": bucket.capacity,
                    "refill_per_s": self.refill_per_s,
                }
        return out


# Singleton — shared across all request threads in the bridge process
_limiter: RateLimiter | None = None
_singleton_lock = threading.Lock()


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        with _singleton_lock:
            if _limiter is None:
                _limiter = RateLimiter()
    return _limiter
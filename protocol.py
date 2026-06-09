"""Local protocol shim for stable payload hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _normalize_payload(payload: Any) -> Any:
    if hasattr(payload, "to_dict"):
        try:
            return payload.to_dict()
        except Exception:
            pass
    if isinstance(payload, dict):
        return {str(key): _normalize_payload(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_normalize_payload(value) for value in payload]
    return payload


def hash_payload(payload: Any) -> str:
    """Return a deterministic sha256 hash for JSON-like payloads."""
    normalized = _normalize_payload(payload)
    text = json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"

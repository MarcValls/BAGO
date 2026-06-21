#!/usr/bin/env python3
"""TranslatorV1 base protocol used by BAGO translator pieces."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from ir_types import IRConversation, IRMessage


@dataclass
class Vocab:
    system_role: str = "system"
    user_role: str = "user"
    assistant_role: str = "assistant"
    tool_role: str = "tool"
    stop_sequences: list[str] = field(default_factory=list)
    format_hint: str = "json"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Safety:
    redact_in: list[str] = field(default_factory=list)
    redact_out: list[str] = field(default_factory=list)
    rate_limit: str = "client-side token bucket"

    def redact(self, text: str, direction: str) -> str:
        if not isinstance(text, str):
            return text
        words = self.redact_in if direction == "in" else self.redact_out
        for word in words:
            if word and word in text:
                text = text.replace(word, "***")
        return text


@dataclass
class EvidenceSpec:
    each_call: bool = True
    fields: list[str] = field(default_factory=lambda: [
        "request_hash",
        "response_hash",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "piece_id",
    ])


@dataclass
class SupportsSpec:
    tools: str = "none"
    vision: bool = False
    json_mode: str = "prompt"
    streaming: str = "sse"
    system_role: str = "native"
    plan_serialization: str = "json-in-system"
    evidence_prompt: str = "template-v1"


class TranslatorBase(Protocol):
    piece_id: str
    model_family: str
    model_id: str
    vocab: Vocab
    safety: Safety
    evidence: EvidenceSpec
    supports: SupportsSpec

    def encode(self, conversation: IRConversation) -> dict[str, Any]:
        ...

    def decode(self, payload: Any) -> IRConversation:
        ...


def hash_payload(payload: Any) -> str:
    """Stable short hash for evidence ledger."""
    import json

    try:
        s = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        s = repr(payload)
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

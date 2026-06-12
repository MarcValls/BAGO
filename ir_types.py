"""Local IR type shim for translator tests and bootstrap paths.

This module provides the minimal IR surface the translator layer expects when
the external shared/base piece is not present in a clean environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"

PART_TYPE_TEXT = "text"
PART_TYPE_PLAN = "plan"
PART_TYPE_EVIDENCE = "evidence"
PART_TYPE_TOOL_CALL = "tool_call"
PART_TYPE_TOOL_RESULT = "tool_result"


@dataclass
class IRMessage:
    id: str
    role: str
    parts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "role": self.role, "parts": list(self.parts)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IRMessage":
        return cls(
            id=str(data.get("id", "")),
            role=str(data.get("role", "")),
            parts=list(data.get("parts", [])),
        )


@dataclass
class IRConversation:
    messages: list[IRMessage] = field(default_factory=list)
    model_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [message.to_dict() for message in self.messages],
            "model_hint": self.model_hint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IRConversation":
        return cls(
            messages=[IRMessage.from_dict(item) for item in data.get("messages", [])],
            model_hint=str(data.get("model_hint", "")),
        )

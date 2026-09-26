"""Dataclasses for agent definitions, requests and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    category: str
    sandbox_mode: str = "read-only"
    model: str = ""
    model_reasoning_effort: str = ""
    prompt_template: str = ""
    source_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_read_only(self) -> bool:
        return self.sandbox_mode == "read-only"


@dataclass
class AgentRequest:
    agent_id: str
    task: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def provider(self) -> str:
        return str(self.options.get("provider", "")).strip()

    @property
    def model(self) -> str:
        return str(self.options.get("model", "")).strip()

    @property
    def use_bago_provider(self) -> bool:
        return bool(self.options.get("use_bago_provider", False))

    @property
    def mode(self) -> str:
        return str(self.options.get("mode", "run")).strip().lower() or "run"


@dataclass
class AgentResult:
    success: bool
    agent_id: str
    output: str = ""
    error: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
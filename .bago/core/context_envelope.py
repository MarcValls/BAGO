"""context_envelope.py — ContextEnvelope, ContextReceipt, SystemPromptCapsule.

F2: Estructura el contexto que se envía al LLM en un envelope inmutable,
genera un receipt con los metadatos de la llamada, y encapsula el system
prompt en secciones versionadas.

ContextEnvelope:
    - system_prompt: str (capsule renderizada)
    - messages: list[dict] (historial normalizado + mensaje actual)
    - tools: list[dict] | None
    - metadata: dict (intent, bago_mode, goal, model, provider)

ContextReceipt:
    - envelope_id: str (hash del envelope)
    - response_content: str
    - model_used: str
    - finish_reason: str
    - usage: dict (input_tokens, output_tokens, total_tokens)
    - latency_ms: float
    - timestamp: str (ISO)

SystemPromptCapsule:
    - sections: dict[str, str] (base, bootstrap, agent_start, bago_mode, active_agent, goal)
    - version: str (BAGO version)
    - render() -> str
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SystemPromptCapsule:
    """Encapsula el system prompt en secciones estructuradas e inmutables.

    Cada sección es independiente y se renderiza en orden fijo.
    La versión permite detectar drift entre sesiones.
    """
    base: str = ""
    bootstrap: str = ""
    agent_start: str = ""
    bago_mode_block: str = ""
    active_agent_block: str = ""
    goal_block: str = ""
    version: str = ""

    def render(self) -> str:
        """Renderiza todas las secciones no vacías separadas por doble newline."""
        parts = [
            self.base,
            self.bootstrap,
            self.agent_start,
            self.bago_mode_block,
            self.active_agent_block,
            self.goal_block,
        ]
        return "\n\n".join(p for p in parts if p and p.strip())


@dataclass
class ContextEnvelope:
    """Estructura inmutable del contexto enviado al adapter de provider.

    Reemplaza la concatenación ad-hoc de system_prompt + messages + tools
    que vivía dentro de SessionManager.send().
    """
    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def envelope_id(self) -> str:
        """Hash determinista del envelope para trazabilidad."""
        payload = json.dumps({
            "system": self.system_prompt,
            "messages": self.messages,
            "tools": self.tools or [],
        }, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class ContextReceipt:
    """Recibo de la ejecución de un ContextEnvelope contra un provider.

    Captura qué salió, cuánto costó (tokens), cuánto tardó, y por qué terminó.
    """
    envelope_id: str
    response_content: str
    model_used: str
    finish_reason: str
    usage: dict[str, int]
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(
        cls,
        envelope: ContextEnvelope,
        response_content: str,
        model_used: str,
        finish_reason: str,
        usage_input: int,
        usage_output: int,
        usage_total: int,
        latency_ms: float,
        extra_metadata: dict[str, Any] | None = None,
    ) -> "ContextReceipt":
        meta = dict(extra_metadata or {})
        meta["envelope_system_length"] = len(envelope.system_prompt)
        meta["envelope_messages_count"] = len(envelope.messages)
        return cls(
            envelope_id=envelope.envelope_id(),
            response_content=response_content,
            model_used=model_used,
            finish_reason=finish_reason,
            usage={
                "input_tokens": usage_input,
                "output_tokens": usage_output,
                "total_tokens": usage_total,
            },
            latency_ms=latency_ms,
            metadata=meta,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "model_used": self.model_used,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
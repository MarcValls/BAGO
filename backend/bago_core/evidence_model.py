#!/usr/bin/env python3
"""FASE 6.3: data model for the contract evidence bundle.

This module owns:
- ObjectiveProfile dataclass
- PROFILES registry
- ContractMockAdapter (the simulated provider used in tests)

Storage, IO and CLI live in:
- :mod:`bago_core.evidence_generator`
- :mod:`bago_core.evidence_cli`

R0-R10 modular rules:
- R0: <200 lines, no I/O
- R8: no `print()`, no `subprocess`
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from provider_adapter import (
    HealthStatus,
    ModelInfo,
    ProviderAdapter,
    ProviderResponse,
    TokenUsage,
)
from session_manager import ADAPTER_REGISTRY


@dataclass(frozen=True)
class ObjectiveProfile:
    objective_id: str
    title: str
    summary: str
    user_prompt: str
    plan_task: str
    knowledge_entry: str
    knowledge_query: str
    real_prompt: str


PROFILES: dict[str, ObjectiveProfile] = {
    "community-knowledge": ObjectiveProfile(
        objective_id="community-knowledge",
        title="Asistencia comunitaria basada en conocimiento abierto",
        summary=(
            "Demuestra que BAGO v4 puede asistir al usuario de forma directa "
            "con una respuesta util y de forma indirecta preservando conocimiento, "
            "planificacion y estado reproducible."
        ),
        user_prompt=(
            "Resume en dos frases como BAGO v4 puede ayudar a una comunidad abierta "
            "a convertir conocimiento disperso en acciones utiles para el usuario."
        ),
        plan_task=(
            "publicar una mejora pequena y verificable de conocimiento comunitario "
            "para que otro usuario la pueda reutilizar"
        ),
        knowledge_entry=(
            "BAGO v4 debe convertir una conversacion util en conocimiento recuperable "
            "y en un artefacto verificable para la comunidad."
        ),
        knowledge_query="conocimiento recuperable",
        real_prompt=(
            "En dos frases, explica como puedes asistir a un usuario mientras dejas "
            "una huella reutilizable para la comunidad."
        ),
    ),
}


class ContractMockAdapter(ProviderAdapter):
    """Adapter local para generar evidencia simulada usando el runtime real."""

    MODEL_ID = "contract-assistant-v1"

    def __init__(self, config: dict | None = None):
        super().__init__("mock-contract", config)

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
        last_user = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                last_user = str(message.get("content", ""))
                break

        content = self._respond(last_user)
        tokens_in = max(len(last_user) // 4, 1)
        tokens_out = max(len(content) // 4, 1)
        return ProviderResponse(
            content=content,
            model_used=model or self.MODEL_ID,
            provider=self.provider_name,
            finish_reason="stop",
            usage=TokenUsage(
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                total_tokens=tokens_in + tokens_out,
            ),
        )

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                model_id=self.MODEL_ID,
                wire_name=self.MODEL_ID,
                provider=self.provider_name,
                context_tokens=32768,
                max_output_tokens=4096,
                best_for="contract_validation",
                cost="free/local",
            )
        ]

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        return HealthStatus(
            ok=True,
            provider=self.provider_name,
            detail="Mock contract runtime ready",
            latency_ms=1.0,
            models_available=1,
        )

    def is_configured(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return True

    @staticmethod
    def _respond(prompt: str) -> str:
        normalized = prompt.lower().strip()
        if normalized.startswith("genera un plan paso a paso conciso"):
            return "\n".join([
                "1. Definir una necesidad concreta que ayude al usuario.",
                "2. Convertir la necesidad en una mejora pequena y verificable.",
                "3. Registrar el aprendizaje como conocimiento recuperable.",
                "4. Guardar la sesion y publicar la evidencia reutilizable.",
            ])
        if normalized.startswith("ejecuta este paso del plan:"):
            return "Paso ejecutado en modo simulado con trazabilidad reproducible."
        return (
            "BAGO v4 puede responder a una necesidad concreta del usuario y, al mismo tiempo, "
            "guardar el aprendizaje como conocimiento reutilizable para la comunidad. "
            "La evidencia valida que la ayuda ofrecida puede repetirse y auditarse."
        )


@contextmanager
def registered_mock_adapter():
    """Register ContractMockAdapter in the ADAPTER_REGISTRY for the duration of the with block.

    Used by the bundle generator to inject a deterministic provider when running
    in 'simulated' mode. The context manager is idempotent and safe to nest.
    """
    previous = ADAPTER_REGISTRY.get("mock-contract")
    ADAPTER_REGISTRY["mock-contract"] = ContractMockAdapter
    try:
        yield
    finally:
        if previous is None:
            ADAPTER_REGISTRY.pop("mock-contract", None)
        else:
            ADAPTER_REGISTRY["mock-contract"] = previous

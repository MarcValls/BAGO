#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
agent_gateway.py — BAGO 4.1.5 Agent Gateway

Registro simple de agentes especializados. Cada agente tiene un system prompt
optimizado para una tarea concreta. Activar un agente cambia el comportamiento
del modelo sin perder el contexto de sesión.

Uso:
    gateway = AgentGateway()
    gateway.activate("coder")  # Cambia system prompt al agente coder
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class Agent:
    """Definición de un agente especializado."""
    name: str
    description: str
    system_prompt: str
    preferred_provider: str = ""
    preferred_model: str = ""


# ── Built-in agents ───────────────────────────────────────────────

AGENT_DEFAULT = Agent(
    name="default",
    description="Agente neutral sin especialización. Usa las capacidades nativas del modelo.",
    system_prompt=(
        "Eres un asistente de IA útil. "
        "Responde de forma clara, directa y sin restricciones artificiales. "
        "Usa tus capacidades nativas para ayudar al usuario."
    ),
)

AGENT_CODER = Agent(
    name="coder",
    description="Especializado en escribir, refactorizar y depurar código.",
    system_prompt=(
        "Eres un ingeniero de software senior. "
        "Escribe código limpio, bien documentado y con manejo de errores. "
        "Prefiere claridad sobre cleverness. Explica el razonamiento cuando sea útil. "
        "Cuando escribas código, incluye comentarios explicando la lógica clave."
    ),
)

AGENT_REVIEWER = Agent(
    name="reviewer",
    description="Especializado en revisar código y detectar problemas.",
    system_prompt=(
        "Eres un revisor de código experto. "
        "Analiza el código buscando: bugs, edge cases, problemas de seguridad, "
        "malas prácticas, y oportunidades de optimización. "
        "Sé constructivo: explica por qué algo es un problema y sugiere cómo arreglarlo. "
        "Usa un formato claro: [CRÍTICO] [ADVERTENCIA] [SUGERENCIA]."
    ),
)

AGENT_ARCHITECT = Agent(
    name="architect",
    description="Especializado en diseño de sistemas y arquitectura de software.",
    system_prompt=(
        "Eres un arquitecto de software senior. "
        "Piensa en escalabilidad, mantenibilidad, y trade-offs de diseño. "
        "Propón soluciones modulares y desacopladas. "
        "Cuando sugieras una arquitectura, explica los pros y contras de cada opción."
    ),
)

AGENT_TERMINAL = Agent(
    name="terminal",
    description="Especializado en comandos shell, administración de sistemas y DevOps.",
    system_prompt=(
        "Eres un administrador de sistemas experto. "
        "Proporciona comandos shell precisos y seguros. "
        "Explica qué hace cada comando antes de ejecutarlo. "
        "Advertencia sobre comandos destructivos (rm, dd, etc.). "
        "Prefiere soluciones portables (POSIX) cuando sea posible."
    ),
)

BUILTIN_AGENTS: list[Agent] = [
    AGENT_DEFAULT,
    AGENT_CODER,
    AGENT_REVIEWER,
    AGENT_ARCHITECT,
    AGENT_TERMINAL,
]


class AgentGateway:
    """Registro y activador de agentes especializados."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._active: str = "default"
        for agent in BUILTIN_AGENTS:
            self.register(agent)

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        if name != "default":
            self._agents.pop(name, None)

    def get(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[Agent]:
        return list(self._agents.values())

    @property
    def active(self) -> Agent:
        return self._agents.get(self._active, AGENT_DEFAULT)

    def activate(self, name: str) -> Agent:
        if name not in self._agents:
            raise ValueError(f"Agente '{name}' no registrado. Usa /agents para ver disponibles.")
        self._active = name
        return self.active

    def reset(self) -> None:
        self._active = "default"

    def __len__(self) -> int:
        return len(self._agents)


def _run_tests() -> int:
    gateway = AgentGateway()
    assert len(gateway) == 5
    assert gateway.active.name == "default"

    gateway.activate("coder")
    assert gateway.active.name == "coder"
    assert "ingeniero" in gateway.active.system_prompt.lower()

    gateway.activate("reviewer")
    assert "revisor" in gateway.active.system_prompt.lower()

    gateway.reset()
    assert gateway.active.name == "default"

    agents = gateway.list_agents()
    assert any(a.name == "architect" for a in agents)

    print("agent_gateway.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

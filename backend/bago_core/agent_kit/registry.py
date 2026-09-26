"""In-memory registry of agents loaded from the catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bago_core.agent_kit.catalog import DEFAULT_CATALOG_PATH, list_agents, load_agent
from bago_core.agent_kit.errors import AgentKitError, AgentNotFound
from bago_core.agent_kit.models import AgentDefinition


class AgentRegistry:
    def __init__(self, catalog_path: Path | str | None = None):
        self.catalog_path = Path(catalog_path or DEFAULT_CATALOG_PATH)
        self._agents: dict[str, AgentDefinition] | None = None

    def refresh(self) -> None:
        self._agents = {a.id: a for a in list_agents(self.catalog_path)}

    def _ensure_loaded(self) -> None:
        if self._agents is None:
            self.refresh()

    def all(self) -> list[AgentDefinition]:
        self._ensure_loaded()
        return sorted(self._agents.values(), key=lambda a: a.id)

    def get(self, agent_id: str) -> AgentDefinition:
        self._ensure_loaded()
        agent_id = agent_id.lower().strip()
        if agent_id not in self._agents:
            # Try loading directly from disk before failing.
            try:
                agent = load_agent(self.catalog_path, agent_id)
                self._agents[agent.id] = agent
                return agent
            except AgentKitError as exc:
                raise AgentNotFound(f"agent {agent_id!r} not found in {self.catalog_path}") from exc
        return self._agents[agent_id]

    def filter_by_category(self, category: str) -> list[AgentDefinition]:
        category = category.lower().strip()
        return [a for a in self.all() if a.category == category]

    def categories(self) -> set[str]:
        return {a.category for a in self.all()}


def default_registry() -> AgentRegistry:
    return AgentRegistry()
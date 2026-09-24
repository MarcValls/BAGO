"""Custom exceptions for the BAGO agent kit."""


class AgentKitError(Exception):
    """Base exception."""


class CatalogNotFound(AgentKitError):
    """The agent catalog path does not exist or is unreadable."""


class AgentNotFound(AgentKitError):
    """Requested agent id is not present in the catalog."""


class AgentDefinitionError(AgentKitError):
    """Agent metadata is invalid or incomplete."""
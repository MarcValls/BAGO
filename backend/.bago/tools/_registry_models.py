"""_registry_models.py — Dataclasses for BAGO tool registry entries.

Internal module: import via tool_registry, not directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PreflightCheck:
    """A single declarative pre-flight condition."""
    kind: str       # "file" | "env" | "cmd"
    value: str      # path | env-var name | command name
    severity: str = "error"   # "error" | "warning"
    message: str = ""         # custom message (empty → auto-generated)


@dataclass
class ToolEntry:
    """Full descriptor for a user-facing BAGO tool."""
    cmd: str                              # Public CLI command (bago <cmd>)
    module: str                           # Python module stem (without .py)
    description: str
    preflight: list[PreflightCheck] = field(default_factory=list)
    schema: dict = field(default_factory=dict)   # Arg schema (future use)
    deprecated: bool = False              # True → mostrar hint al ejecutar
    see_also: str = ""                    # Comando grupo preferido
    layer: str = ""                       # Capa taxonómica
    scope: str = ""                       # Ámbito (framework|project|both)
    agent: str = ""                       # Agente responsable
    subscribes: list[str] = field(default_factory=list)
    # Kernel Lockdown (v3.2) — classification fields
    stability: str = "experimental"       # "core"|"experimental"|"legacy"|"internal"|"dangerous"
    risk: str = "safe"                    # "safe"|"mutating"|"dangerous"
    preflight_policy: str = "optional"   # "required"|"optional"|"none"
    supports_dry_run: bool = False
    layer_group: str = "core"             # "core"|"agents"|"ui"|"labs"

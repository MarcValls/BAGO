"""Shared runtime types for gateway-owned effect adapters."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from execution_request import ExecutionRequest
class ExecutionGatewayError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "execution_gateway_error",
        pre_dispatch: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.pre_dispatch = bool(pre_dispatch)
@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Trusted runtime dependencies, never part of user authority."""
    manager: Any = None
    services: Mapping[str, Any] = field(default_factory=dict)
class EffectAdapter(Protocol):
    effect_ids: frozenset[str]
    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        ...

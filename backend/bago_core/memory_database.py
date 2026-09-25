"""Interactive entry points for persistent memory database writes."""
from __future__ import annotations

from typing import Any

def execute_memory_database_cli(manager: Any, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from bago_core.cli_execution import execute_cli_effect
    from database_write_request import build_memory_database_request

    request = build_memory_database_request(
        manager,
        operation=operation,
        arguments=arguments,
        source_surface="cli.memory",
    )
    confirmation = {
        "knowledge.add": "guardar un recuerdo en la memoria persistente",
        "knowledge.delete": f"eliminar el recuerdo {arguments.get('memory_id')}",
        "knowledge.delete_many": f"eliminar {len(arguments.get('memory_ids', []))} recuerdos seleccionados",
        "knowledge.deprecate": f"retirar el recuerdo {arguments.get('memory_id')}",
        "knowledge.delete_by_source_prefix": "eliminar recuerdos por prefijo de sesión",
        "knowledge.hybrid_add": "guardar recuerdo y embedding asociados",
    }.get(operation, "escribir un embedding en la memoria persistente")
    result, _authorization = execute_cli_effect(
        request,
        confirmation_text=confirmation,
        manager=manager,
    )
    return result

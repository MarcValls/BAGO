"""One operation-bound authorization path for interactive BAGO CLI effects."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Callable

_CORE_MODULE_ROOT = Path(__file__).resolve().parents[1] / ".bago" / "core"
if str(_CORE_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_MODULE_ROOT))

from execution_adapter_contract import ExecutionContext
from execution_gateway import ExecutionGateway
from execution_request import ExecutionRequest


def execute_cli_effect(
    request: ExecutionRequest,
    *,
    confirmation_text: str,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], Any] | None = None,
    manager: Any = None,
) -> Any:
    """Challenge, obtain a TTY-only direct approval, then execute one request."""
    from authorization_boundary import AuthorizationBoundary, AuthorizationError

    if request.actor_kind != "user" or request.principal_id != "interactive-local-user":
        raise AuthorizationError("CLI approval requires an interactive user request", code="authorization_cli_actor_invalid")
    if not sys.stdin.isatty():
        raise AuthorizationError("CLI approval requires a TTY", code="authorization_cli_terminal_required")

    boundary = AuthorizationBoundary()
    interaction_id = f"cli-{uuid.uuid4().hex}"
    challenge = boundary.create_challenge(request, interaction_id=interaction_id)
    (output_fn or print)(
        f"\n⚠️ Autorización CLI requerida: {confirmation_text}\n"
        f"Efecto: {request.effect_id}; destino: {request.target}; "
        f"huella: {request.fingerprint[:16]}",
    )
    answer = (input_fn or input)("¿Autorizar esta operación exacta? [s/N]: ").strip().lower()
    if answer not in {"s", "si", "sí", "y", "yes"}:
        raise AuthorizationError("Operación rechazada por el usuario", code="authorization_cli_denied")
    approval = boundary.approve_cli_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id=interaction_id,
        session_id=request.session_id,
        terminal_confirmed=True,
    )
    return ExecutionGateway(boundary).execute(
        permit_token=str(approval["permit"]["token"]),
        request=request,
        context=ExecutionContext(manager=manager),
    )

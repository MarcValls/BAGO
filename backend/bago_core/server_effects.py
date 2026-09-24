"""Small server-owned effect helpers used by persistent BAGO state primitives.

The helpers construct canonical policy requests; they do not write files.
Materialization stays inside the registered ``ServerStateEffectAdapter``.
"""

from __future__ import annotations

import base64
import sys
import urllib.request
from pathlib import Path
from typing import Any

# The legacy runtime modules under ``backend/.bago/core`` are also launched
# directly by ``python -m bago_core...``. Bind that module root explicitly so
# the server-owned gateway is the same implementation in both launch modes.
_CORE_MODULE_ROOT = Path(__file__).resolve().parents[1] / ".bago" / "core"
if str(_CORE_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_MODULE_ROOT))

from execution_gateway import ExecutionContext, ExecutionGateway
from execution_request import build_execution_request


def _execute_text(
    path: Path,
    content: str,
    *,
    operation: str,
    effect_id: str,
    scope: str,
    source_surface: str,
    session_id: str,
    trusted_root: Path | None,
) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    root = Path(trusted_root or target.parent).expanduser().resolve()
    surface = str(source_surface or "atomic_json").strip()
    if not surface.startswith("server."):
        surface = f"server.{surface}"
    request = build_execution_request(
        effect_id=effect_id,
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=str(session_id or f"server-state:{root}"),
        source_surface=surface,
        target={
            "path": str(target),
            "allowed_root": str(root),
            "operation": operation,
        },
        arguments={"content": str(content)},
        scope=scope,
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(services={"_server_allowed_root": str(root)}),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Server-owned persistent effect returned no success receipt")
    return result


def write_text_atomic(
    path: Path,
    content: str,
    *,
    trusted_root: Path | None = None,
    source_surface: str = "atomic_json",
    session_id: str = "",
) -> dict[str, Any]:
    return _execute_text(
        path,
        content,
        operation="replace_text",
        effect_id="state.write",
        scope="session",
        source_surface=source_surface,
        session_id=session_id,
        trusted_root=trusted_root,
    )


def append_text_durable(
    path: Path,
    content: str,
    *,
    trusted_root: Path | None = None,
    source_surface: str = "atomic_json",
    session_id: str = "",
) -> dict[str, Any]:
    return _execute_text(
        path,
        content,
        operation="append_text",
        effect_id="state.write",
        scope="session",
        source_surface=source_surface,
        session_id=session_id,
        trusted_root=trusted_root,
    )


def gateway_urlopen(
    request: str | urllib.request.Request,
    *,
    timeout: float = 30.0,
    network_class: str = "provider_transport",
) -> Any:
    """Perform one classified BAGO transport request through the gateway."""

    if isinstance(request, urllib.request.Request):
        url = str(request.full_url)
        method = str(request.get_method() or "GET").upper()
        headers = {
            str(key): str(value)
            for key, value in {**request.unredirected_hdrs, **request.headers}.items()
        }
        data = request.data
    else:
        url = str(request)
        method = "GET"
        headers = {}
        data = None
    request_contract = build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=f"network:{network_class}",
        source_surface=f"server.network.{network_class}",
        target={
            "url": url,
            "method": method,
            "network_class": network_class,
            "timeout": float(timeout),
        },
        arguments={
            "headers": headers,
            "data_b64": base64.b64encode(data).decode("ascii") if isinstance(data, bytes) else "",
        },
        scope="external",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request_contract,
        context=ExecutionContext(),
    )
    return result


__all__ = ["append_text_durable", "gateway_urlopen", "write_text_atomic"]

"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
import base64
import urllib.error
import urllib.request
from typing import Any, Mapping
from execution_request import ExecutionRequest


class GatewayHTTPResponse:
    """urllib-compatible response proxy that preserves incremental reads."""

    def __init__(self, response: Any, *, status: int, headers: Mapping[str, Any], url: str) -> None:
        self._response = response
        self.status = int(status)
        self.code = self.status
        self.headers = headers
        self.url = str(url)

    def read(self, amount: int = -1) -> bytes:
        try:
            return self._response.read(amount)
        except TypeError:
            return self._response.read()

    def readinto(self, buffer: Any) -> int:
        reader = getattr(self._response, "readinto", None)
        if callable(reader):
            return int(reader(buffer))
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def close(self) -> None:
        close = getattr(self._response, "close", None)
        if callable(close):
            return close()
        return None

    def __enter__(self) -> "GatewayHTTPResponse":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def __iter__(self):
        return iter(self._response)


class NetworkReadEffectAdapter:
    """Server-owned policy adapter for approved BAGO transport reads.

    Provider inference calls may use HTTP POST at the transport layer, but
    this adapter is only reachable for an explicitly classified BAGO transport
    surface. Release, GitHub and arbitrary external mutations remain outside
    this policy adapter and must use their explicit effects in later waves.
    """

    effect_ids = frozenset({"network.read"})
    server_policy_only = True
    _ALLOWED_CLASSES = frozenset({"provider_transport", "runtime_probe", "local_discovery"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Network read requires server-owned policy authorization",
                code="network_read_authorization_required",
            )
        network_class = str(request.target.get("network_class") or "").strip()
        if network_class not in self._ALLOWED_CLASSES:
            raise ExecutionGatewayError(
                "Network target is not an approved BAGO transport surface",
                code="network_read_surface_blocked",
            )
        url = str(request.target.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            raise ExecutionGatewayError(
                "Network target must use HTTP(S)",
                code="network_read_url_invalid",
            )
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        method = str(request.target.get("method") or "GET").upper()
        headers = arguments.get("headers") if isinstance(arguments.get("headers"), dict) else {}
        encoded_data = str(arguments.get("data_b64") or "")
        try:
            data = base64.b64decode(encoded_data) if encoded_data else None
            outbound = urllib.request.Request(
                url,
                data=data,
                headers={str(key): str(value) for key, value in headers.items()},
                method=method,
            )
            timeout = float(request.target.get("timeout") or 30.0)
            response = urllib.request.urlopen(outbound, timeout=timeout)
            raw_headers = getattr(response, "headers", {})
            response_headers = raw_headers if hasattr(raw_headers, "items") else dict(raw_headers)
            getcode = getattr(response, "getcode", None)
            status = int(getattr(response, "status", getcode() if callable(getcode) else 200))
            geturl = getattr(response, "geturl", None)
            final_url = str(geturl() if callable(geturl) else url)
        except ExecutionGatewayError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError):
            # Preserve urllib's typed transport errors for provider retry and
            # fallback policies; the effect has already been authorized and
            # no caller-side sink is reintroduced by re-raising the error.
            raise
        except OSError:
            # Local discovery and provider fallback already treat transport
            # availability as a recoverable OSError boundary. Preserve that
            # contract after the server-owned dispatch.
            raise
        except Exception as exc:
            raise ExecutionGatewayError(
                f"Network read failed: {exc}",
                code="network_read_failed",
            ) from exc
        return GatewayHTTPResponse(
            response,
            status=status,
            headers=response_headers,
            url=final_url,
        )

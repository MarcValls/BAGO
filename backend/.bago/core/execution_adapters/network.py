"""Registered server-owned effect adapters for this domain."""
from __future__ import annotations

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
import base64
import urllib.error
import urllib.request
from typing import Any, Mapping
from urllib.parse import urlparse
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


class _ReleaseRedirectGuard(urllib.request.HTTPRedirectHandler):
    """Keep release traffic on the fixed GitHub hosts approved by policy."""

    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        super().__init__()
        self._allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(str(newurl))
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self._allowed_hosts:
            raise ExecutionGatewayError(
                "Release redirect target is outside the approved GitHub hosts",
                code="network_read_redirect_blocked",
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NetworkReadEffectAdapter:
    """Server-owned policy adapter for approved BAGO transport reads.

    Provider inference calls may use HTTP POST at the transport layer, but
    this adapter is only reachable for an explicitly classified BAGO transport
    surface. Release traffic is limited to fixed HTTPS GitHub hosts and
    read-only methods; arbitrary external mutations remain outside this
    policy adapter and must use their explicit effects.
    """

    effect_ids = frozenset({"network.read"})
    server_policy_only = True
    _ALLOWED_CLASSES = frozenset({
        "provider_transport",
        "runtime_probe",
        "local_discovery",
        "release_metadata",
        "release_asset_download",
    })
    _RELEASE_METADATA_HOSTS = frozenset({"api.github.com"})
    _RELEASE_ASSET_HOSTS = frozenset({
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    })

    @classmethod
    def _release_hosts(cls, network_class: str) -> frozenset[str] | None:
        if network_class == "release_metadata":
            return cls._RELEASE_METADATA_HOSTS
        if network_class == "release_asset_download":
            return cls._RELEASE_ASSET_HOSTS
        return None

    @classmethod
    def validate_release_download_url(cls, url: str) -> str:
        parsed = urlparse(str(url or "").strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in cls._RELEASE_ASSET_HOSTS:
            raise ExecutionGatewayError(
                "Release URL is outside the approved GitHub hosts",
                code="network_read_release_host_blocked",
            )
        return parsed.geturl()

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
        release_hosts = self._release_hosts(network_class)
        parsed_url = urlparse(url)
        if network_class == "release_asset_download":
            self.validate_release_download_url(url)
        if release_hosts is not None and (
            parsed_url.scheme != "https"
            or (parsed_url.hostname or "").lower() not in release_hosts
        ):
            raise ExecutionGatewayError(
                "Release URL is outside the approved GitHub hosts",
                code="network_read_release_host_blocked",
            )
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        method = str(request.target.get("method") or "GET").upper()
        if release_hosts is not None and method not in {"GET", "HEAD"}:
            raise ExecutionGatewayError(
                "Release transport only allows read methods",
                code="network_read_release_method_blocked",
            )
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
            if release_hosts is None:
                response = urllib.request.urlopen(outbound, timeout=timeout)
            else:
                opener = urllib.request.build_opener(_ReleaseRedirectGuard(release_hosts))
                response = opener.open(outbound, timeout=timeout)
            raw_headers = getattr(response, "headers", {})
            response_headers = raw_headers if hasattr(raw_headers, "items") else dict(raw_headers)
            getcode = getattr(response, "getcode", None)
            status = int(getattr(response, "status", getcode() if callable(getcode) else 200))
            geturl = getattr(response, "geturl", None)
            final_url = str(geturl() if callable(geturl) else url)
            if release_hosts is not None:
                final = urlparse(final_url)
                if final.scheme != "https" or (final.hostname or "").lower() not in release_hosts:
                    response.close()
                    raise ExecutionGatewayError(
                        "Release response resolved outside the approved GitHub hosts",
                        code="network_read_release_redirect_blocked",
                    )
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

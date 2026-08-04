"""HTTP lifecycle for user-installed Capability Packages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _send(handler: "BaseHTTPRequestHandler", operation: Callable[[], Any]) -> None:
    from api_serializers import send_json
    from capability_packages import CapabilityPackageError

    try:
        payload = operation()
    except CapabilityPackageError as exc:
        status = 404 if exc.code == "not_found" else 409 if exc.code == "version_conflict" else 400
        send_json(handler, status, {"ok": False, "error": str(exc), "code": exc.code})
        return
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"Error interno de Capability Packages: {exc}"})
        return
    send_json(handler, 200, payload)


def handle_list(handler: "BaseHTTPRequestHandler") -> None:
    from capability_packages import list_packages
    _send(handler, lambda: {"ok": True, "packages": list_packages()})


def handle_get(handler: "BaseHTTPRequestHandler", capability_id: str) -> None:
    from capability_packages import get_package
    _send(handler, lambda: {"ok": True, "package": get_package(capability_id)})


def handle_receipts(handler: "BaseHTTPRequestHandler") -> None:
    from capability_packages import list_receipts
    _send(handler, lambda: {"ok": True, "receipts": list_receipts()})


def handle_import(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from capability_packages import import_package
    _send(handler, lambda: import_package(
        content_base64=str((body or {}).get("content_base64") or ""),
        file_name=str((body or {}).get("file_name") or ""),
        confirm_trust=(body or {}).get("confirm_trust") is True,
    ))


def handle_enable(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from capability_packages import set_enabled
    enabled = (body or {}).get("enabled")
    if not isinstance(enabled, bool):
        from api_serializers import send_json
        send_json(handler, 400, {"ok": False, "error": "enabled debe ser boolean", "code": "invalid_request"})
        return
    _send(handler, lambda: {"ok": True, "package": set_enabled(capability_id, enabled)})


def handle_configure(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from capability_packages import configure_package
    _send(handler, lambda: {"ok": True, "package": configure_package(capability_id, (body or {}).get("config", {}))})


def handle_execute(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from capability_packages import execute_package
    _send(handler, lambda: execute_package(
        capability_id,
        inputs=(body or {}).get("input", {}),
        confirmed=(body or {}).get("confirmed") is True,
        approved_permissions=(body or {}).get("approved_permissions", []),
    ))

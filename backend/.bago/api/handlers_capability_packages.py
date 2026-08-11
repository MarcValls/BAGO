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


def handle_examples(handler: "BaseHTTPRequestHandler") -> None:
    from capability_packages import list_example_packages
    _send(handler, lambda: {"ok": True, "examples": list_example_packages()})


def handle_install_example(handler: "BaseHTTPRequestHandler", package_id: str, body: dict[str, Any]) -> None:
    from capability_packages import install_example_package
    _send(handler, lambda: install_example_package(package_id))


def handle_import(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from capability_packages import import_package
    _send(handler, lambda: import_package(
        content_base64=str((body or {}).get("content_base64") or ""),
        file_name=str((body or {}).get("file_name") or ""),
        confirm_trust=(body or {}).get("confirm_trust") is True,
    ))


def handle_inspect(handler: "BaseHTTPRequestHandler", body: dict[str, Any]) -> None:
    from capability_packages import inspect_package
    _send(handler, lambda: inspect_package(
        content_base64=str((body or {}).get("content_base64") or ""),
        file_name=str((body or {}).get("file_name") or ""),
    ))


def handle_export(handler: "BaseHTTPRequestHandler", capability_id: str) -> None:
    from capability_packages import export_package
    _send(handler, lambda: export_package(capability_id))


def handle_enable(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from capability_packages import set_enabled
    enabled = (body or {}).get("enabled")
    if not isinstance(enabled, bool):
        from api_serializers import send_json
        send_json(handler, 400, {"ok": False, "error": "enabled debe ser boolean", "code": "invalid_request"})
        return
    _send(handler, lambda: {"ok": True, "package": set_enabled(
        capability_id,
        enabled,
        confirm_trust=(body or {}).get("confirm_trust") is True,
    )})


def handle_configure(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from capability_packages import configure_package
    _send(handler, lambda: {"ok": True, "package": configure_package(capability_id, (body or {}).get("config", {}))})


def handle_execute(handler: "BaseHTTPRequestHandler", capability_id: str, body: dict[str, Any]) -> None:
    from api_state import get_mgr
    from capability_packages import execute_package, execute_pipeline_package, get_package

    def execute() -> dict[str, Any]:
        arguments = {
            "inputs": (body or {}).get("input", {}),
            "confirmed": (body or {}).get("confirmed") is True,
            "approved_permissions": (body or {}).get("approved_permissions", []),
        }
        if get_package(capability_id)["kind"] == "pipeline":
            return execute_pipeline_package(capability_id, manager=get_mgr(handler), **arguments)
        return execute_package(capability_id, **arguments)

    _send(handler, execute)

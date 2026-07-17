"""handlers_audit.py - Project and runtime audit endpoints for BAGO."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


ROOT_DIR = Path(__file__).resolve().parents[2]


def _mgr(handler):
    from api_state import get_mgr

    return get_mgr(handler)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _read_json(file_path: Path) -> dict[str, Any]:
    try:
        return json.loads(_read_text(file_path) or "{}")
    except Exception:
        return {}


def _normalize_version(value: Any) -> str:
    return str(value or "").strip().lstrip("vV")


def _extract_version(text: str) -> str:
    for line in str(text or "").splitlines():
        clean = line.strip()
        if clean.lower().startswith("version"):
            parts = clean.split(":", 1)
            if len(parts) == 2:
                return _normalize_version(parts[1])
    return ""


def _make_finding(severity: str, scope: str, code: str, title: str, detail: str, file: str = "") -> dict[str, Any]:
    return {
        "severity": severity,
        "scope": scope,
        "code": code,
        "title": title,
        "detail": detail,
        "file": file,
    }


def _project_audit() -> dict[str, Any]:
    pkg = _read_json(ROOT_DIR / "package.json")
    package_version = _normalize_version(pkg.get("version", ""))
    release_version = _normalize_version(_read_text(ROOT_DIR / "release_version.txt"))
    latest_yml = _read_text(ROOT_DIR / "dist" / "latest.yml")
    readme = _read_text(ROOT_DIR / "README.md")
    manual = _read_text(ROOT_DIR / "MANUAL.md")
    html = _read_text(ROOT_DIR / "manager" / "index.html")
    findings: list[dict[str, Any]] = []

    if package_version and release_version and package_version != release_version:
        findings.append(_make_finding("high", "project", "VERSION_DRIFT", "package.json y release_version.txt no coinciden", f"{package_version} vs {release_version}", "package.json"))

    dist_version = _extract_version(latest_yml)
    if package_version and dist_version and package_version != dist_version:
        findings.append(_make_finding("high", "project", "DIST_DRIFT", "dist/latest.yml desalineado", f"{package_version} vs {dist_version}", "dist/latest.yml"))

    release_notes = ROOT_DIR / "docs" / f"RELEASE_NOTES_{package_version}.md"
    if package_version and not release_notes.exists():
        findings.append(_make_finding("medium", "project", "MISSING_RELEASE_NOTES", "Faltan notas de release canónicas", f"No existe {release_notes.relative_to(ROOT_DIR)}", str(release_notes)))

    if html.count('id="pm-detail"') > 1:
        findings.append(_make_finding("high", "project", "DUPLICATE_DETAIL", "pm-detail duplicado", "id=\"pm-detail\" aparece más de una vez", "manager/index.html"))

    if package_version and package_version not in readme:
        findings.append(_make_finding("low", "project", "README_VERSION", "README no menciona la versión actual", f"No aparece {package_version}", "README.md"))

    if package_version and package_version not in manual:
        findings.append(_make_finding("low", "project", "MANUAL_VERSION", "MANUAL no menciona la versión actual", f"No aparece {package_version}", "MANUAL.md"))

    return {
        "scope": "project",
        "checked_at": _now(),
        "root": str(ROOT_DIR),
        "version": package_version or "unknown",
        "summary": {
            "findings": len(findings),
            "high": sum(1 for item in findings if item["severity"] == "high"),
            "medium": sum(1 for item in findings if item["severity"] == "medium"),
            "low": sum(1 for item in findings if item["severity"] == "low"),
        },
        "sources": {
            "package_json": bool(pkg),
            "release_version": release_version or "",
            "dist_latest": dist_version or "",
            "readme_has_version": bool(package_version and package_version in readme),
            "manual_has_version": bool(package_version and package_version in manual),
        },
        "findings": findings,
    }


def _bago_audit(mgr: Any) -> dict[str, Any]:
    status = mgr.status()
    workspace_state = status.get("workspace_state") or getattr(mgr, "workspace_state", lambda: {})()
    framework_root = Path(str(status.get("framework_root") or ROOT_DIR)).resolve()
    runtime_version = _normalize_version(_read_text(framework_root / "release_version.txt"))
    has_manifest = bool(workspace_state.get("manifest_exists", False) or (framework_root / ".gabo" / "workspace.json").exists())
    has_launcher = (framework_root / "bago_core" / "launcher.py").exists()
    findings: list[dict[str, Any]] = []

    if not has_launcher:
        findings.append(_make_finding("high", "bago", "MISSING_LAUNCHER", "Falta launcher en el runtime", "No existe bago_core/launcher.py en la instalación detectada", str(framework_root)))
    if not has_manifest:
        findings.append(_make_finding("medium", "bago", "NO_MANIFEST", "La instalación no tiene manifiesto", "workspace.json no existe en el estado activo", str(framework_root)))
    if not bool(workspace_state.get("binding_confirmed", False)):
        findings.append(_make_finding("high", "bago", "BINDING_UNCONFIRMED", "Binding no confirmado", str(workspace_state.get("binding_reason", "sin motivo")), "workspace_state"))

    return {
        "scope": "bago",
        "checked_at": _now(),
        "runtime_root": str(framework_root),
        "repo_root": str(ROOT_DIR),
        "version": _normalize_version(status.get("version") or status.get("framework_version") or "") or "unknown",
        "summary": {
            "findings": len(findings),
            "high": sum(1 for item in findings if item["severity"] == "high"),
            "medium": sum(1 for item in findings if item["severity"] == "medium"),
            "low": sum(1 for item in findings if item["severity"] == "low"),
        },
        "health": {
            "ok": bool(workspace_state.get("binding_confirmed", False)),
            "detail": str(status.get("binding_reason") or workspace_state.get("binding_reason") or "unconfirmed"),
        },
        "sources": {
            "runtime_version": runtime_version or "",
            "manifest": has_manifest,
            "launcher": has_launcher,
        },
        "findings": findings,
    }


def _event_ledger(mgr: Any, limit: int = 60) -> dict[str, Any]:
    status = mgr.status()
    history = list(getattr(getattr(mgr, "store", None), "get_history", lambda: [])() or [])
    entries: list[dict[str, Any]] = []
    for message in history[-limit:]:
        if not isinstance(message, dict):
            continue
        entries.append({
            "timestamp": str(message.get("timestamp") or message.get("created_at") or ""),
            "scope": "history",
            "action": str(message.get("role") or message.get("type") or "message"),
            "detail": str(message.get("content") or message.get("text") or message.get("message") or ""),
            "source": "history",
            "severity": "info",
        })
    if status.get("binding_reason"):
        entries.append({
            "timestamp": str(status.get("created_at") or ""),
            "scope": "workspace",
            "action": "binding_reason",
            "detail": str(status.get("binding_reason")),
            "source": "status",
            "severity": "warn",
        })
    return {
        "scope": "ledger",
        "checked_at": _now(),
        "entries": entries[:limit],
        "summary": {"entries": len(entries)},
    }


def handle_project(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    send_json(handler, 200, {"ok": True, "audit": _project_audit()})


def handle_bago(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    send_json(handler, 200, {"ok": True, "audit": _bago_audit(mgr)})


def handle_ledger(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    import urllib.parse as _up

    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"ok": False, "error": "SessionManager no disponible"})
        return
    q = _up.parse_qs(_up.urlparse(handler.path).query)
    limit = int(str(q.get("limit", ["60"])[0] or "60"))
    send_json(handler, 200, {"ok": True, "ledger": _event_ledger(mgr, limit=max(1, min(limit, 200)))})

"""GitHub capabilities exposed to the UI through the authenticated gh CLI."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

from handler_support import safe_handler
from api_response import send_error
from bago_core.atomic_json import write_json_atomic

_REPO_FILE = ".bago_github_repo.json"
_REPO_RE = re.compile(r"^(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def _state(handler) -> Path:
    from api_state import resolve_state_root
    return Path(resolve_state_root(handler))


def _run_gh(handler, args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run fixed GitHub reads through the registered process.inspect owner."""
    from api_state import get_mgr
    from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
    from execution_gateway import ExecutionGateway
    from execution_request import build_execution_request
    from execution_adapters.process import ProcessExecutionEffectAdapter

    manager = get_mgr(handler)
    if manager is None or not ProcessExecutionEffectAdapter.is_read_only_github_argv(args):
        return 126, "", "Esta operación gh no está permitida como inspección de servidor"
    try:
        request = build_execution_request(
            effect_id="process.inspect", actor_kind="server", principal_id="bago-runtime",
            session_id=str(getattr(manager, "session_id", "") or ""),
            source_surface="server.process.inspect",
            target={
                "operation": "gh", "executable": "gh",
                "cwd": str(getattr(manager, "base_path", "") or ""),
                "timeout_seconds": min(max(int(timeout), 1), 30),
            }, arguments={"argv": args}, scope="workspace",
        )
        result, _authorization = ExecutionGateway().execute_server_owned(
            request=request, context=ExecutionContext(manager=manager),
        )
        return int(result.get("exit_code", 1)), str(result.get("stdout", "")).strip(), str(result.get("stderr", "")).strip()
    except (ExecutionGatewayError, ValueError, TypeError) as exc:
        return 126, "", str(exc)


def _repo_value(value: object) -> str:
    match = _REPO_RE.match(str(value or "").strip())
    if not match:
        raise ValueError("Usa owner/repo o una URL de GitHub válida")
    return f"{match.group(1)}/{match.group(2)}"


def _saved_repo(state: Path) -> str | None:
    path = state / _REPO_FILE
    if path.exists():
        try:
            return str(json.loads(path.read_text(encoding="utf-8")).get("repo") or "") or None
        except Exception:
            return None
    return None


def _send(handler, code: int, payload: dict) -> None:
    from api_serializers import send_json
    send_json(handler, code, payload)


@safe_handler
def handle_status(handler: "BaseHTTPRequestHandler") -> None:
    state = _state(handler)
    code, output, error = _run_gh(handler, ["auth", "status"])
    repo = _saved_repo(state)
    details = None
    if repo and code == 0:
        rcode, raw, _ = _run_gh(handler, ["api", f"repos/{repo}"])
        if rcode == 0:
            try:
                details = json.loads(raw)
            except json.JSONDecodeError:
                details = None
    _send(handler, 200, {"ok": True, "authenticated": code == 0, "repo": repo, "repository": details, "error": error or None})


@safe_handler
def handle_connect(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    try:
        repo = _repo_value(body.get("repo"))
    except ValueError as exc:
        send_error(handler, 400, "invalid_repository", str(exc))
        return
    code, raw, error = _run_gh(handler, ["api", f"repos/{repo}"])
    if code != 0:
        send_error(handler, 403 if code == 4 else 400, "github_repository_unavailable", error or raw or "No se pudo leer el repositorio")
        return
    try:
        details = json.loads(raw)
    except json.JSONDecodeError:
        send_error(handler, 502, "github_invalid_response", "GitHub devolvió una respuesta no válida")
        return
    state = _state(handler)
    # The canonical state.write adapter creates this parent directory as part
    # of the same server-owned materialization; do not split a second writer.
    write_json_atomic(state / _REPO_FILE, {"repo": repo})
    _send(handler, 200, {"ok": True, "repo": repo, "repository": details, "knowledge_source": f"github:{repo}"})


@safe_handler
def handle_contents(handler: "BaseHTTPRequestHandler") -> None:
    from urllib.parse import parse_qs, urlparse
    query = parse_qs(urlparse(handler.path).query)
    repo = _saved_repo(_state(handler))
    path = str(query.get("path", [""])[0]).strip()
    if not repo:
        _send(handler, 409, {"ok": False, "error": "Vincula un repositorio primero"})
        return
    endpoint = f"repos/{repo}/contents/{path}" if path else f"repos/{repo}/readme"
    code, raw, error = _run_gh(handler, ["api", endpoint])
    if code != 0:
        _send(handler, 400, {"ok": False, "error": error or raw})
        return
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and payload.get("content"):
            payload["decoded_content"] = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        _send(handler, 200, {"ok": True, "repo": repo, "path": path or "README", "content": payload})
    except json.JSONDecodeError:
        _send(handler, 502, {"ok": False, "error": "GitHub devolvió una respuesta no válida"})


@safe_handler
def handle_create(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    _send(handler, 410, {"ok": False, "error": "La creación de repositorios requiere el cliente Desktop y su autorización de proceso."})


@safe_handler
def handle_auth_start(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Initiate GitHub authentication via gh CLI — returns auth URL for manual flow."""
    _send(handler, 200, {
        "ok": True,
        "auth_url": "https://github.com/login/device/code",
        "instructions": "Ejecuta `gh auth login` en tu terminal o visita la URL proporcionada por `gh auth login`.",
    })


@safe_handler
def handle_auth_refresh(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Refresh gh auth token by re-checking auth status."""
    code, output, error = _run_gh(handler, ["auth", "status"])
    _send(handler, 200, {
        "ok": True,
        "authenticated": code == 0,
        "output": output,
        "error": error or None,
    })


@safe_handler
def handle_auth_logout(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    _send(handler, 410, {"ok": False, "error": "El cierre de sesión requiere el cliente Desktop y su autorización de proceso."})


@safe_handler
def handle_setup(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    _send(handler, 410, {"ok": False, "error": "La configuración de credenciales requiere el cliente Desktop y su autorización de proceso."})


@safe_handler
def handle_mcp_create(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    _send(handler, 410, {"ok": False, "error": "La ruta de creación MCP fue retirada; usa la acción Desktop gobernada."})


# ─── GitHub Auth State ──────────────────────────────────────────────────

# Fields that are NEVER exposed
_FORBIDDEN_FIELDS = frozenset([
    "token", "pat", "secret", "accessToken", "oauthToken",
    "refresh_token", "credential", "auth_method",
])


def _scrub_payload(payload: dict) -> dict:
    """Remove any forbidden fields from a dict before sending to client."""
    return {k: v for k, v in payload.items() if k not in _FORBIDDEN_FIELDS}


def _parse_status_hosts(output: str) -> dict[str, list[dict]]:
    """Parse `gh auth status --json hosts` output into a hostname -> accounts map."""
    try:
        data = json.loads(output) if output else {}
    except json.JSONDecodeError:
        return {}
    hosts = data.get("hosts", {}) if isinstance(data, dict) else {}
    if not isinstance(hosts, dict):
        return {}
    return {str(host): [a for a in (accts or []) if isinstance(a, dict)] for host, accts in hosts.items()}


def _valid_accounts(hosts: dict[str, list[dict]]) -> list[dict]:
    return [acct for accts in hosts.values() for acct in accts if acct.get("state") == "success"]


def _credential_storage_for(account: dict) -> str:
    """Map the account tokenSource reported by gh to the public credentialStorage contract."""
    src = str(account.get("tokenSource") or "")
    if not src:
        return "unknown"
    low = src.lower()
    if "keyring" in low or "keychain" in low:
        return "secure"
    if "_TOKEN" in src or src.startswith(("GH_", "GITHUB_", "COPILOT_")):
        return "unknown"  # environment-provided, not stored locally
    return "plaintext"  # remaining sources are on-disk config files


def _extract_auth_info(code: int, output: str, error: str) -> dict:
    """Extract auth info from `gh auth status --json hosts`, never exposing tokens.

    With --json, gh exits zero even when there are authentication issues, so
    `authenticated` is derived strictly from the hosts/accounts payload.
    """
    checked_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    if code == 127:
        return {
            "installed": False,
            "authenticated": False,
            "credentialStorage": "unknown",
            "error": error or "gh no está instalado",
            "checkedAt": checked_at,
        }

    hosts = _parse_status_hosts(output)
    valid = _valid_accounts(hosts)

    if not valid:
        return {
            "installed": True,
            "authenticated": False,
            "credentialStorage": "unknown",
            "error": error or None,
            "checkedAt": checked_at,
        }

    active = next((a for a in valid if a.get("active")), valid[0])
    username = str(active.get("login") or "") or None
    hostname = str(active.get("host") or "") or None
    scopes = [s.strip() for s in str(active.get("scopes") or "").split(",") if s.strip()]

    return {
        "installed": True,
        "authenticated": True,
        "hostname": hostname,
        "username": username,
        "activeAccount": username,
        "scopes": scopes,
        "credentialStorage": _credential_storage_for(active),
        "error": None,
        "checkedAt": checked_at,
    }


# ─── GET /github/status ─────────────────────────────────────────────────


@safe_handler
def handle_github_status(handler: "BaseHTTPRequestHandler") -> None:
    """Return GitHub auth state — no secrets exposed.

    Keeps the previous /github/status contract (repo/repository fields) while
    reporting the richer auth-panel state derived from the hosts payload.
    """
    code, output, error = _run_gh(handler, ["auth", "status", "--json", "hosts"])
    info = _extract_auth_info(code, output, error)
    repo = _saved_repo(_state(handler))
    repository = None
    if repo and info.get("authenticated"):
        rcode, raw, _ = _run_gh(handler, ["api", f"repos/{repo}"])
        if rcode == 0:
            try:
                repository = json.loads(raw)
            except json.JSONDecodeError:
                repository = None
    _send(handler, 200, {"ok": True, **_scrub_payload(info), "repo": repo, "repository": repository})


# ─── POST /github/auth/start ───────────────────────────────────────────


@safe_handler
def handle_github_auth_start(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    _send(handler, 410, {"ok": False, "error": "La autenticación requiere el cliente Desktop y su autorización de proceso."})


# ─── POST /github/auth/refresh ─────────────────────────────────────────


@safe_handler
def handle_github_auth_refresh(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Refresh GitHub auth by re-checking status."""
    handle_github_status(handler)


# ─── POST /github/auth/logout ─────────────────────────────────────────


@safe_handler
def handle_github_auth_logout(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    _send(handler, 410, {"ok": False, "error": "El cierre de sesión requiere el cliente Desktop y su autorización de proceso."})


# ─── POST /github/setup-git ────────────────────────────────────────────


@safe_handler
def handle_github_setup_git(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    _send(handler, 410, {"ok": False, "error": "La identidad Git requiere el cliente Desktop y su autorización de proceso."})


# ─── GET /github/accounts ──────────────────────────────────────────────


@safe_handler
def handle_github_accounts(handler: "BaseHTTPRequestHandler") -> None:
    """List all configured GitHub accounts."""
    code, output, error = _run_gh(handler, ["auth", "status", "--json", "hosts"])
    if code != 0:
        _send(handler, 200, {"ok": True, "accounts": [], "count": 0, "error": error or None})
        return

    try:
        hosts = _parse_status_hosts(output)
        safe_accounts = []
        for host, accounts in sorted(hosts.items()):
            for acct in accounts:
                login = str(acct.get("login") or "") or None
                safe_accounts.append({
                    "username": login,
                    "name": login,
                    "active": bool(acct.get("active")) and acct.get("state") == "success",
                    "hostname": str(acct.get("host") or host),
                })
        _send(handler, 200, {
            "ok": True,
            "accounts": safe_accounts,
            "count": len(safe_accounts),
        })
    except Exception as exc:
        _send(handler, 200, {"ok": True, "accounts": [], "count": 0, "error": str(exc)})

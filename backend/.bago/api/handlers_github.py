"""GitHub capabilities exposed to the UI through the authenticated gh CLI."""
from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

_REPO_FILE = ".bago_github_repo.json"
_REPO_RE = re.compile(r"^(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def _state(handler) -> Path:
    from api_state import resolve_state_root
    return Path(resolve_state_root(handler))


def _run_gh(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "gh no está instalado"
    except subprocess.TimeoutExpired:
        return 124, "", "GitHub tardó demasiado en responder"


def _repo_value(value: object) -> str:
    match = _REPO_RE.match(str(value or "").strip())
    if not match:
        raise ValueError("Usa owner/repo o una URL de GitHub válida")
    return f"{match.group(1)}/{match.group(2)}"


def _extract_github_url(raw: str) -> str:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    for line in lines:
        parsed = urlparse(line)
        host = (parsed.hostname or "").lower()
        if parsed.scheme in ("http", "https") and (host == "github.com" or host.endswith(".github.com")):
            return line
    return lines[-1] if lines else ""


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


def handle_status(handler: "BaseHTTPRequestHandler") -> None:
    state = _state(handler)
    code, output, error = _run_gh(["auth", "status"])
    repo = _saved_repo(state)
    details = None
    if repo and code == 0:
        rcode, raw, _ = _run_gh(["api", f"repos/{repo}"])
        if rcode == 0:
            try:
                details = json.loads(raw)
            except json.JSONDecodeError:
                details = None
    _send(handler, 200, {"ok": True, "authenticated": code == 0, "repo": repo, "repository": details, "error": error or None})


def handle_connect(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    try:
        repo = _repo_value(body.get("repo"))
    except ValueError as exc:
        _send(handler, 400, {"ok": False, "error": str(exc)})
        return
    code, raw, error = _run_gh(["api", f"repos/{repo}"])
    if code != 0:
        _send(handler, 403 if code == 4 else 400, {"ok": False, "error": error or raw or "No se pudo leer el repositorio"})
        return
    try:
        details = json.loads(raw)
    except json.JSONDecodeError:
        _send(handler, 502, {"ok": False, "error": "GitHub devolvió una respuesta no válida"})
        return
    state = _state(handler)
    state.mkdir(parents=True, exist_ok=True)
    (state / _REPO_FILE).write_text(json.dumps({"repo": repo}, ensure_ascii=False, indent=2), encoding="utf-8")
    _send(handler, 200, {"ok": True, "repo": repo, "repository": details, "knowledge_source": f"github:{repo}"})


def handle_contents(handler: "BaseHTTPRequestHandler") -> None:
    from urllib.parse import parse_qs, urlparse
    query = parse_qs(urlparse(handler.path).query)
    repo = _saved_repo(_state(handler))
    path = str(query.get("path", [""])[0]).strip()
    if not repo:
        _send(handler, 409, {"ok": False, "error": "Vincula un repositorio primero"})
        return
    endpoint = f"repos/{repo}/contents/{path}" if path else f"repos/{repo}/readme"
    code, raw, error = _run_gh(["api", endpoint])
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


def handle_create(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    name = str(body.get("name") or "").strip()
    if not re.match(r"^[A-Za-z0-9_.-]{1,100}$", name):
        _send(handler, 400, {"ok": False, "error": "Nombre de repositorio no válido"})
        return
    visibility = "--private" if bool(body.get("private", True)) else "--public"
    args = ["repo", "create", name, visibility]
    description = str(body.get("description") or "").strip()
    if description:
        args.extend(["--description", description[:500]])
    code, raw, error = _run_gh(args)
    if code != 0:
        _send(handler, 403, {"ok": False, "error": error or raw or "No se pudo crear el repositorio; revisa tus permisos"})
        return
    url = _extract_github_url(raw)
    _send(handler, 200, {"ok": True, "url": url, "output": raw})


def handle_mcp_create(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Invoke the same explicit write policy through BAGO's MCP tool surface."""
    try:
        import importlib.util
        mcp_path = Path(__file__).resolve().parents[1] / "mcp" / "bago_mcp_server.py"
        spec = importlib.util.spec_from_file_location("bago_mcp_server_ui", mcp_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("MCP GitHub no disponible")
        mcp_server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mcp_server)
        mcp_server.READONLY_MODE = False
        mcp_server.ALLOW_MUTATING = True
        result = mcp_server._github_create_repository({
            "name": body.get("name"),
            "private": body.get("private", True),
            "description": body.get("description", ""),
            "confirm": body.get("confirm") is True,
        })
        text = str(result.get("content", [{}])[0].get("text", "{}"))
        _send(handler, 200, json.loads(text))
    except Exception as exc:
        _send(handler, 400, {"ok": False, "error": str(exc)})


# ─── GitHub Auth State ──────────────────────────────────────────────────

# Fields that are NEVER exposed
_FORBIDDEN_FIELDS = frozenset([
    "token", "pat", "secret", "accessToken", "oauthToken",
    "refresh_token", "credential", "auth_method",
])


def _scrub_payload(payload: dict) -> dict:
    """Remove any forbidden fields from a dict before sending to client."""
    return {k: v for k, v in payload.items() if k not in _FORBIDDEN_FIELDS}


def _credential_storage() -> str:
    """Determine credential storage type from gh config."""
    code, output, _ = _run_gh(["auth", "status", "--format", "json"])
    if code != 0:
        return "unknown"
    try:
        data = json.loads(output)
        accounts = data.get("accounts", [])
        if not accounts:
            return "unknown"
        # Check if token is stored in keychain (secure) or plaintext
        for account in accounts:
            if account.get("user", {}).get("type") == "oauth" or account.get("auth_method") == "oauth":
                return "unknown"  # OAuth, uncertain storage
            if account.get("active"):
                # Try to detect storage type
                code2, out2, _ = _run_gh(["auth", "token", "--format", "json"])
                if code2 == 0:
                    return "secure"  # gh can read token from keychain
                return "plaintext"
        return "unknown"
    except Exception:
        return "unknown"


def _extract_auth_info(code: int, output: str, error: str) -> dict:
    """Extract auth info from gh auth status, never exposing tokens."""
    if code == 127:
        return {
            "installed": False,
            "authenticated": False,
            "credentialStorage": "unknown",
            "error": error or "gh no está instalado",
            "checkedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }

    authenticated = code == 0

    if not authenticated:
        return {
            "installed": True,
            "authenticated": False,
            "credentialStorage": "unknown",
            "error": error or None,
            "checkedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }

    # Authenticated — extract safe fields
    hostname: str | None = None
    username: str | None = None
    active_account: str | None = None
    scopes: list[str] = []

    try:
        status_data = json.loads(output) if output else {}
        accounts = status_data.get("accounts", [])
        if accounts:
            active = next((a for a in accounts if a.get("active", False)), accounts[0])
            username = active.get("user", {}).get("login")
            active_account = active.get("name") or active.get("user", {}).get("name") or username
            hostname = active.get("name")  # may be None for github.com
            # Extract scopes
            token_info = active.get("token", {})
            if isinstance(token_info, dict):
                scopes = token_info.get("scopes", [])
    except Exception:
        pass

    return {
        "installed": True,
        "authenticated": True,
        "hostname": hostname,
        "username": username,
        "activeAccount": active_account,
        "scopes": scopes,
        "credentialStorage": _credential_storage(),
        "error": None,
        "checkedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


# ─── GET /github/status ─────────────────────────────────────────────────


def handle_github_status(handler: "BaseHTTPRequestHandler") -> None:
    """Return GitHub auth state — no secrets exposed."""
    code, output, error = _run_gh(["auth", "status", "--format", "json"])
    info = _extract_auth_info(code, output, error)
    _send(handler, 200, {"ok": True, **_scrub_payload(info)})


# ─── POST /github/auth/start ───────────────────────────────────────────


def handle_github_auth_start(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Start GitHub auth flow. Backend decides the strategy."""
    code, output, error = _run_gh(["auth", "status"])
    if code == 0:
        _send(handler, 200, {
            "ok": True,
            "message": "Ya autenticado",
            "authenticated": True,
        })
        return

    # Try device flow
    code, _, error = _run_gh(["auth", "login", "--device", "--scopes", "repo:iac workflow"], timeout=120)
    if code == 0:
        handle_github_status(handler)
        return

    _send(handler, 200, {
        "ok": True,
        "message": "Flujo de autenticación iniciado — completa en el navegador o CLI",
        "authenticated": False,
        "error": error or None,
    })


# ─── POST /github/auth/refresh ─────────────────────────────────────────


def handle_github_auth_refresh(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Refresh GitHub auth by re-checking status."""
    handle_github_status(handler)


# ─── POST /github/auth/logout ─────────────────────────────────────────


def handle_github_auth_logout(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Logout from GitHub."""
    code, _, error = _run_gh(["auth", "logout", "--hostname", body.get("hostname", "github.com") or "github.com", "-y"])
    if code == 0:
        handle_github_status(handler)
    else:
        _send(handler, 200, {
            "ok": True,
            "authenticated": False,
            "error": error or "No se pudo cerrar sesión",
        })


# ─── POST /github/setup-git ────────────────────────────────────────────


def handle_github_setup_git(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Configure git with GitHub credentials."""
    email = str(body.get("email") or "").strip()
    username = str(body.get("username") or "").strip()

    if not email or not username:
        _send(handler, 400, {"ok": False, "error": "email y username son obligatorios"})
        return

    errors: list[str] = []

    code1, _, err1 = _run_gh(["config", "git", "--email", email])
    if code1 != 0:
        errors.append(f"git config email: {err1}")

    code2, _, err2 = _run_gh(["config", "git", "--name", username])
    if code2 != 0:
        errors.append(f"git config name: {err2}")

    if errors:
        _send(handler, 200, {
            "ok": True,
            "configured": False,
            "errors": errors,
        })
    else:
        _send(handler, 200, {
            "ok": True,
            "configured": True,
            "message": f"Git configurado para {username}",
        })


# ─── GET /github/accounts ──────────────────────────────────────────────


def handle_github_accounts(handler: "BaseHTTPRequestHandler") -> None:
    """List all configured GitHub accounts."""
    code, output, error = _run_gh(["auth", "status", "--format", "json"])
    if code != 0:
        _send(handler, 200, {"ok": True, "accounts": [], "count": 0, "error": error or None})
        return

    try:
        data = json.loads(output)
        accounts = data.get("accounts", [])
        safe_accounts = []
        for acct in accounts:
            safe_accounts.append({
                "username": acct.get("user", {}).get("login"),
                "name": acct.get("name") or acct.get("user", {}).get("name"),
                "active": acct.get("active", False),
                "hostname": acct.get("name"),
            })
        _send(handler, 200, {
            "ok": True,
            "accounts": safe_accounts,
            "count": len(safe_accounts),
        })
    except Exception as exc:
        _send(handler, 200, {"ok": True, "accounts": [], "count": 0, "error": str(exc)})

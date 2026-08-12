"""GitHub capabilities exposed to the UI through the authenticated gh CLI."""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

_REPO_FILE = ".bago_github_repo.json"
_REPO_RE = re.compile(r"^(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _state(handler) -> Path:
    from api_state import resolve_state_root
    return Path(resolve_state_root(handler))


def _non_interactive_env() -> dict:
    env = dict(os.environ)
    env["GH_PROMPT_DISABLED"] = "1"
    return env


def _run_gh(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=_non_interactive_env(),
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "gh no está instalado"
    except subprocess.TimeoutExpired:
        return 124, "", "GitHub tardó demasiado en responder"


def _run_git(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "git no está instalado"
    except subprocess.TimeoutExpired:
        return 124, "", "git tardó demasiado en responder"


def _launch_gh_detached(args: list[str]) -> None:
    """Launch gh in the background so the UI can poll status while the user auths."""
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(["gh", *args], **kwargs)


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


def handle_auth_start(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Initiate GitHub authentication via gh CLI — returns auth URL for manual flow."""
    _send(handler, 200, {
        "ok": True,
        "auth_url": "https://github.com/login/device/code",
        "instructions": "Ejecuta `gh auth login` en tu terminal o visita la URL proporcionada por `gh auth login`.",
    })


def handle_auth_refresh(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Refresh gh auth token by re-checking auth status."""
    code, output, error = _run_gh(["auth", "status"])
    _send(handler, 200, {
        "ok": True,
        "authenticated": code == 0,
        "output": output,
        "error": error or None,
    })


def handle_auth_logout(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Logout from gh CLI."""
    code, _, error = _run_gh(["auth", "logout", "--hostname", "github.com"])
    if code == 0:
        _send(handler, 200, {"ok": True, "message": "Sesión de GitHub cerrada"})
    else:
        _send(handler, 400, {"ok": False, "error": error or "No se pudo cerrar sesión"})


def handle_setup(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Configure gh with a token directly (token never stored by BAGO)."""
    token = str(body.get("token") or "").strip()
    hostname = str(body.get("hostname") or "github.com").strip()
    if not token:
        _send(handler, 400, {"ok": False, "error": "'token' es obligatorio"})
        return
    code, _, error = _run_gh(["auth", "login", "--hostname", hostname, "--token", token])
    if code == 0:
        _send(handler, 200, {"ok": True, "authenticated": True, "hostname": hostname})
    else:
        _send(handler, 400, {"ok": False, "error": error or "Falló la autenticación con gh"})


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


def handle_github_status(handler: "BaseHTTPRequestHandler") -> None:
    """Return GitHub auth state — no secrets exposed.

    Keeps the previous /github/status contract (repo/repository fields) while
    reporting the richer auth-panel state derived from the hosts payload.
    """
    code, output, error = _run_gh(["auth", "status", "--json", "hosts"])
    info = _extract_auth_info(code, output, error)
    repo = _saved_repo(_state(handler))
    repository = None
    if repo and info.get("authenticated"):
        rcode, raw, _ = _run_gh(["api", f"repos/{repo}"])
        if rcode == 0:
            try:
                repository = json.loads(raw)
            except json.JSONDecodeError:
                repository = None
    _send(handler, 200, {"ok": True, **_scrub_payload(info), "repo": repo, "repository": repository})


# ─── POST /github/auth/start ───────────────────────────────────────────


def handle_github_auth_start(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Start GitHub auth flow. Backend decides the strategy."""
    code, output, _ = _run_gh(["auth", "status", "--json", "hosts"])
    if code == 127:
        _send(handler, 200, {
            "ok": True,
            "authenticated": False,
            "installed": False,
            "pending": False,
            "error": "gh no está instalado",
        })
        return

    info = _extract_auth_info(code, output, "")
    if info.get("authenticated"):
        _send(handler, 200, {
            "ok": True,
            "message": "Ya autenticado",
            "authenticated": True,
        })
        return

    hostname = str(body.get("hostname") or "github.com").strip() or "github.com"
    if not _HOSTNAME_RE.match(hostname):
        _send(handler, 400, {"ok": False, "error": "hostname no válido"})
        return

    # Web-based device flow launched in the background: gh opens the browser and
    # copies the one-time code to the clipboard, while the UI polls for status.
    try:
        _launch_gh_detached([
            "auth", "login",
            "--hostname", hostname,
            "--web",
            "--clipboard",
            "--git-protocol", "https",
            "--skip-ssh-key",
            "--scopes", "repo,workflow",
        ])
    except FileNotFoundError:
        _send(handler, 200, {
            "ok": True,
            "authenticated": False,
            "installed": False,
            "pending": False,
            "error": "gh no está instalado",
        })
        return
    except OSError as exc:
        _send(handler, 200, {
            "ok": True,
            "authenticated": False,
            "pending": False,
            "error": f"No se pudo iniciar el flujo de autenticación: {exc}",
        })
        return

    _send(handler, 200, {
        "ok": True,
        "message": "Se abrió el navegador: autoriza el dispositivo con el código del portapapeles y pulsa Refrescar",
        "authenticated": False,
        "hostname": hostname,
        "pending": True,
        "error": None,
    })


# ─── POST /github/auth/refresh ─────────────────────────────────────────


def handle_github_auth_refresh(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Refresh GitHub auth by re-checking status."""
    handle_github_status(handler)


# ─── POST /github/auth/logout ─────────────────────────────────────────


def handle_github_auth_logout(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """Logout from GitHub non-interactively (no -y flag in supported gh versions)."""
    hostname = str(body.get("hostname") or "github.com").strip() or "github.com"
    if not _HOSTNAME_RE.match(hostname):
        _send(handler, 400, {"ok": False, "error": "hostname no válido"})
        return

    args = ["auth", "logout", "--hostname", hostname]

    # gh requires an explicit --user in non-interactive mode; resolve the active
    # account for the host from the status payload when the body omits it.
    user = str(body.get("user") or "").strip()
    if not user:
        code, output, _ = _run_gh(["auth", "status", "--json", "hosts"])
        if code == 0:
            accounts = _parse_status_hosts(output).get(hostname, [])
            active = next((a for a in accounts if a.get("active")), accounts[0] if accounts else None)
            if active:
                user = str(active.get("login") or "").strip()
    if user:
        args.extend(["--user", user])

    code, _, error = _run_gh(args)
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
    """Configure git identity for the workspace (git config, not gh config)."""
    email = str(body.get("email") or "").strip()
    username = str(body.get("username") or "").strip()

    if not email or not username:
        _send(handler, 400, {"ok": False, "error": "email y username son obligatorios"})
        return
    if email.startswith("-") or username.startswith("-") or len(email) > 254 or len(username) > 254:
        _send(handler, 400, {"ok": False, "error": "email o username no válidos"})
        return

    errors: list[str] = []

    code1, _, err1 = _run_git(["config", "user.email", email])
    if code1 != 0:
        errors.append(f"git config email: {err1}")

    code2, _, err2 = _run_git(["config", "user.name", username])
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
    code, output, error = _run_gh(["auth", "status", "--json", "hosts"])
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

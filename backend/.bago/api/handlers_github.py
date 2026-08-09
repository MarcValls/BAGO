"""GitHub capabilities exposed to the UI through the authenticated gh CLI."""
from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

_REPO_FILE = ".bago_github_repo.json"
_REPO_RE = re.compile(r"^(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def _state(handler) -> Path:
    from api_state import resolve_state_root
    return Path(resolve_state_root(handler))


def _run_gh(args: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=30)
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
    url = next((line.strip() for line in raw.splitlines() if "github.com/" in line), raw.splitlines()[-1].strip() if raw else "")
    _send(handler, 200, {"ok": True, "url": url, "output": raw})

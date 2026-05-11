from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICE_ENTRYPOINT_RE = re.compile(r"\b(?:HTTPServer|socketserver\.TCPServer)\(")
WILDCARD_CORS_RE = re.compile(
    r'send_header\(\s*["\']Access-Control-Allow-Origin["\']\s*,\s*["\']\*["\']\s*\)'
)
ALL_INTERFACES_BIND_MARKERS = (
    'HTTPServer(("0.0.0.0",',
    "HTTPServer(('0.0.0.0',",
    'socketserver.TCPServer(("0.0.0.0",',
    "socketserver.TCPServer(('0.0.0.0',",
)

SERVICE_POLICY = {
    ".bago/tools/bago_miniapp_server.py": {
        "command": "`python3 .bago/tools/bago_miniapp_server.py`",
        "bind_markers": (
            'SERVER_HOST  = os.environ.get("BAGO_MINIAPP_HOST", "127.0.0.1")',
            'parser.add_argument("--host", default="127.0.0.1")',
        ),
        "doc_tokens": (
            "`python3 .bago/tools/bago_miniapp_server.py`",
            "`.bago/tools/bago_miniapp_server.py`",
            "`127.0.0.1`",
        ),
        "mutating": True,
        "cors_markers": (
            'self.send_header("Access-Control-Allow-Origin", self._cors_origin())',
            'def _cors_origin(self) -> str:',
        ),
        "auth_markers": (
            "def _auth_ok(self) -> bool:",
            "def _requires_auth(self, path: str) -> bool:",
        ),
    },
    ".bago/tools/peer_link.py": {
        "command": "`bago peer serve`",
        "bind_markers": (
            'def cmd_serve(http_port: int = HTTP_PORT, host: str = "127.0.0.1"):',
            'p_serve.add_argument("--host", default="127.0.0.1")',
        ),
        "doc_tokens": (
            "`bago peer serve`",
            "`.bago/tools/peer_link.py`",
            "Opt-in LAN via `--host`",
        ),
        "mutating": True,
        "cors_markers": (
            'self.send_header("Access-Control-Allow-Origin", allowed_origin)',
            'allowed_origin = f"http://{host}:{http_port}"',
        ),
        "lan_override_markers": (
            'if host != "127.0.0.1":',
            "Modo LAN expuesto",
        ),
    },
    ".bago/tools/live_dashboard.py": {
        "command": "`python3 .bago/tools/live_dashboard.py`",
        "bind_markers": ('server = HTTPServer(("localhost", port), handler)',),
        "doc_tokens": (
            "`python3 .bago/tools/live_dashboard.py`",
            "`.bago/tools/live_dashboard.py`",
            "`localhost`",
        ),
        "mutating": False,
    },
    ".bago/tools/bago_telemetry_web.py": {
        "command": "`bago telemetry --web`",
        "bind_markers": ('server = HTTPServer(("127.0.0.1", port), _Handler)',),
        "doc_tokens": (
            "`bago telemetry --web`",
            "`.bago/tools/bago_telemetry_web.py`",
            "`127.0.0.1`",
        ),
        "mutating": False,
    },
    ".bago/tools/http_discover.py": {
        "command": "`http-discover`",
        "bind_markers": ("server = socketserver.TCPServer(('0.0.0.0', 8080), BAGOHandler)",),
        "doc_tokens": (
            "`http-discover`",
            "`.bago/tools/http_discover.py`",
            "Legacy experimental LAN exception",
        ),
        "mutating": False,
        "lan_default_exception": True,
        "lan_exception_markers": (
            "Experimental",
            "redes de confianza",
        ),
    },
}


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _service_entrypoints() -> set[str]:
    found = set()
    for path in (REPO_ROOT / ".bago" / "tools").glob("*.py"):
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        if SERVICE_ENTRYPOINT_RE.search(path.read_text(encoding="utf-8")):
            found.add(rel_path)
    return found


def test_service_inventory_matches_http_entrypoints():
    assert _service_entrypoints() == set(SERVICE_POLICY)


def test_security_md_documents_enforced_local_service_inventory():
    security_md = _read("SECURITY.md")
    assert "## CI-enforced local service guarantees" in security_md
    for service in SERVICE_POLICY.values():
        for token in service["doc_tokens"]:
            assert token in security_md


def test_default_host_binding_is_localhost_unless_documented_exception():
    for rel_path, service in SERVICE_POLICY.items():
        content = _read(rel_path)
        for marker in service["bind_markers"]:
            assert marker in content
        if service.get("lan_default_exception"):
            continue
        else:
            for marker in ALL_INTERFACES_BIND_MARKERS:
                assert marker not in content


def test_opt_in_lan_services_have_explicit_code_markers():
    peer_content = _read(".bago/tools/peer_link.py")
    for marker in SERVICE_POLICY[".bago/tools/peer_link.py"]["lan_override_markers"]:
        assert marker in peer_content

    http_discover = _read(".bago/tools/http_discover.py")
    for marker in SERVICE_POLICY[".bago/tools/http_discover.py"]["lan_exception_markers"]:
        assert marker in http_discover


def test_mutating_http_handlers_do_not_use_wildcard_cors_without_guard():
    for rel_path, service in SERVICE_POLICY.items():
        if not service["mutating"]:
            continue
        content = _read(rel_path)
        assert not WILDCARD_CORS_RE.search(content), (
            f"{rel_path}: uses wildcard CORS on a mutating handler"
        )
        for marker in service.get("cors_markers", ()):
            assert marker in content, (
                f"{rel_path}: missing CORS marker: {marker!r}"
            )
        for marker in service.get("auth_markers", ()):
            assert marker in content, (
                f"{rel_path}: missing auth marker: {marker!r}"
            )


def test_miniapp_requires_token_when_exposed_beyond_localhost():
    content = _read(".bago/tools/bago_miniapp_server.py")
    assert '_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}' in content
    assert "SERVER_HOST not in _LOCAL_HOSTS and not AUTH_TOKEN" in content

def test_peer_has_no_wildcard_cors_origin():
    content = _read(".bago/tools/peer_link.py")
    assert 'Access-Control-Allow-Origin", "*"' not in content


def test_security_policy_documents_local_service_promises():
    content = _read("SECURITY.md")
    assert "127.0.0.1" in content
    assert "restricted CORS" in content
    assert "token auth on mutating endpoints" in content


def test_miniapp_mutating_endpoints_support_token_auth():
    content = _read(".bago/tools/bago_miniapp_server.py")
    assert 'self.headers.get("Authorization")' in content
    assert "def _requires_auth" in content
    assert 'parser.add_argument("--token"' in content

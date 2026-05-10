from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_miniapp_httpserver_not_bound_to_all_interfaces_literal():
    content = _read(".bago/tools/bago_miniapp_server.py")
    assert 'HTTPServer(("0.0.0.0",' not in content


def test_peer_httpserver_not_bound_to_all_interfaces_literal():
    content = _read(".bago/tools/peer_link.py")
    assert 'HTTPServer(("0.0.0.0",' not in content


def test_miniapp_has_no_wildcard_cors_origin():
    content = _read(".bago/tools/bago_miniapp_server.py")
    assert 'Access-Control-Allow-Origin", "*"' not in content


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

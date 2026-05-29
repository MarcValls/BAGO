"""Contratos para el login de Codex/OpenAI."""

from __future__ import annotations

from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))


def test_openai_login_uses_resolved_codex_cli():
    path = TOOLS / "bago" / "credentials" / "flows" / "openai.py"
    text = path.read_text(encoding="utf-8")

    assert "_resolve_codex_cli" in text
    assert "_run_codex_login" in text
    assert "where.exe" in text
    assert 'cmd", "/c", cli, "login"' in text


def test_login_flows_uses_resolved_codex_cli():
    path = TOOLS / "bago" / "credentials" / "login_flows.py"
    text = path.read_text(encoding="utf-8")

    assert "_resolve_codex_cli" in text
    assert "_run_codex_login" in text
    assert "where.exe" in text
    assert 'cmd", "/c", cli, "login"' in text

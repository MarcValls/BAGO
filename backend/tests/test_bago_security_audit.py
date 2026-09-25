from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import bago_security_audit


def test_security_audit_detects_tokens_and_respects_examples(tmp_path) -> None:
    token = "github_pat_" + "abcdefghijklmnopqrstuvwxyz_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
    (tmp_path / "token.txt").write_text(token + "\n", encoding="utf-8")
    (tmp_path / "example.txt").write_text("example github_pat_placeholder_token\n", encoding="utf-8")
    (tmp_path / "prompt.ps1").write_text(
        "$cfg.api_key = Read-InputOrDefault -Default $env:OPENAI_API_KEY\n",
        encoding="utf-8",
    )

    findings = bago_security_audit.scan_tokens(tmp_path)

    assert any(item["token_type"] == "github_pat" and item["file"] == "token.txt" for item in findings)
    assert not any(item["file"] in {"example.txt", "prompt.ps1"} for item in findings)


def test_env_ignore_remediation_score_and_permission_flags(tmp_path) -> None:
    (tmp_path / ".env").write_text("OPENAI_KEY=test\n", encoding="utf-8")
    assert any(item["kind"] == "env_gitignore" for item in bago_security_audit.scan_env_gitignore(tmp_path))

    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    assert not bago_security_audit.scan_env_gitignore(tmp_path)
    assert bago_security_audit._permission_flags(0o777) == ["executable", "world_writable"]
    assert bago_security_audit.compute_score([{"severity": "CRITICAL"}] * 10) == 0
    assert bago_security_audit.remediation_steps([{
        "kind": "token_exposed", "token_type": "github_pat", "file": "token.txt", "line": 1,
    }]) == ["Rotate github_pat secret found in token.txt line 1"]


def test_removed_selftest_switch_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc:
        bago_security_audit.main(["--test"])

    assert exc.value.code == 2

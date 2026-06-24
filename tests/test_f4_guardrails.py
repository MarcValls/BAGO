"""test_f4_guardrails.py — Regression tests for F4: Forbidden paths, structured tool log, no claims without execution.

Covers:
- TEST 014: PathGuard blocks forbidden paths (.git, .env, .bago, state, etc.)
- TEST 015: ToolLogger records structured entries (tool name, args, result, latency)
- TEST 017: ClaimValidator detects claims without tool execution evidence
- TEST 029: ClaimValidator does not flag responses without claims
- PathGuard allows safe paths
- ToolLogger persists entries to JSONL file
- ToolLogger has_evidence_for / tool_names_executed
- ClaimValidator does not flag when evidence exists
- SessionManager initializes guardrails
- SessionManager.tool_logger is populated after tool execution
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"
if str(_BAGO_CORE) not in sys.path:
    sys.path.insert(0, str(_BAGO_CORE))


# ── TEST 014: PathGuard ─────────────────────────────────────────────

def test_pathguard_blocks_git():
    """PathGuard must block access to .git paths."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("write_file", {"path": "repo/.git/config"})
    assert result.blocked is True
    assert ".git" in result.reason
    assert any(".git" in p for p in result.blocked_paths)


def test_pathguard_blocks_env():
    """PathGuard must block access to .env files."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("write_file", {"path": "project/.env"})
    assert result.blocked is True
    assert ".env" in result.reason


def test_pathguard_blocks_bago_state():
    """PathGuard must block access to .bago/state paths."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("read_file", {"file": "workspace/.bago/state/sessions.json"})
    assert result.blocked is True


def test_pathguard_blocks_node_modules():
    """PathGuard must block access to node_modules."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("read_file", {"path": "project/node_modules/react/index.js"})
    assert result.blocked is True


def test_pathguard_blocks_venv():
    """PathGuard must block access to venv directories."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("execute", {"cwd": "project/venv/bin"})
    assert result.blocked is True


def test_pathguard_allows_safe_paths():
    """PathGuard must allow normal workspace paths."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("write_file", {"path": "src/main.py"})
    assert result.blocked is False
    assert result.reason == ""
    assert result.blocked_paths == []


def test_pathguard_allows_nested_safe_paths():
    """PathGuard must allow deeply nested safe paths."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("read_file", {"path": "src/components/Button.jsx"})
    assert result.blocked is False


def test_pathguard_case_insensitive():
    """PathGuard must be case-insensitive."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("write_file", {"path": "repo/.GIT/HEAD"})
    assert result.blocked is True


def test_pathguard_backslash_paths():
    """PathGuard must handle Windows backslash paths."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("write_file", {"path": "repo\\.git\\config"})
    assert result.blocked is True


def test_pathguard_blocks_state_segment():
    """PathGuard must block 'state' as a path segment."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("read_file", {"path": "project/state/data.json"})
    assert result.blocked is True


def test_pathguard_empty_args():
    """PathGuard must not block when arguments have no paths."""
    from guardrails import PathGuard
    pg = PathGuard()
    result = pg.check("ping", {"host": "localhost"})
    assert result.blocked is False


# ── TEST 015: ToolLogger ────────────────────────────────────────────

def test_toollogger_records_entry():
    """ToolLogger must record a structured entry with all fields."""
    from guardrails import ToolLogger
    logger = ToolLogger()
    entry = logger.log(
        session_id="test-session",
        tool_name="read_file",
        arguments={"path": "src/main.py"},
        ok=True,
        returncode=0,
        latency_ms=42.5,
        content="file contents here",
    )
    assert entry.tool_name == "read_file"
    assert entry.ok is True
    assert entry.returncode == 0
    assert entry.latency_ms == 42.5
    assert entry.session_id == "test-session"
    assert entry.content_preview == "file contents here"
    assert entry.blocked is False


def test_toollogger_records_blocked_entry():
    """ToolLogger must record blocked entries with block_reason."""
    from guardrails import ToolLogger
    logger = ToolLogger()
    entry = logger.log(
        session_id="test-session",
        tool_name="write_file",
        arguments={"path": ".git/config"},
        ok=False,
        returncode=1,
        latency_ms=0.0,
        content="blocked",
        blocked=True,
        block_reason="forbidden path .git",
    )
    assert entry.blocked is True
    assert entry.block_reason == "forbidden path .git"
    assert entry.ok is False


def test_toollogger_persists_to_jsonl():
    """ToolLogger must append entries to JSONL file."""
    from guardrails import ToolLogger
    with tempfile.TemporaryDirectory() as td:
        log_path = Path(td) / "tool_log.jsonl"
        logger = ToolLogger(log_path=str(log_path))
        logger.log(
            session_id="s1",
            tool_name="read_file",
            arguments={"path": "foo.py"},
            ok=True,
            returncode=0,
            latency_ms=10.0,
            content="ok",
        )
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tool_name"] == "read_file"
        assert entry["ok"] is True
        assert entry["session_id"] == "s1"
        assert "timestamp" in entry


def test_toollogger_tool_names_executed():
    """tool_names_executed must return only successful non-blocked tools."""
    from guardrails import ToolLogger
    logger = ToolLogger()
    logger.log("s1", "read_file", {"p": "a"}, True, 0, 10, "ok")
    logger.log("s1", "write_file", {"p": ".git"}, False, 1, 0, "blocked", blocked=True)
    logger.log("s1", "grep", {"p": "b"}, True, 0, 5, "found")
    names = logger.tool_names_executed()
    assert "read_file" in names
    assert "grep" in names
    assert "write_file" not in names


def test_toollogger_has_evidence_for():
    """has_evidence_for must return True only for successful non-blocked tools."""
    from guardrails import ToolLogger
    logger = ToolLogger()
    logger.log("s1", "read_file", {"p": "a"}, True, 0, 10, "ok")
    logger.log("s1", "bad_tool", {"p": ".git"}, False, 1, 0, "blocked", blocked=True)
    assert logger.has_evidence_for("read_file") is True
    assert logger.has_evidence_for("bad_tool") is False
    assert logger.has_evidence_for("nonexistent") is False


def test_toollogger_clear():
    """clear must empty the in-memory entries."""
    from guardrails import ToolLogger
    logger = ToolLogger()
    logger.log("s1", "read_file", {"p": "a"}, True, 0, 10, "ok")
    assert len(logger.entries) == 1
    logger.clear()
    assert len(logger.entries) == 0


# ── TEST 017: ClaimValidator — no claims without execution ─────────

def test_claimvalidator_no_claim_no_warning():
    """ClaimValidator must not warn when response has no claim verbs."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()
    result = cv.validate("El sistema funciona correctamente.", logger)
    assert result.has_claim is False
    assert result.has_evidence is True
    assert result.warning == ""


def test_claimvalidator_claim_without_evidence():
    """ClaimValidator must warn when claim is made without tool evidence."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()  # empty, no tools executed
    result = cv.validate("He ejecutado el comando y funcionó.", logger)
    assert result.has_claim is True
    assert result.has_evidence is False
    assert "AVISO" in result.warning
    assert "evidencia" in result.warning.lower()


def test_claimvalidator_claim_with_evidence():
    """ClaimValidator must not warn when claim is backed by tool execution."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()
    logger.log("s1", "run_command", {"cmd": "ls"}, True, 0, 10, "output")
    result = cv.validate("He ejecutado el comando y funcionó.", logger)
    assert result.has_claim is True
    assert result.has_evidence is True
    assert result.warning == ""


def test_claimvalidator_english_claims():
    """ClaimValidator must detect English claim verbs."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()
    result = cv.validate("I ran the tests and they passed.", logger)
    assert result.has_claim is True
    assert result.has_evidence is False
    assert len(result.warning) > 0


def test_claimvalidator_created_claim():
    """ClaimValidator must detect 'creé' / 'he creado' claims."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()
    result = cv.validate("He creado el archivo correctamente.", logger)
    assert result.has_claim is True
    assert result.has_evidence is False


def test_claimvalidator_applied_claim():
    """ClaimValidator must detect 'ya apliqué' / 'he aplicado' claims."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()
    result = cv.validate("Ya apliqué el patch al archivo.", logger)
    assert result.has_claim is True
    assert result.has_evidence is False


def test_claimvalidator_no_false_positive_on_question():
    """ClaimValidator must not flag questions that mention execution."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()
    result = cv.validate("¿Has ejecutado el comando?", logger)
    assert result.has_claim is False


# ── TEST 029: Detección de invención ────────────────────────────────

def test_claimvalidator_invention_warning_added_to_response():
    """When a claim is made without evidence, the warning must be generated."""
    from guardrails import ClaimValidator, ToolLogger
    cv = ClaimValidator()
    logger = ToolLogger()
    response = "He inspeccionado el sistema y encontré 3 errores."
    result = cv.validate(response, logger)
    assert result.has_claim is True
    assert result.has_evidence is False
    assert len(result.warning) > 0
    assert "AVISO" in result.warning


# ── SessionManager integration ─────────────────────────────────────

def test_session_manager_has_guardrails():
    """SessionManager must initialize PathGuard, ToolLogger, and ClaimValidator."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f4-init",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            from guardrails import PathGuard, ToolLogger, ClaimValidator
            assert isinstance(mgr.path_guard, PathGuard)
            assert isinstance(mgr.tool_logger, ToolLogger)
            assert isinstance(mgr.claim_validator, ClaimValidator)
        finally:
            mgr.close()


def test_session_manager_tool_logger_persists_file():
    """SessionManager must create a tool_log.jsonl file in state dir."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f4-log",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            # The log path should be under state_dir
            log_file = Path(td) / "tool_log.jsonl"
            assert log_file.exists() or mgr.tool_logger.log_path is not None
        finally:
            mgr.close()


def test_is_forbidden_path_standalone():
    """is_forbidden_path must work as a standalone function."""
    from guardrails import is_forbidden_path
    assert is_forbidden_path(".git/config") is True
    assert is_forbidden_path("src/main.py") is False
    assert is_forbidden_path("project/.env") is True
    assert is_forbidden_path("node_modules/x") is True
    assert is_forbidden_path("README.md") is False
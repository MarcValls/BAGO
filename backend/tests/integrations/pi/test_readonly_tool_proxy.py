"""Fase 2 — tests del readonly_tool_proxy."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from integrations.pi.contracts import (
    CapabilityClaims,
    ToolReceipt,
    _now_iso,
)
from integrations.pi.errors import (
    BridgeError,
    CapabilityDenied,
    OutputLimitExceeded,
    ScopeLinkEscapeDenied,
    ScopePathDenied,
    ScopeReadDenied,
    ScopeToctouDetected,
    ToolNotAllowed,
)
from integrations.pi.readonly_tool_proxy import (
    MAX_LS_ENTRIES,
    MAX_READ_BYTES,
    PROXY_VERSION,
    ToolDecision,
    build_tool_receipt,
    invoke_tool,
)


def _claims(**overrides) -> CapabilityClaims:
    base = dict(
        filesystem_read=True,
        filesystem_read_root="/nonexistent",
        filesystem_write=False,
        process_spawn=False,
        network_mode="provider_endpoints_only",
        tools_allowed=("read", "ls", "grep", "find"),
        skills_imported_ids=(),
        extensions_allowed=(),
        packages_allowed=(),
    )
    base.update(overrides)
    return CapabilityClaims(**base)


# ── read ──────────────────────────────────────────────────────────────────


def test_read_returns_file_content(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hello world\nline 2\n", encoding="utf-8")
    decision = invoke_tool(
        tool="read",
        arguments={"path": str(f)},
        scope_root=str(tmp_path),
        execution_id="exec-1",
        tool_call_id="tc-1",
        claims=_claims(filesystem_read_root=str(tmp_path)),
    )
    assert decision.allowed
    assert "hello world" in decision.result.output
    assert decision.result.size_bytes > 0


def test_read_rejects_path_outside_scope(tmp_path: Path) -> None:
    other = tmp_path.parent / "evil.txt"
    other.write_text("evil", encoding="utf-8")
    with pytest.raises((ScopePathDenied, ScopeLinkEscapeDenied)):
        invoke_tool(
            tool="read",
            arguments={"path": str(other)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )


def test_read_rejects_missing_path_argument(tmp_path: Path) -> None:
    with pytest.raises(ScopeReadDenied):
        invoke_tool(
            tool="read",
            arguments={},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )


def test_read_truncates_huge_file(tmp_path: Path) -> None:
    f = tmp_path / "big.bin"
    f.write_bytes(b"a" * (MAX_READ_BYTES + 1000))
    decision = invoke_tool(
        tool="read",
        arguments={"path": str(f)},
        scope_root=str(tmp_path),
        execution_id="exec-1",
        tool_call_id="tc-1",
        claims=_claims(filesystem_read_root=str(tmp_path)),
    )
    assert decision.allowed
    assert decision.result.truncated is True
    assert decision.result.size_bytes == MAX_READ_BYTES


def test_read_detects_toctou(tmp_path: Path) -> None:
    """El bridge detecta TOCTOU vía re-stat tras la lectura.

    El flujo completo de `read` no es fácil de monkey-patchear sin
    afectar el resto. Aquí verificamos que el helper `verify_toctou`
    (usado por el proxy) detecta el cambio de identidad.
    """
    from integrations.pi.scope_validator import resolve_path, verify_toctou
    from integrations.pi.errors import ScopeToctouDetected

    f = tmp_path / "x.txt"
    f.write_text("first", encoding="utf-8")
    resolved = resolve_path(str(f), str(tmp_path))
    stat_before = os.stat(resolved.canonical)
    f.unlink()
    f.write_text("second", encoding="utf-8")
    with pytest.raises(ScopeToctouDetected):
        verify_toctou(resolved, stat_before)


# ── ls ────────────────────────────────────────────────────────────────────


def test_ls_returns_entries(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    decision = invoke_tool(
        tool="ls",
        arguments={"path": str(tmp_path)},
        scope_root=str(tmp_path),
        execution_id="exec-1",
        tool_call_id="tc-1",
        claims=_claims(filesystem_read_root=str(tmp_path)),
    )
    assert decision.allowed
    names = {e["name"] for e in decision.result.output}
    assert "a.txt" in names
    assert "b.txt" in names


def test_ls_rejects_when_target_is_a_file(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ScopeReadDenied):
        invoke_tool(
            tool="ls",
            arguments={"path": str(f)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )


# ── grep ──────────────────────────────────────────────────────────────────


def test_grep_finds_pattern_in_file(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    decision = invoke_tool(
        tool="grep",
        arguments={"path": str(f), "pattern": "beta"},
        scope_root=str(tmp_path),
        execution_id="exec-1",
        tool_call_id="tc-1",
        claims=_claims(filesystem_read_root=str(tmp_path)),
    )
    assert decision.allowed
    assert len(decision.result.output) == 1
    assert "beta" in decision.result.output[0]["content"]


def test_grep_requires_pattern(tmp_path: Path) -> None:
    with pytest.raises(CapabilityDenied):
        invoke_tool(
            tool="grep",
            arguments={"path": str(tmp_path)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )


def test_grep_rejects_invalid_regex(tmp_path: Path) -> None:
    with pytest.raises(CapabilityDenied):
        invoke_tool(
            tool="grep",
            arguments={"path": str(tmp_path), "pattern": "["},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )


# ── find ──────────────────────────────────────────────────────────────────


def test_find_returns_matching_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.log").write_text("b", encoding="utf-8")
    decision = invoke_tool(
        tool="find",
        arguments={"path": str(tmp_path), "name": ".txt"},
        scope_root=str(tmp_path),
        execution_id="exec-1",
        tool_call_id="tc-1",
        claims=_claims(filesystem_read_root=str(tmp_path)),
    )
    assert decision.allowed
    paths = {e["path"] for e in decision.result.output}
    assert any("a.txt" in p for p in paths)
    assert not any("b.log" in p for p in paths)


def test_find_rejects_excessive_depth(tmp_path: Path) -> None:
    with pytest.raises(CapabilityDenied):
        invoke_tool(
            tool="find",
            arguments={"path": str(tmp_path), "max_depth": 999},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )


# ── Tools no permitidas ───────────────────────────────────────────────────


def test_unknown_tool_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolNotAllowed):
        invoke_tool(
            tool="bash",
            arguments={"command": "rm -rf /"},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )


def test_tool_not_in_claims_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolNotAllowed):
        invoke_tool(
            tool="read",
            arguments={"path": str(tmp_path)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(tools_allowed=("ls",)),
        )


def test_filesystem_read_disabled_rejects_tools(tmp_path: Path) -> None:
    with pytest.raises(ToolNotAllowed):
        invoke_tool(
            tool="read",
            arguments={"path": str(tmp_path)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read=False),
        )


# ── ToolReceipt ──────────────────────────────────────────────────────────


def test_build_receipt_for_successful_read(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    decision = invoke_tool(
        tool="read",
        arguments={"path": str(f)},
        scope_root=str(tmp_path),
        execution_id="exec-1",
        tool_call_id="tc-1",
        claims=_claims(filesystem_read_root=str(tmp_path)),
    )
    receipt = build_tool_receipt(
        tool_call_id="tc-1",
        execution_id="exec-1",
        tool="read",
        arguments={"path": str(f)},
        requested_path=str(f),
        scope_root=str(tmp_path),
        decision=decision,
    )
    # Estructural: la clase es la misma definida en tool_receipt.py
    # canónico. La comparación de tipo puede fallar por re-imports
    # de pytest, así que verificamos los campos.
    assert receipt.__class__.__name__ == "ToolReceipt"
    assert hasattr(receipt, "proxy_version")
    assert receipt.proxy_version == PROXY_VERSION
    assert receipt.status == "completed"
    assert receipt.policy_decision == "allow"
    assert receipt.policy_rule_code == "PI_TOOL_OK"
    assert receipt.result_size_bytes == 5
    assert receipt.result_hash != "0" * 16
    assert receipt.tool_call_id == "tc-1"


def test_build_receipt_for_denied_tool() -> None:
    receipt = build_tool_receipt(
        tool_call_id="tc-1",
        execution_id="exec-1",
        tool="bash",
        arguments={"command": "evil"},
        requested_path="",
        scope_root="/tmp",
        decision=ToolDecision(
            allowed=False, tool="bash", rule_code="TOOL_NOT_ALLOWED"
        ),
    )
    assert receipt.status == "denied"
    assert receipt.policy_decision == "deny"
    assert receipt.policy_rule_code == "TOOL_NOT_ALLOWED"
    assert receipt.result_size_bytes == 0
    assert receipt.result_hash == "0" * 16


# ── Cobertura de path con alias `file` y `target` ─────────────────────────


def test_read_accepts_file_alias(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi", encoding="utf-8")
    decision = invoke_tool(
        tool="read",
        arguments={"file": str(f)},
        scope_root=str(tmp_path),
        execution_id="exec-1",
        tool_call_id="tc-1",
        claims=_claims(filesystem_read_root=str(tmp_path)),
    )
    assert decision.allowed


def test_read_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(str(outside), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises((ScopeLinkEscapeDenied, ScopePathDenied)):
        invoke_tool(
            tool="read",
            arguments={"path": str(link)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims(filesystem_read_root=str(tmp_path)),
        )

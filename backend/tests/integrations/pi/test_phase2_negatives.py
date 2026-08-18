"""Fase 2 — pruebas negativas adicionales para tools.

Cubre los escenarios del PLAN §8 atribuibles a Fase 2:
    - NEG-008  tool result sin ToolReceipt → MISSING_TOOL_RECEIPT
    - NEG-011  symlink/junction hacia fuera de scope
    - NEG-012  rutas absolutas, UNC, drive alternativo
    - NEG-022  tool no registrada cancela
    - NEG-021  TOCTOU
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from integrations.pi.contracts import (
    BridgeExecutionRequest,
    CapabilityClaims,
    _now_iso,
    make_event,
)
from integrations.pi.errors import (
    BridgeError,
    MissingToolReceipt,
    ScopeLinkEscapeDenied,
    ScopePathDenied,
    ToolNotAllowed,
)
from integrations.pi.event_capture import EventLog
from integrations.pi.readonly_tool_proxy import (
    ToolDecision,
    build_tool_receipt,
    invoke_tool,
)
from integrations.pi.tool_event_flow import (
    process_tool_events,
    require_receipts,
)


def _claims_with_root(root: str) -> CapabilityClaims:
    return CapabilityClaims(
        filesystem_read=True,
        filesystem_read_root=root,
        filesystem_write=False,
        process_spawn=False,
        network_mode="provider_endpoints_only",
        tools_allowed=("read", "ls", "grep", "find"),
        skills_imported_ids=(),
        extensions_allowed=(),
        packages_allowed=(),
    )


# ── NEG-008 ───────────────────────────────────────────────────────────────


def test_NEG_008_tool_result_without_receipt_is_rejected(tmp_path: Path) -> None:
    """Si el flujo produce un tool_result_attached sin ToolReceipt, el
    bridge descarta el resultado con `MISSING_TOOL_RECEIPT`."""
    log = EventLog(execution_id="exec-1")
    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log.append(e1)
    e2 = make_event(
        execution_id="exec-1", sequence_number=2, event_id="tc-1",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-1", "tool": "read", "arguments": {"path": str(tmp_path)}},
        previous_event_hash=e1.event_hash,
    )
    log.append(e2)
    # Forzamos la situación: process_tool_events decide, pero
    # `require_receipts` se llama con una lista de receipts vacía.
    requested = log.by_type("tool_requested")
    with pytest.raises(MissingToolReceipt) as exc:
        require_receipts([], [], requested)
    assert exc.value.code == "MISSING_TOOL_RECEIPT"


# ── NEG-011 ───────────────────────────────────────────────────────────────


def test_NEG_011_symlink_escape_in_read(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(str(outside), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    with pytest.raises((ScopeLinkEscapeDenied, ScopePathDenied)):
        invoke_tool(
            tool="read",
            arguments={"path": str(link)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims_with_root(str(tmp_path)),
        )


def test_NEG_011_symlink_escape_in_ls(tmp_path: Path) -> None:
    outside_dir = tmp_path.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "secret.txt").write_text("x", encoding="utf-8")
    link_dir = tmp_path / "linkdir"
    try:
        os.symlink(str(outside_dir), str(link_dir))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    with pytest.raises((ScopeLinkEscapeDenied, ScopePathDenied)):
        invoke_tool(
            tool="ls",
            arguments={"path": str(link_dir)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims_with_root(str(tmp_path)),
        )


# ── NEG-012 ───────────────────────────────────────────────────────────────


def test_NEG_012_unc_path_rejected_in_phase2(tmp_path: Path) -> None:
    if os.name != "nt":
        # En sistemas no-Windows, una UNC `\\server\share` se rechaza
        # en el scope_validator.
        with pytest.raises(ScopePathDenied):
            invoke_tool(
                tool="read",
                arguments={"path": r"\\evil-server\share\x.txt"},
                scope_root=str(tmp_path),
                execution_id="exec-1",
                tool_call_id="tc-1",
                claims=_claims_with_root(str(tmp_path)),
            )
    else:
        # En Windows, rutas tipo `C:\` fuera de scope.
        with pytest.raises(ScopePathDenied):
            invoke_tool(
                tool="read",
                arguments={"path": r"C:\Windows\System32\drivers\etc\hosts"},
                scope_root=str(tmp_path),
                execution_id="exec-1",
                tool_call_id="tc-1",
                claims=_claims_with_root(str(tmp_path)),
            )


def test_NEG_012_traversal_in_find(tmp_path: Path) -> None:
    """`..` debe rechazarse en `find`."""
    with pytest.raises(ScopePathDenied):
        invoke_tool(
            tool="find",
            arguments={"path": str(tmp_path / ".." / "etc")},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=_claims_with_root(str(tmp_path)),
        )


# ── NEG-022 ───────────────────────────────────────────────────────────────


def test_NEG_022_unregistered_tool_blocks_execution(tmp_path: Path) -> None:
    log = EventLog(execution_id="exec-1")
    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log.append(e1)
    e2 = make_event(
        execution_id="exec-1", sequence_number=2, event_id="tc-1",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-1", "tool": "bash", "arguments": {"command": "rm"}},
        previous_event_hash=e1.event_hash,
    )
    log.append(e2)
    flow = process_tool_events(
        log=log,
        claims=_claims_with_root(str(tmp_path)),
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=e2.event_hash,
    )
    # La ejecución NO se interrumpe (deny) pero el receipt registra.
    assert flow.new_events[0].payload["decision"] == "deny"
    assert flow.new_events[0].payload["rule_code"] == "TOOL_NOT_ALLOWED"
    assert flow.receipts[0].status == "denied"
    # Si la tool es `write`, el bridge aborta con MutationPhaseLocked
    # via policy_gate (write siempre denegado).
    log2 = EventLog(execution_id="exec-2")
    e3 = make_event(
        execution_id="exec-2", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log2.append(e3)
    e4 = make_event(
        execution_id="exec-2", sequence_number=2, event_id="tc-2",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-2", "tool": "write", "arguments": {"path": "x"}},
        previous_event_hash=e3.event_hash,
    )
    log2.append(e4)
    flow2 = process_tool_events(
        log=log2,
        claims=_claims_with_root(str(tmp_path)),
        scope_root=str(tmp_path),
        execution_id="exec-2",
        start_sequence=10,
        last_event_hash=e4.event_hash,
    )
    assert flow2.new_events[0].payload["decision"] == "deny"
    assert "TOOL_NOT_ALLOWED" in flow2.new_events[0].payload["rule_code"]


def test_NEG_022_known_tool_in_allowlist_not_in_claims_blocks(tmp_path: Path) -> None:
    """Una tool del allowlist global pero no declarada en claims."""
    claims = CapabilityClaims(
        filesystem_read=True,
        filesystem_read_root=str(tmp_path),
        filesystem_write=False,
        process_spawn=False,
        network_mode="provider_endpoints_only",
        tools_allowed=(),  # vacía
        skills_imported_ids=(),
        extensions_allowed=(),
        packages_allowed=(),
    )
    f = tmp_path / "x.txt"
    f.write_text("hi", encoding="utf-8")
    with pytest.raises(ToolNotAllowed):
        invoke_tool(
            tool="read",
            arguments={"path": str(f)},
            scope_root=str(tmp_path),
            execution_id="exec-1",
            tool_call_id="tc-1",
            claims=claims,
        )


# ── NEG-021 (TOCTOU) ──────────────────────────────────────────────────────


def test_NEG_021_toctou_detected_in_read(tmp_path: Path) -> None:
    """Verifica que el helper de TOCTOU detecta cambio de identidad."""
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

"""Fase 2 — tests del tool_event_flow."""
from __future__ import annotations

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
    MissingToolReceipt,
    ScopePathDenied,
    ToolNotAllowed,
)
from integrations.pi.event_capture import EventLog
from integrations.pi.tool_event_flow import (
    process_tool_events,
    require_receipts,
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


def _log_with_tool_request(
    execution_id: str, tool: str, arguments: dict, scope_root: str
) -> tuple[EventLog, str]:
    log = EventLog(execution_id=execution_id)
    e1 = make_event(
        execution_id=execution_id, sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={"k": "v"},
        previous_event_hash="0" * 16,
    )
    log.append(e1)
    e2 = make_event(
        execution_id=execution_id, sequence_number=2, event_id="tc-1",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-1", "tool": tool, "arguments": arguments},
        previous_event_hash=e1.event_hash,
    )
    log.append(e2)
    return log, e2.event_hash


def test_process_tool_events_emits_policy_and_result(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    log, prev_hash = _log_with_tool_request(
        execution_id="exec-1",
        tool="read",
        arguments={"path": str(f)},
        scope_root=str(tmp_path),
    )
    flow = process_tool_events(
        log=log,
        claims=_claims(filesystem_read_root=str(tmp_path)),
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=prev_hash,
    )
    # 2 eventos por tool: policy + result
    assert len(flow.new_events) == 2
    assert flow.new_events[0].event_type == "tool_policy_decided"
    assert flow.new_events[0].payload["decision"] == "allow"
    assert flow.new_events[1].event_type == "tool_result_attached"
    assert flow.new_events[1].payload["status"] == "completed"
    assert flow.new_events[1].payload["tool_receipt_id"] == "tc-1"
    # El chain encadena correctamente.
    assert flow.new_events[1].previous_event_hash == flow.new_events[0].event_hash
    assert flow.new_events[0].previous_event_hash == prev_hash
    assert len(flow.receipts) == 1
    receipt = flow.receipts[0]
    assert receipt.tool_call_id == "tc-1"
    assert receipt.policy_decision == "allow"


def test_process_tool_events_denies_unknown_tool(tmp_path: Path) -> None:
    log, prev_hash = _log_with_tool_request(
        execution_id="exec-1",
        tool="bash",
        arguments={"command": "evil"},
        scope_root=str(tmp_path),
    )
    flow = process_tool_events(
        log=log,
        claims=_claims(),
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=prev_hash,
    )
    assert flow.new_events[0].payload["decision"] == "deny"
    assert flow.new_events[0].payload["rule_code"] == "TOOL_NOT_ALLOWED"
    assert flow.receipts[0].policy_decision == "deny"
    assert flow.receipts[0].status == "denied"


def test_process_tool_events_denies_path_outside_scope(tmp_path: Path) -> None:
    outside = tmp_path.parent / "evil.txt"
    outside.write_text("evil", encoding="utf-8")
    log, prev_hash = _log_with_tool_request(
        execution_id="exec-1",
        tool="read",
        arguments={"path": str(outside)},
        scope_root=str(tmp_path),
    )
    flow = process_tool_events(
        log=log,
        claims=_claims(filesystem_read_root=str(tmp_path)),
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=prev_hash,
    )
    assert flow.new_events[0].payload["decision"] == "deny"
    assert flow.new_events[1].payload["status"] == "denied"


def test_process_tool_events_with_no_requests_returns_empty() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log.append(e1)
    flow = process_tool_events(
        log=log,
        claims=_claims(),
        scope_root="/tmp",
        execution_id="exec-1",
        start_sequence=2,
        last_event_hash=e1.event_hash,
    )
    assert flow.new_events == []
    assert flow.receipts == []


def test_require_receipts_raises_when_missing() -> None:
    events = [
        make_event(
            execution_id="exec-1", sequence_number=1, event_id="e1",
            event_type="tool_requested", payload={"tool": "read"},
            previous_event_hash="0" * 16,
        )
    ]
    with pytest.raises(MissingToolReceipt):
        require_receipts([], [], events)


def test_require_receipts_passes_when_present() -> None:
    fake_receipt = object()
    require_receipts([], [fake_receipt], [
        type("E", (), {
            "event_type": "tool_requested",
            "payload": {"tool": "read"},
        })()
    ])


def test_process_tool_events_handles_multiple_requests(tmp_path: Path) -> None:
    f1 = tmp_path / "a.txt"
    f1.write_text("a", encoding="utf-8")
    f2 = tmp_path / "b.txt"
    f2.write_text("b", encoding="utf-8")
    log = EventLog(execution_id="exec-1")
    e1 = make_event(
        execution_id="exec-1", sequence_number=1, event_id="e1",
        event_type="runtime_attested", payload={}, previous_event_hash="0" * 16,
    )
    log.append(e1)
    e2 = make_event(
        execution_id="exec-1", sequence_number=2, event_id="tc-1",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-1", "tool": "read", "arguments": {"path": str(f1)}},
        previous_event_hash=e1.event_hash,
    )
    log.append(e2)
    e3 = make_event(
        execution_id="exec-1", sequence_number=3, event_id="tc-2",
        event_type="tool_requested",
        payload={"tool_call_id": "tc-2", "tool": "read", "arguments": {"path": str(f2)}},
        previous_event_hash=e2.event_hash,
    )
    log.append(e3)
    flow = process_tool_events(
        log=log,
        claims=_claims(filesystem_read_root=str(tmp_path)),
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=e3.event_hash,
    )
    assert len(flow.new_events) == 4
    assert len(flow.receipts) == 2
    # Los events están encadenados.
    assert flow.new_events[1].previous_event_hash == flow.new_events[0].event_hash
    assert flow.new_events[2].previous_event_hash == flow.new_events[1].event_hash
    assert flow.new_events[3].previous_event_hash == flow.new_events[2].event_hash


def test_tool_call_id_is_unique_per_event(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi", encoding="utf-8")
    log, prev_hash = _log_with_tool_request(
        execution_id="exec-1",
        tool="read",
        arguments={"path": str(f)},
        scope_root=str(tmp_path),
    )
    flow = process_tool_events(
        log=log,
        claims=_claims(filesystem_read_root=str(tmp_path)),
        scope_root=str(tmp_path),
        execution_id="exec-1",
        start_sequence=10,
        last_event_hash=prev_hash,
    )
    policy_id = flow.new_events[0].event_id
    result_id = flow.new_events[1].event_id
    assert policy_id.endswith("-policy")
    assert result_id.endswith("-result")

"""Tests del protocolo JSONL."""
from __future__ import annotations

import json

import pytest

from integrations.pi.contracts import make_event
from integrations.pi.errors import (
    BridgeProtocolViolation,
    OutputLimitExceeded,
    UnknownEvent,
)
from integrations.pi.protocol import (
    MAX_EVENT_BYTES,
    MAX_EVENTS_TOTAL,
    ProtocolLimits,
    decode_event,
    encode_event,
    iter_events,
)


def _event(seq: int, event_type: str = "runtime_attested", payload: dict | None = None):
    return make_event(
        execution_id="exec-1",
        sequence_number=seq,
        event_id=f"ev-{seq}",
        event_type=event_type,
        payload=payload or {"k": "v"},
        previous_event_hash="0" * 16,
    )


def test_encode_decode_roundtrip() -> None:
    event = _event(1, "runtime_attested", {"home": "/tmp/x"})
    line = encode_event(event)
    decoded = decode_event(line, phase=0)
    assert decoded.execution_id == "exec-1"
    assert decoded.sequence_number == 1
    assert decoded.event_type == "runtime_attested"
    assert decoded.payload == {"home": "/tmp/x"}


def test_decode_rejects_invalid_json() -> None:
    with pytest.raises(BridgeProtocolViolation):
        decode_event("{not json", phase=0)


def test_decode_rejects_empty_line() -> None:
    with pytest.raises(BridgeProtocolViolation):
        decode_event("", phase=0)


def test_decode_rejects_object_required() -> None:
    with pytest.raises(BridgeProtocolViolation):
        decode_event("[]", phase=0)


def test_decode_rejects_too_many_fields() -> None:
    payload = {f"k{i}": i for i in range(64)}
    payload["execution_id"] = "exec-1"
    payload["sequence_number"] = 1
    payload["event_id"] = "ev-1"
    payload["event_type"] = "runtime_attested"
    payload["timestamp"] = "2025-01-01T00:00:00+00:00"
    payload["payload"] = {}
    payload["previous_event_hash"] = ""
    payload["event_hash"] = ""
    payload["redaction_applied"] = False
    payload["source"] = "pi_sidecar"
    line = json.dumps(payload)
    with pytest.raises(OutputLimitExceeded):
        decode_event(line, phase=0)


def test_decode_rejects_unknown_event_in_phase_0() -> None:
    event = _event(1, "agent_step_started", {})
    line = encode_event(event)
    with pytest.raises(UnknownEvent):
        decode_event(line, phase=0)


def test_decode_accepts_phase_3_event_in_phase_3() -> None:
    event = _event(1, "agent_step_started", {})
    line = encode_event(event)
    decoded = decode_event(line, phase=3)
    assert decoded.event_type == "agent_step_started"


def test_decode_rejects_oversized_line() -> None:
    huge = "x" * (MAX_EVENT_BYTES + 1)
    with pytest.raises(OutputLimitExceeded):
        decode_event(huge, phase=0)


def test_iter_events_enforces_monotonic_order() -> None:
    e1 = _event(1)
    e2 = _event(2)
    lines = [encode_event(e1), encode_event(e2)]
    list(iter_events(lines, phase=0))


def test_iter_events_rejects_out_of_order() -> None:
    e1 = _event(2)
    e2 = _event(1)
    lines = [encode_event(e1), encode_event(e2)]
    with pytest.raises(BridgeProtocolViolation):
        list(iter_events(lines, phase=0))


def test_iter_events_enforces_max_count() -> None:
    limits = ProtocolLimits(max_events_total=2)
    e1 = _event(1)
    e2 = _event(2)
    e3 = _event(3)
    lines = [encode_event(e1), encode_event(e2), encode_event(e3)]
    with pytest.raises(OutputLimitExceeded):
        list(iter_events(lines, phase=0, limits=limits))


def test_encode_event_rejects_oversized_payload() -> None:
    event = _event(1, "runtime_attested", {"big": "x" * (MAX_EVENT_BYTES + 10)})
    with pytest.raises(OutputLimitExceeded):
        encode_event(event)

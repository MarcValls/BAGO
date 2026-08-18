"""Fase 1 — tests de event_capture."""
from __future__ import annotations

import pytest

from integrations.pi.contracts import make_event
from integrations.pi.errors import BridgeProtocolViolation, OutputLimitExceeded
from integrations.pi.event_capture import EventLog
from integrations.pi.protocol import encode_event


def _ev(seq: int, et: str = "runtime_attested", payload: dict | None = None,
        prev: str = "0" * 16):
    return make_event(
        execution_id="exec-1",
        sequence_number=seq,
        event_id=f"ev-{seq}",
        event_type=et,
        payload=payload or {"k": "v"},
        previous_event_hash=prev,
    )


def test_log_appends_event_with_correct_chain() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1)
    log.append(e1)
    assert len(log) == 1
    assert log.first_hash() == e1.event_hash
    assert log.last_hash() == e1.event_hash


def test_log_rejects_broken_chain() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1)
    log.append(e1)
    # Intentar añadir un evento cuyo previous_event_hash no coincide
    # con el event_hash del último registrado.
    bad = _ev(2, prev="ffffffffffffffff")
    with pytest.raises(BridgeProtocolViolation) as exc:
        log.append(bad)
    assert "event chain broken" in str(exc.value.reason)


def test_log_rejects_tampered_event_hash() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1)
    log.append(e1)
    # Construir un evento cuyo event_hash ha sido alterado (longitud
    # inválida). El log debe detectarlo al añadirlo, no propagarlo.
    tampered = make_event(
        execution_id=e1.execution_id,
        sequence_number=e1.sequence_number + 1,
        event_id="tampered",
        event_type="model_output_delta",
        payload={"delta": "x"},
        previous_event_hash=e1.event_hash,
    )
    # Alterar el event_hash a longitud no-64.
    object.__setattr__(tampered, "event_hash", "deadbeef" * 4)  # 32 chars
    with pytest.raises(BridgeProtocolViolation) as exc:
        log.append(tampered)
    assert "event_hash missing or malformed" in str(exc.value.reason)


def test_log_rejects_chain_break_after_legit_event() -> None:
    """Si un evento declara un previous_event_hash que no coincide con
    el último registrado, el log detecta la ruptura de cadena."""
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1)
    log.append(e1)
    # Construir un evento con previous_event_hash incorrecto.
    bad = make_event(
        execution_id=e1.execution_id,
        sequence_number=e1.sequence_number + 1,
        event_id="bad",
        event_type="model_output_delta",
        payload={"delta": "x"},
        previous_event_hash="a" * 64,  # 64 chars hex pero incorrecto
    )
    with pytest.raises(BridgeProtocolViolation) as exc:
        log.append(bad)
    assert "event chain broken" in str(exc.value.reason)


def test_log_extends_from_jsonl_lines() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1)
    line1 = encode_event(e1)
    # El segundo evento debe encadenarse al primero.
    e2 = _ev(2, prev=e1.event_hash)
    line2 = encode_event(e2)
    log.extend([line1, line2])
    assert len(log) == 2
    assert log.first_hash() == e1.event_hash
    assert log.last_hash() == e2.event_hash


def test_log_rejects_oversized_total() -> None:
    from integrations.pi.protocol import ProtocolLimits
    log = EventLog(
        execution_id="exec-1",
        limits=ProtocolLimits(max_events_total=1),
    )
    log.append(_ev(1))
    with pytest.raises(OutputLimitExceeded):
        log.append(_ev(2, prev=log.last_hash()))


def test_log_final_status_pi_finished() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1)
    log.append(e1)
    e2 = _ev(2, et="pi_finished", prev=e1.event_hash, payload={"finish_reason": "stop"})
    log.append(e2)
    assert log.final_status() == "EXECUTION_COMPLETED_UNVERIFIED"


def test_log_final_status_no_events_is_rejected() -> None:
    log = EventLog(execution_id="exec-1")
    assert log.final_status() == "REJECTED"


def test_log_final_status_without_pi_finished_is_rejected() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1, et="model_output_delta")
    log.append(e1)
    assert log.final_status() == "REJECTED"


def test_log_by_type_filters() -> None:
    log = EventLog(execution_id="exec-1")
    e1 = _ev(1, et="runtime_attested")
    log.append(e1)
    e2 = _ev(2, et="pi_finished", prev=e1.event_hash, payload={"finish_reason": "stop"})
    log.append(e2)
    finished = log.by_type("pi_finished")
    assert len(finished) == 1
    assert finished[0].event_type == "pi_finished"


def test_log_requires_execution_id() -> None:
    with pytest.raises(BridgeProtocolViolation):
        EventLog(execution_id="")

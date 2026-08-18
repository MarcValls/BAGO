"""protocol.py — serialización JSONL, validación de orden y límites.

El sidecar y BAGO se comunican por líneas JSON. El bridge es el único
responsable de validar que:
    - El número de campos por línea no exceda un máximo.
    - El tamaño por línea no exceda `MAX_EVENT_BYTES`.
    - El total de líneas no exceda `MAX_EVENTS_TOTAL`.
    - El orden de eventos sea monotónico por `sequence_number`.
    - Los `event_type` pertenezcan a la allowlist de la fase.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

from .contracts import ALLOWED_EVENTS_BY_PHASE, BridgeEvent
from .errors import (
    BridgeProtocolViolation,
    OutputLimitExceeded,
    UnknownEvent,
)


MAX_EVENT_BYTES: int = 256 * 1024  # 256 KiB por evento
MAX_EVENTS_TOTAL: int = 4096
MAX_FIELDS_PER_EVENT: int = 32


@dataclass(frozen=True)
class ProtocolLimits:
    max_event_bytes: int = MAX_EVENT_BYTES
    max_events_total: int = MAX_EVENTS_TOTAL
    max_fields_per_event: int = MAX_FIELDS_PER_EVENT


def encode_event(event: BridgeEvent, *, limits: ProtocolLimits | None = None) -> str:
    """Serializa un evento a una línea JSON terminada en `\\n`."""
    limits = limits or ProtocolLimits()
    payload = event.to_dict()
    if len(payload) > limits.max_fields_per_event:
        raise OutputLimitExceeded(
            "event has too many fields",
            details={"count": len(payload), "max": limits.max_fields_per_event},
        )
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    encoded = line.encode("utf-8")
    if len(encoded) > limits.max_event_bytes:
        raise OutputLimitExceeded(
            "event exceeds byte limit",
            details={"bytes": len(encoded), "max": limits.max_event_bytes},
        )
    return line


def decode_event(line: str, *, phase: int, limits: ProtocolLimits | None = None) -> BridgeEvent:
    """Decodifica y valida una línea JSONL.

    - Lanza `BridgeProtocolViolation` ante JSON inválido o estructura
      incorrecta.
    - Lanza `UnknownEvent` si el `event_type` no está permitido por la
      fase (esto puede mapearse a `BRIDGE_PROTOCOL_VIOLATION`).
    - Lanza `OutputLimitExceeded` si la línea excede `max_event_bytes`.
    """
    limits = limits or ProtocolLimits()
    if not line or not line.strip():
        raise BridgeProtocolViolation("empty line")
    if len(line.encode("utf-8")) > limits.max_event_bytes:
        raise OutputLimitExceeded(
            "line exceeds byte limit",
            details={"max": limits.max_event_bytes},
        )
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise BridgeProtocolViolation(
            "invalid json",
            details={"error": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise BridgeProtocolViolation("event must be an object")
    if len(data) > limits.max_fields_per_event:
        raise OutputLimitExceeded(
            "event has too many fields",
            details={"count": len(data), "max": limits.max_fields_per_event},
        )

    event_type = str(data.get("event_type") or "")
    allowed = ALLOWED_EVENTS_BY_PHASE.get(phase, frozenset())
    if event_type not in allowed:
        raise UnknownEvent(
            "event_type not in allowlist",
            details={"event_type": event_type, "phase": phase},
        )

    try:
        return BridgeEvent(
            execution_id=str(data["execution_id"]),
            sequence_number=int(data["sequence_number"]),
            event_id=str(data["event_id"]),
            event_type=event_type,
            timestamp=str(data["timestamp"]),
            payload=dict(data.get("payload") or {}),
            previous_event_hash=str(data.get("previous_event_hash") or ""),
            event_hash=str(data.get("event_hash") or ""),
            redaction_applied=bool(data.get("redaction_applied") or False),
            source=str(data.get("source") or "pi_sidecar"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BridgeProtocolViolation(
            "event missing required fields",
            details={"error": str(exc)},
        ) from exc


def iter_events(
    lines: Iterable[str], *, phase: int, limits: ProtocolLimits | None = None
) -> Iterator[BridgeEvent]:
    """Itera líneas JSONL, valida cada evento, exige monotonía."""
    limits = limits or ProtocolLimits()
    last_seq = -1
    count = 0
    for line in lines:
        count += 1
        if count > limits.max_events_total:
            raise OutputLimitExceeded(
                "too many events",
                details={"max": limits.max_events_total},
            )
        event = decode_event(line, phase=phase, limits=limits)
        if event.sequence_number <= last_seq:
            raise BridgeProtocolViolation(
                "events out of order",
                details={
                    "previous": last_seq,
                    "received": event.sequence_number,
                },
            )
        last_seq = event.sequence_number
        yield event


def encode_stream(
    events: Iterable[BridgeEvent], *, limits: ProtocolLimits | None = None
) -> Iterator[str]:
    """Generador inverso: de eventos a líneas JSONL."""
    limits = limits or ProtocolLimits()
    count = 0
    for event in events:
        count += 1
        if count > limits.max_events_total:
            raise OutputLimitExceeded(
                "stream too long",
                details={"max": limits.max_events_total},
            )
        yield encode_event(event, limits=limits)


__all__ = [
    "MAX_EVENT_BYTES",
    "MAX_EVENTS_TOTAL",
    "MAX_FIELDS_PER_EVENT",
    "ProtocolLimits",
    "encode_event",
    "decode_event",
    "iter_events",
    "encode_stream",
]

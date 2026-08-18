"""event_capture.py — captura, numeración y hash encadenado de eventos.

Cada evento se valida con `protocol.decode_event` y luego se
encadena con el anterior vía `event_hash` ↔ `previous_event_hash`.
`EventLog` mantiene un buffer in-memory en Fase 1; en Fase 3 este
buffer se sustituye por un append-only file con `fsync` por evento.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from .contracts import BridgeEvent
from .errors import BridgeProtocolViolation, OutputLimitExceeded
from .protocol import (
    MAX_EVENTS_TOTAL,
    ProtocolLimits,
    decode_event,
)


@dataclass
class EventLog:
    """Registro en memoria de eventos con hash encadenado.

    El registro **no** es persistencia BAGO. Es el buffer que el
    bridge entrega al `receipt_factory` para emitir el `ContextReceipt`
    canónico. Cualquiera que sea la duración de la ejecución, el
    buffer respeta `MAX_EVENTS_TOTAL`.
    """

    execution_id: str
    limits: ProtocolLimits = field(default_factory=ProtocolLimits)
    _events: list[BridgeEvent] = field(default_factory=list)
    _last_hash: str = "0" * 16

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise BridgeProtocolViolation("event log requires execution_id")

    def __len__(self) -> int:
        return len(self._events)

    def append(self, line_or_event: str | BridgeEvent) -> BridgeEvent:
        if len(self._events) >= self.limits.max_events_total:
            raise OutputLimitExceeded(
                "event log full",
                details={"max": self.limits.max_events_total},
            )
        if isinstance(line_or_event, BridgeEvent):
            event = line_or_event
        else:
            event = decode_event(
                line_or_event, phase=_phase_for_event_type(self._events)
            )
        # Encadenamiento: el previous_event_hash del evento entrante
        # debe coincidir con el event_hash del último evento registrado.
        # Esto es la firma de la cadena; BAGO valida la cadena, el
        # sidecar firma cada evento individualmente.
        if event.previous_event_hash != self._last_hash:
            raise BridgeProtocolViolation(
                "event chain broken",
                details={
                    "expected_previous": self._last_hash,
                    "received_previous": event.previous_event_hash,
                },
            )
        # Validación de formato del hash: debe existir y tener 64
        # caracteres hexadecimales. No re-calculamos el hash: el sidecar
        # es quien firma.
        if not event.event_hash or len(event.event_hash) != 64:
            raise BridgeProtocolViolation(
                "event_hash missing or malformed",
                details={"event_id": event.event_id, "hash": event.event_hash},
            )
        import re as _re
        if not _re.fullmatch(r"[0-9a-f]{64}", event.event_hash):
            raise BridgeProtocolViolation(
                "event_hash not hex",
                details={"event_id": event.event_id, "hash": event.event_hash},
            )
        self._events.append(event)
        self._last_hash = event.event_hash
        return event

    def extend(self, lines: Iterable[str]) -> list[BridgeEvent]:
        added: list[BridgeEvent] = []
        for line in lines:
            added.append(self.append(line))
        return added

    def first_hash(self) -> str:
        if not self._events:
            return ""
        first = self._events[0]
        return first.event_hash or ""

    def last_hash(self) -> str:
        if not self._events:
            return ""
        last = self._events[-1]
        return last.event_hash or ""

    def events(self) -> list[BridgeEvent]:
        return list(self._events)

    def iter(self) -> Iterator[BridgeEvent]:
        return iter(self._events)

    def by_type(self, event_type: str) -> list[BridgeEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def final_status(self) -> str:
        """Devuelve `EXECUTION_COMPLETED_UNVERIFIED` si el último evento
        fue `pi_finished`, o `REJECTED` en caso contrario.

        El bridge **nunca** devuelve `done`/`verified`/`certified`."""
        if not self._events:
            return "REJECTED"
        last = self._events[-1]
        if last.event_type == "pi_finished":
            return "EXECUTION_COMPLETED_UNVERIFIED"
        return "REJECTED"


def _phase_for_event_type(events: list[BridgeEvent]) -> int:
    """Determina la fase en función de los eventos ya vistos.

    Estrategia Fase 1: el bridge corre siempre en fase 1 (provider
    adapter), por lo que se devuelve 1. En Fase 3 este helper se
    ampliará para rastrear la fase activa del runner.
    """
    if events:
        return 1
    return 1


__all__ = ["EventLog", "MAX_EVENTS_TOTAL"]

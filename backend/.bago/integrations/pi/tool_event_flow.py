"""tool_event_flow.py — orquesta el ciclo tool_requested → tool_result_attached.

Este módulo es el **manager de tool events** que conecta el sidecar
con el proxy BAGO. Toma los eventos `tool_requested` del log y los
mapea a invocaciones de `readonly_tool_proxy.invoke_tool`, emite
`tool_policy_decided` y `tool_result_attached`, y construye el
`ToolReceipt` asociado.

Reglas (Fase 2):
    - Toda invocación de tool sin `tool_receipt_id` en su evento
      `tool_result_attached` se descarta: `MISSING_TOOL_RECEIPT`.
    - Si la tool emite `tool_requested` pero el `policy_decision` es
      `deny`, el `tool_result_attached` se emite con un receipt de
      denegación y la ejecución **no se interrumpe**; el modelo debe
      recibir la denegación como información.
    - Si la tool no está en el allowlist, se aborta toda la ejecución
      con `TOOL_NOT_ALLOWED`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .contracts import (
    ALLOWED_TOOLS,
    BridgeEvent,
    CapabilityClaims,
    _now_iso,
    make_event,
)
from .errors import (
    BridgeError,
    MissingToolReceipt,
    OutputLimitExceeded,
    ToolNotAllowed,
)
from .event_capture import EventLog
from .readonly_tool_proxy import (
    ToolDecision,
    build_tool_receipt,
    invoke_tool,
)


@dataclass
class ToolFlowResult:
    """Resultado del flujo de tool events para un log dado."""

    receipts: list[Any] = field(default_factory=list)
    decisions: list[ToolDecision] = field(default_factory=list)
    new_events: list[BridgeEvent] = field(default_factory=list)
    last_event_hash: str = ""


def _now() -> str:
    return _now_iso()


def process_tool_events(
    *,
    log: EventLog,
    claims: CapabilityClaims,
    scope_root: str,
    execution_id: str,
    start_sequence: int,
    last_event_hash: str,
) -> ToolFlowResult:
    """Procesa los `tool_requested` del log y emite los eventos
    `tool_policy_decided` + `tool_result_attached` con su `ToolReceipt`.

    Devuelve los nuevos eventos para que el caller los encadene en el
    log. NO modifica el log original; el caller decide si los anexa.
    """
    requested = log.by_type("tool_requested")
    if not requested:
        return ToolFlowResult(last_event_hash=last_event_hash)

    result = ToolFlowResult(last_event_hash=last_event_hash)
    seq = start_sequence
    prev_hash = last_event_hash
    for event in requested:
        payload = event.payload
        tool = str(payload.get("tool") or "")
        tool_call_id = str(payload.get("tool_call_id") or event.event_id)
        arguments = dict(payload.get("arguments") or {})

        # 1. tool_policy_decided
        seq += 1
        decision_payload: dict[str, Any]
        receipt = None
        decision: ToolDecision
        if tool not in ALLOWED_TOOLS:
            decision = ToolDecision(
                allowed=False,
                tool=tool,
                rule_code="TOOL_NOT_ALLOWED",
            )
            decision_payload = {
                "tool_call_id": tool_call_id,
                "tool": tool,
                "decision": "deny",
                "rule_code": decision.rule_code,
            }
        else:
            from .policy_gate import decide_tool

            policy = decide_tool(claims, tool)
            if not policy.allowed:
                decision = ToolDecision(
                    allowed=False,
                    tool=tool,
                    rule_code=policy.reason_code,
                )
                decision_payload = {
                    "tool_call_id": tool_call_id,
                    "tool": tool,
                    "decision": "deny",
                    "rule_code": decision.rule_code,
                }
            else:
                # 2. Ejecutar la tool.
                try:
                    decision = invoke_tool(
                        tool=tool,
                        arguments=arguments,
                        scope_root=scope_root,
                        execution_id=execution_id,
                        tool_call_id=tool_call_id,
                        claims=claims,
                    )
                except ToolNotAllowed as exc:
                    decision = ToolDecision(
                        allowed=False,
                        tool=tool,
                        rule_code=exc.code,
                    )
                except BridgeError as exc:
                    decision = ToolDecision(
                        allowed=False,
                        tool=tool,
                        rule_code=exc.code,
                        redactions=("arguments",),
                    )
                decision_payload = {
                    "tool_call_id": tool_call_id,
                    "tool": tool,
                    "decision": "allow" if decision.allowed else "deny",
                    "rule_code": decision.rule_code,
                }

        # Emitir tool_policy_decided
        ev_policy = make_event(
            execution_id=execution_id,
            sequence_number=seq,
            event_id=f"{tool_call_id}-policy",
            event_type="tool_policy_decided",
            payload=decision_payload,
            previous_event_hash=prev_hash,
        )
        result.new_events.append(ev_policy)
        prev_hash = ev_policy.event_hash
        result.decisions.append(decision)

        # 3. Construir ToolReceipt
        requested_path = str(arguments.get("path") or arguments.get("file") or "")
        receipt = build_tool_receipt(
            tool_call_id=tool_call_id,
            execution_id=execution_id,
            tool=tool,
            arguments=arguments,
            requested_path=requested_path,
            scope_root=scope_root,
            decision=decision,
        )
        result.receipts.append(receipt)

        # 4. Emitir tool_result_attached
        seq += 1
        result_payload: dict[str, Any] = {
            "tool_call_id": tool_call_id,
            "tool": tool,
            "status": receipt.status,
            "tool_receipt_id": tool_call_id,  # el receipt_id == call_id
            "size_bytes": receipt.result_size_bytes,
            "result_hash": receipt.result_hash,
        }
        if decision.allowed and decision.result is not None:
            result_payload["output"] = decision.result.output
        ev_result = make_event(
            execution_id=execution_id,
            sequence_number=seq,
            event_id=f"{tool_call_id}-result",
            event_type="tool_result_attached",
            payload=result_payload,
            previous_event_hash=prev_hash,
        )
        result.new_events.append(ev_result)
        prev_hash = ev_result.event_hash

    result.last_event_hash = prev_hash
    return result


def require_receipts(
    decisions: list[ToolDecision],
    receipts: list[Any],
    tool_requested_events: list[BridgeEvent],
) -> None:
    """Verifica que cada tool call tenga su receipt. Falla con
    `MISSING_TOOL_RECEIPT` si falta alguno. Esta función es la
    segunda condición del PLAN §2.5: 'Todo tool result sin ToolReceipt
    se descarta'."""
    if not tool_requested_events:
        return
    if len(receipts) < len(tool_requested_events):
        raise MissingToolReceipt(
            "missing tool receipt(s)",
            details={
                "requested": len(tool_requested_events),
                "receipts": len(receipts),
            },
        )


__all__ = [
    "ToolFlowResult",
    "process_tool_events",
    "require_receipts",
]

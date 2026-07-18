"""tool_receipt.py — tipo canónico de ToolReceipt BAGO.

**Promovido a canónico en Sprint 4 (Fase 2).** El Sprint 0 lo dejó
local al bridge; el Sprint 1 mantuvo esa decisión; el uso en Fase 2
demuestra que el tipo es cross-cutting (lo emite el bridge, lo
consume el validador, lo muestra la UI, lo firman los gates).

Este módulo es la **única definición** de ToolReceipt en el repo.
Otros módulos (incluido `integrations.pi.contracts`) lo importan
desde aquí vía import lazy para evitar ciclos.

Campos:
    tool_call_id       ID único de la tool call
    execution_id       ID de la ejecución BAGO
    tool               Nombre canónico (`read|ls|grep|find`)
    proxy_version      Versión del proxy que emitió el receipt
    arguments          Argumentos normalizados (sin secretos)
    arguments_hash     SHA-256[:16] de `arguments` canónico
    requested_path     Path tal como llegó del sidecar
    resolved_path      Path canónico tras `assert_within_scope`
    scope_root         Raíz autorizada para esta ejecución
    policy_decision    `allow` | `deny`
    policy_rule_code   Código estable del gate
    approval_id        ID de aprobación (futuro; vacío en Fase 0-3)
    status             `allowed` | `denied` | `failed` | `completed`
    result_size_bytes  Tamaño del resultado (0 si denegado)
    result_hash        SHA-256[:16] del contenido (0 si denegado)
    evidence_refs      Referencias a evidencias (futuro)
    redactions_applied Lista de campos redactados
    requested_at       ISO-8601
    decided_at         ISO-8601
    started_at         ISO-8601
    finished_at        ISO-8601
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ToolReceipt:
    tool_call_id: str
    execution_id: str
    tool: str
    proxy_version: str
    arguments: dict[str, Any]
    arguments_hash: str
    requested_path: str
    resolved_path: str
    scope_root: str
    policy_decision: str
    policy_rule_code: str
    approval_id: str
    status: str
    result_size_bytes: int
    result_hash: str
    evidence_refs: tuple[str, ...]
    redactions_applied: tuple[str, ...]
    requested_at: str
    decided_at: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def deny(
        cls,
        *,
        tool_call_id: str,
        execution_id: str,
        tool: str,
        arguments: dict[str, Any],
        requested_path: str,
        scope_root: str,
        rule_code: str,
        decision_reason: str = "",
    ) -> "ToolReceipt":
        now = _now_iso()
        return cls(
            tool_call_id=tool_call_id,
            execution_id=execution_id,
            tool=tool,
            proxy_version="0.1.0",
            arguments=dict(arguments),
            arguments_hash=_stable_hash(arguments),
            requested_path=requested_path,
            resolved_path="",
            scope_root=scope_root,
            policy_decision="deny",
            policy_rule_code=rule_code,
            approval_id="",
            status="denied",
            result_size_bytes=0,
            result_hash="0" * 16,
            evidence_refs=(),
            redactions_applied=("requested_path",) if not requested_path else (),
            requested_at=now,
            decided_at=now,
            started_at=now,
            finished_at=now,
        )


__all__ = ["ToolReceipt", "_stable_hash", "_now_iso"]

#!/usr/bin/env python3
"""Present internal task contracts as concise user-facing responses."""
from __future__ import annotations

from typing import Any

from task_response_contract import extract_task_response_json


def _items(value: Any, limit: int = 4) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("message") or item.get("summary") or item.get("path") or item.get("key") or "").strip()
        else:
            text = str(item).strip()
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def task_response_state(data: dict[str, Any], *, contract_ok: bool = True) -> str:
    if not contract_ok:
        return "failed"
    if _items(data.get("missing_information")):
        return "needs_confirmation"
    objective = str(data.get("objective") or "").strip()
    actionable = any(_items(data.get(key)) for key in ("proposed_changes", "validation_actions", "evidence"))
    if not objective or not actionable:
        return "needs_confirmation"
    return "done"


def present_task_response(
    data: dict[str, Any],
    *,
    user_message: str = "",
    contract_ok: bool = True,
) -> str:
    """Convert a validated internal contract into readable chat text."""
    if not contract_ok:
        return "No he podido validar la respuesta del modelo. No se ha marcado la tarea como completada."

    objective = str(data.get("objective") or "").strip()
    missing = _items(data.get("missing_information"))
    changes = _items(data.get("proposed_changes"))
    validation = _items(data.get("validation_actions"))
    evidence = _items(data.get("evidence"))

    if not objective:
        subject = (user_message or "la tarea").strip()
        return f"Necesito concretar el objetivo antes de continuar con: {subject}"

    lines = [objective]
    if missing:
        lines.append("Necesito confirmar: " + "; ".join(missing))
    if changes:
        lines.append("Cambios propuestos: " + "; ".join(changes))
    if validation:
        lines.append("Validación: " + "; ".join(validation))
    elif evidence:
        lines.append("Evidencia: " + "; ".join(evidence))
    return "\n\n".join(lines)


def present_legacy_task_content(text: str) -> tuple[str, str, dict[str, Any] | None]:
    """Sanitize historical contract-shaped assistant content."""
    try:
        data, _ = extract_task_response_json(text)
    except Exception:
        return text, "done", None
    required = {"intent", "objective", "facts", "evidence", "confidence"}
    if not required.issubset(data):
        return text, "done", None
    state = task_response_state(data)
    return present_task_response(data), state, data

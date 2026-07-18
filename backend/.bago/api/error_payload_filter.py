"""error_payload_filter.py — Detect and rewrite BAGO's internal error payload.

When a model response fails to satisfy the JSON contract, BAGO's
`_canonical_task_failure_payload` (in session_turn_mixin.py) emits a
canonical JSON blob with this shape:

    {
      "intent": "...",
      "objective": "...",
      "evidence": [{"type": "validation_error", "errors": [...], ...}],
      "validation_actions": ["repair_response", "revalidate_contract"],
      "missing_information": [...],
      "confidence": 0.0,
      ...
    }

That blob is an *internal* signal of the repair loop. It was being
streamed to the user verbatim, which is what produced the
`previous_response_excerpt` / `validation_actions` JSON fragments that
ended up being treated as the model's answer. The frontend then
re-injected that JSON into the next turn, poisoning context.

This module exposes two helpers:

  * `is_canonical_error_payload(s)` — detect it
  * `rewrite_to_user_friendly(s)`    — replace it with a readable message

The two HTTP handlers (`handlers_chat.py` and `handlers_chat_stream.py`)
use these helpers at the response boundary so the internal contract
never leaks to the user-facing SSE / JSON response.
"""
from __future__ import annotations

import json
from typing import Any


_CANONICAL_ACTIONS = ("repair_response", "revalidate_contract")


def is_canonical_error_payload(chunk: Any) -> bool:
    """True if `chunk` is the internal canonical error payload.

    Detection is intentionally tolerant: a real model response is
    markdown/prose and never carries `validation_actions: [repair_response,
    revalidate_contract]` together with an `evidence[0].type ==
    "validation_error"`. We test both signals and accept either.
    """
    if not isinstance(chunk, str):
        return False
    s = chunk.lstrip()
    if not s.startswith("{"):
        return False
    try:
        data = json.loads(s)
    except Exception:
        return False
    if not isinstance(data, dict):
        return False

    actions = data.get("validation_actions")
    if (
        isinstance(actions, list)
        and all(a in actions for a in _CANONICAL_ACTIONS)
    ):
        return True

    evidence = data.get("evidence")
    if isinstance(evidence, list) and evidence:
        first = evidence[0]
        if isinstance(first, dict) and first.get("type") == "validation_error":
            return True

    return False


def _extract_detail(raw: str) -> tuple[str, str | None]:
    """Best-effort: pull the first human-readable detail from the payload."""
    try:
        data = json.loads(raw)
    except Exception:
        return "", None
    if not isinstance(data, dict):
        return "", None

    evidence = data.get("evidence")
    if isinstance(evidence, list) and evidence:
        first = evidence[0]
        if isinstance(first, dict):
            errs = first.get("errors")
            if isinstance(errs, list) and errs:
                first_err = errs[0]
                if isinstance(first_err, dict):
                    detail = first_err.get("detail")
                    if detail:
                        return str(detail), "validation_error"
            excerpt = first.get("previous_response_excerpt")
            if excerpt:
                return str(excerpt), "previous_response_excerpt"

    missing = data.get("missing_information")
    if isinstance(missing, list) and missing:
        m = missing[0]
        if m:
            return str(m), "missing_information"

    return "", None


def rewrite_to_user_friendly(raw: str) -> str:
    """Translate the internal canonical error into a user-facing message.

    Returns a short, plain-text string. Never returns the raw JSON.
    """
    detail, kind = _extract_detail(raw)
    if detail:
        return (
            "⚠️ El modelo no generó una respuesta válida. "
            f"Detalle: {detail}. Reformula tu petición o cambia de modelo."
        )
    if kind:
        return (
            f"⚠️ El modelo no generó una respuesta válida (falla interna: {kind}). "
            "Reformula tu petición o cambia de modelo desde la barra superior."
        )
    return (
        "⚠️ El modelo no generó una respuesta válida (no cumplió el contrato "
        "JSON interno). Reformula tu petición o cambia de modelo desde la "
        "barra superior."
    )


def extract_diagnostic(raw: str) -> dict[str, Any]:
    """Return a small, safe-to-display diagnostic dict for the UI/logs."""
    detail, kind = _extract_detail(raw)
    return {
        "diagnostic": True,
        "kind": "validation_error",
        "detail": detail or None,
        "source": kind,
        "raw_excerpt": raw[:240] if isinstance(raw, str) else None,
    }

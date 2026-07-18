#!/usr/bin/env python3
"""task_response_contract.py - JSON contract for task-oriented model turns.

The contract is intentionally strict for review/execute/work turns:
the model must answer with a JSON object that can be parsed, validated, and
used by the session layer before any change is accepted.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


REQUIRED_KEYS = (
    "intent",
    "objective",
    "facts",
    "assumptions",
    "files_required",
    "symbols_required",
    "evidence",
    "risks",
    "proposed_changes",
    "validation_actions",
    "missing_information",
    "confidence",
)

TASK_INTENTS = {"review", "execute", "work"}


@dataclass(frozen=True)
class TaskResponseValidationReport:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    errors: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    raw_json: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": dict(self.data),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "raw_json": self.raw_json,
        }


def task_response_guidance(intent: str, *, user_message: str = "") -> str:
    """Return the JSON contract instruction block for task-oriented turns."""
    intent = (intent or "").strip().lower()
    if intent not in TASK_INTENTS:
        return ""
    lines = [
        "TASK RESPONSE CONTRACT",
        "Return ONLY a JSON object. No markdown, no code fences, no prose.",
        "Required keys:",
        ", ".join(REQUIRED_KEYS),
        "Types:",
        "intent: string",
        "objective: string",
        "facts: array",
        "assumptions: array",
        "files_required: array",
        "symbols_required: array",
        "evidence: array",
        "risks: array",
        "proposed_changes: array",
        "validation_actions: array",
        "missing_information: array",
        "confidence: number between 0 and 1",
        "Rules:",
        "- Do not invent files, symbols, commands, or evidence.",
        "- Use missing_information when evidence is insufficient.",
        "- Keep proposed_changes minimal.",
        "- If validation is pending, say so explicitly in validation_actions.",
        "- If you cannot comply, return a JSON object with the same keys and confidence 0.",
    ]
    if user_message:
        lines.extend([
            "User task:",
            user_message.strip(),
        ])
    return "\n".join(lines)


def _strip_code_fences(text: str) -> str:
    content = (text or "").strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", content, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return content


def _extract_balanced_object(text: str) -> str:
    content = _strip_code_fences(text)
    start = content.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1].strip()
    return ""


def extract_task_response_json(text: str) -> tuple[dict[str, Any], str]:
    """Extract and parse the first JSON object found in text."""
    candidates = [_strip_code_fences(text)]
    extracted = _extract_balanced_object(text)
    if extracted:
        candidates.insert(0, extracted)

    last_error = ""
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = str(exc)
            continue
        if isinstance(parsed, dict):
            return parsed, json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        last_error = "top_level_json_not_object"
    raise ValueError(last_error or "json_object_not_found")


def validate_task_response(text: str, *, intent: str = "") -> TaskResponseValidationReport:
    """Validate a task response against the JSON contract."""
    warnings: list[str] = []
    try:
        data, raw_json = extract_task_response_json(text)
    except Exception as exc:
        return TaskResponseValidationReport(
            ok=False,
            errors=({"name": "json_parse", "detail": str(exc)},),
            warnings=tuple(warnings),
        )

    errors: list[dict[str, Any]] = []
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append({"name": "missing_key", "key": key, "detail": f"missing {key}"})

    if "intent" in data and not isinstance(data["intent"], str):
        errors.append({"name": "invalid_type", "key": "intent", "detail": "intent must be string"})
    if intent and isinstance(data.get("intent"), str) and data["intent"].strip().lower() != intent.strip().lower():
        warnings.append("intent_mismatch")
    if "objective" in data and not isinstance(data["objective"], str):
        errors.append({"name": "invalid_type", "key": "objective", "detail": "objective must be string"})

    for key in ("facts", "assumptions", "files_required", "symbols_required", "evidence", "risks", "proposed_changes", "validation_actions", "missing_information"):
        if key in data and not isinstance(data[key], list):
            errors.append({"name": "invalid_type", "key": key, "detail": f"{key} must be array"})

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append({"name": "invalid_type", "key": "confidence", "detail": "confidence must be number"})
    elif not 0.0 <= float(confidence) <= 1.0:
        errors.append({"name": "out_of_range", "key": "confidence", "detail": "confidence must be between 0 and 1"})

    if isinstance(data.get("evidence"), list) and not data["evidence"]:
        warnings.append("empty_evidence")
    if isinstance(data.get("files_required"), list) and not data["files_required"]:
        warnings.append("empty_files_required")

    return TaskResponseValidationReport(
        ok=not errors,
        data=data,
        errors=tuple(errors),
        warnings=tuple(warnings),
        raw_json=raw_json,
    )


def canonicalize_task_response(data: dict[str, Any]) -> str:
    """Emit a stable JSON string for a validated task response."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)

#!/usr/bin/env python3
"""Bootstrap the translator layer.

Adds the shared translator piece root to sys.path
once, then delegates to the piece's own registry module.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_BOOTSTRAPPED = False

def _shared_base() -> Path:
    override = os.environ.get("BAGO_PIECES_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve() / "translators" / "shared" / "base"
    data_root = os.environ.get("BAGO_DATA_ROOT", "").strip()
    if data_root:
        return Path(data_root).expanduser().resolve() / "pieces" / "translators" / "shared" / "base"
    program_data = os.environ.get("ProgramData", "").strip()
    if program_data:
        return Path(program_data) / "BAGO" / "pieces" / "translators" / "shared" / "base"
    return Path.home() / "AppData" / "Local" / "BAGO" / "pieces" / "translators" / "shared" / "base"

def bootstrap_path() -> None:
    """Add the shared/base piece to sys.path so other pieces can `from ir_types import ...`."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    p = str(_shared_base())
    if p not in sys.path:
        sys.path.insert(0, p)
    _BOOTSTRAPPED = True

def _import_registry():
    bootstrap_path()
    import registry  # type: ignore  # noqa: E402
    return registry

def _ensure_ir_types_path() -> None:
    """Idempotent path injection so callers can `from ir_types import ...`."""
    bootstrap_path()

def list_translators() -> list[dict[str, Any]]:
    return _import_registry().list_translators()

def get_translator(piece_id: str):
    return _import_registry().get_translator(piece_id)

def smoke_test_piece(piece_id: str) -> dict[str, Any]:
    """Round-trip a sample conversation through encode -> decode for the given piece.

    Returns a dict with: ok, piece_id, sample_request_keys, roundtrip_ok, mismatches.
    Does NOT require network access. Only validates that the IR survives
    encode->decode without losing information.
    """
    bootstrap_path()
    from ir_types import (  # noqa: E402
        IRConversation, IRMessage, ROLE_SYSTEM, ROLE_USER, ROLE_ASSISTANT, ROLE_TOOL,
        PART_TYPE_TEXT, PART_TYPE_PLAN, PART_TYPE_EVIDENCE, PART_TYPE_TOOL_CALL, PART_TYPE_TOOL_RESULT,
    )

    def _find_part(parts, type_name):
        for p in parts:
            if p.get("type") == type_name:
                return p
        return None

    piece = get_translator(piece_id)
    if piece is None:
        return {"ok": False, "piece_id": piece_id, "error": "piece not found"}

    ir_in = IRConversation(
        messages=[
            IRMessage(id="m1", role=ROLE_SYSTEM, parts=[
                {"type": "text", "text": "You are BAGO. Always respond with a plan and evidence."},
            ]),
            IRMessage(id="m2", role=ROLE_USER, parts=[
                {"type": "text", "text": "Find the BAGO install on this machine."},
            ]),
            IRMessage(id="m3", role=ROLE_ASSISTANT, parts=[
                {"type": "text", "text": "I'll scan the registry."},
                {"type": "plan", "plan_id": "p-1", "steps": [{"id": 1, "text": "scan registry"}], "status": "draft"},
                {"type": "evidence", "claim_id": "c-1", "hash": "sha256:abcd", "refs": ["registry.json"]},
                {"type": "tool_call", "name": "scan_registry", "args": {"path": "C:/ProgramData/BAGO"}},
            ]),
            IRMessage(id="m4", role=ROLE_TOOL, parts=[
                {"type": "tool_result", "name": "scan_registry", "result": {"ok": True, "found": 6}, "is_error": False},
            ]),
        ],
        model_hint=piece.manifest.get("model_id", ""),
    )

    try:
        request = piece.encode.encode(ir_in)
    except Exception as exc:
        return {"ok": False, "piece_id": piece_id, "error": f"encode failed: {exc!r}"}

    # Build a fake provider response that mirrors the assistant message.
    sample_response = _build_sample_response(piece, ir_in.messages[2], _find_part)
    try:
        ir_out = piece.decode.decode(sample_response)
    except Exception as exc:
        return {"ok": False, "piece_id": piece_id, "error": f"decode failed: {exc!r}"}

    mismatches: list[str] = []
    if not ir_out.messages:
        mismatches.append("decoded conversation has no messages")
    else:
        out_msg = ir_out.messages[0]
        if out_msg.role != ROLE_ASSISTANT:
            mismatches.append(f"expected role=assistant, got {out_msg.role}")
        if not any(p.get("type") == PART_TYPE_PLAN for p in out_msg.parts):
            mismatches.append("plan part lost in roundtrip")
        if not any(p.get("type") == PART_TYPE_EVIDENCE for p in out_msg.parts):
            mismatches.append("evidence part lost in roundtrip")
        if not any(p.get("type") == PART_TYPE_TOOL_CALL for p in out_msg.parts):
            mismatches.append("tool_call part lost in roundtrip")

    return {
        "ok":               not mismatches,
        "piece_id":         piece_id,
        "sample_request_keys": sorted(request.keys()) if isinstance(request, dict) else [],
        "roundtrip_ok":     not mismatches,
        "mismatches":       mismatches,
    }

def smoke_test_all() -> list[dict[str, Any]]:
    """Run smoke_test_piece() for all real translator pieces (skip shared/base)."""
    return [smoke_test_piece(p["piece_id"]) for p in list_translators()
            if p["piece_id"] != "translator.shared.base"]

def _build_sample_response(piece, assistant_message, find_part) -> dict[str, Any]:
    """Build a fake provider response that contains a plan, evidence and a tool_call.

    The fake response uses whatever the model_family understands:
    - openai:        {"choices": [{"message": {"role": "assistant", "content": "..."}}]}
    - anthropic:     {"content": [{"type": "text", "text": "..."}, {"type": "tool_use", ...}]}
    - ollama:        {"message": {"role": "assistant", "content": "..."}, "model": "..."}
    """
    family = piece.manifest.get("model_family", "openai")

    plan_part     = find_part(assistant_message.parts, "plan")
    evidence_part = find_part(assistant_message.parts, "evidence")
    tool_part     = find_part(assistant_message.parts, "tool_call")

    import json
    plan_xml     = f"<bago:plan>{json.dumps(plan_part, ensure_ascii=False)}</bago:plan>"     if plan_part else ""
    evidence_xml = f"<bago:evidence>{json.dumps(evidence_part, ensure_ascii=False)}</bago:evidence>" if evidence_part else ""
    visible_text = "I will run a scan."
    full_text = f"{visible_text} {plan_xml} {evidence_xml}".strip()

    if family == "openai":
        msg: dict[str, Any] = {"role": "assistant", "content": full_text}
        if tool_part:
            msg["tool_calls"] = [{
                "id":       "call_scan_0",
                "type":     "function",
                "function": {
                    "name":      tool_part.get("name", ""),
                    "arguments": json.dumps(tool_part.get("args", {}), ensure_ascii=False),
                },
            }]
        return {"choices": [{"message": msg, "index": 0}], "model": piece.manifest.get("model_id", "gpt-4o")}

    if family == "anthropic":
        content: list[dict[str, Any]] = [{"type": "text", "text": full_text}]
        if tool_part:
            content.append({
                "type":  "tool_use",
                "id":    "toolu_scan",
                "name":  tool_part.get("name", ""),
                "input": tool_part.get("args", {}),
            })
        return {"content": content, "model": piece.manifest.get("model_id", "claude-3-5-sonnet")}

    # ollama
    text = full_text
    if tool_part:
        text += f' <bago:tool_call>{json.dumps({"name": tool_part.get("name", ""), "args": tool_part.get("args", {})}, ensure_ascii=False)}</bago:tool_call>'
    return {
        "model":            piece.manifest.get("model_id", "llama3.2"),
        "message":          {"role": "assistant", "content": text},
        "eval_count":       42,
        "prompt_eval_count": 17,
        "total_duration":   1_234_567,
    }

#!/usr/bin/env python3
"""FASE 12.8 -- Evidence Gate per translation.

A wrapper that, given a translator piece, runs:
  1. encode(BAGO IR)            -> provider request
  2. callable(provider request) -> provider response  (real HTTP or fake)
  3. decode(provider response)  -> BAGO IR

and records the mandatory FASE 12.8 evidence fields into the evidence ledger:
  - request_hash
  - response_hash
  - tokens_in / tokens_out (best-effort from the provider payload)
  - latency_ms
  - piece_id

The actual call is pluggable: pass a `caller` callable that performs the HTTP
request. The default is a fake caller that returns a sample response produced
by `bago_core.translators.bootstrap._build_sample_response`.

The evidence entry is appended to the JSONL ledger on disk via
`bago_core.evidence_bundle` when available, or written to a fallback path
under `<state_dir>/evidence/translator.jsonl` otherwise.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from bago_core.translators import get_translator, bootstrap_path  # type: ignore
from bago_core.node_control_store import jsonl_append, now  # type: ignore

_EVIDENCE_TYPE = "translator_call"
_LEDGER_RELATIVE = "evidence/translator.jsonl"


def _default_caller(piece, request: dict[str, Any], assistant_message, find_part):
    """Build a fake provider response so the evidence gate can be exercised
    without a real HTTP roundtrip. This is the same builder used by the smoke
    test in `bago_core.translators.bootstrap._build_sample_response`."""
    from bago_core.translators import bootstrap as _bs  # type: ignore
    return _bs._build_sample_response(piece, assistant_message, find_part)


def _extract_tokens(response: Any) -> tuple[int, int]:
    """Best-effort token extraction from a provider response payload."""
    if not isinstance(response, dict):
        return (0, 0)
    usage = response.get("usage")
    if isinstance(usage, dict):
        return (int(usage.get("prompt_tokens", 0) or 0),
                int(usage.get("completion_tokens", 0) or 0))
    out = response.get("eval_count") or 0
    inp = response.get("prompt_eval_count") or 0
    try:
        return (int(inp), int(out))
    except Exception:
        return (0, 0)


def call_with_evidence(
    piece_id: str,
    conversation,
    caller: Optional[Callable[[Any, dict[str, Any]], Any]] = None,
    *,
    paths=None,
    base_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Run encode -> caller -> decode and write evidence.

    Args:
        piece_id:        translator piece id (e.g. "translator.openai.gpt-4o")
        conversation:    IRConversation instance
        caller:          optional callable(provider_piece, request_dict) -> response
                         (defaults to a fake caller for testing)
        paths:           optional RegistryPaths (auto-derived if None)
        base_path:       optional BAGO root (used to derive paths if paths is None)

    Returns:
        dict with: ok, piece_id, evidence (the ledger entry), decoded_messages, request_hash, response_hash
    """
    bootstrap_path()
    from protocol import hash_payload  # type: ignore  # noqa: E402

    piece = get_translator(piece_id)
    if piece is None:
        return {"ok": False, "piece_id": piece_id, "error": "piece not found"}

    def _find_part(parts, type_name):
        for p in parts:
            if p.get("type") == type_name:
                return p
        return None

    assistant_msg = next(
        (m for m in conversation.messages if getattr(m, "role", "") == "assistant"),
        (conversation.messages[0] if conversation.messages else None),
    )

    t0 = time.perf_counter()
    request = piece.encode.encode(conversation)
    if caller is None:
        response = _default_caller(piece, request, assistant_msg, _find_part)
    else:
        response = caller(piece, request)
    decoded = piece.decode.decode(response)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    tokens_in, tokens_out = _extract_tokens(response)
    request_hash = hash_payload(request)
    response_hash = hash_payload(response)

    # Derive ledger path. The default lives under <base>/.bago/state/node_control/evidence/translator.jsonl
    # so it co-locates with the rest of the node_control state.
    if base_path is None:
        base_path = Path.cwd()
    if paths is None:
        ledger_dir = Path(base_path) / ".bago" / "state" / "node_control" / "evidence"
    else:
        ledger_dir = Path(paths.root) / "evidence"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger = ledger_dir / "translator.jsonl"

    evidence_entry = {
        "evidence_id":   f"tra-{request_hash[7:13]}-{response_hash[7:13]}",
        "type":          _EVIDENCE_TYPE,
        "piece_id":      piece_id,
        "model_family":  piece.manifest.get("model_family", ""),
        "model_id":      piece.manifest.get("model_id", ""),
        "request_hash":  request_hash,
        "response_hash": response_hash,
        "tokens_in":     tokens_in,
        "tokens_out":    tokens_out,
        "latency_ms":    latency_ms,
        "messages_in":   len(conversation.messages),
        "messages_out":  len(getattr(decoded, "messages", []) or []),
        "timestamp":     now(),
    }
    jsonl_append(ledger, evidence_entry)

    return {
        "ok":              True,
        "piece_id":        piece_id,
        "evidence":        evidence_entry,
        "decoded_messages": [m.to_dict() if hasattr(m, "to_dict") else m
                             for m in getattr(decoded, "messages", [])],
        "request_hash":    request_hash,
        "response_hash":   response_hash,
    }


def evidence_path(paths=None, base_path: Optional[Path] = None) -> Path:
    """Public helper so the CLI dispatch and tests can point at the same ledger."""
    if base_path is None:
        base_path = Path.cwd()
    if paths is None:
        return Path(base_path) / ".bago" / "state" / "node_control" / "evidence" / "translator.jsonl"
    return Path(paths.root) / "evidence" / "translator.jsonl"


def last_evidence(piece_id: str, paths=None, base_path: Optional[Path] = None, limit: int = 1) -> list[dict[str, Any]]:
    """Tail the ledger and return the most recent entries for `piece_id`."""
    ledger = evidence_path(paths=paths, base_path=base_path)
    if not ledger.exists():
        return []
    matches: list[dict[str, Any]] = []
    with ledger.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("piece_id") == piece_id:
                matches.append(rec)
    return matches[-limit:]

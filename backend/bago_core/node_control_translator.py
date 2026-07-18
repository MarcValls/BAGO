#!/usr/bin/env python3
"""CLI dispatch for the `bago node translator` command group (FASE 12).

Layer: dispatch. Convierte argparse -> store calls -> render -> print.
NO contiene I/O directo ni logica de negocio (R8).
"""
from __future__ import annotations

import json
import sys
from typing import Any

from bago_core.node_control_render import (
    render_translator_list,
    render_translator_manifest,
    render_translator_validation,
    render_translator_map,
)

def _list(payload: list[dict[str, Any]], json_mode: bool) -> int:
    if json_mode:
        sys.stdout.write(json.dumps({"count": len(payload), "translators": payload}, ensure_ascii=False) + "\n")
        return 0
    sys.stdout.write(render_translator_list(payload) + "\n")
    return 0

def _show(piece: Any, json_mode: bool) -> int:
    manifest = piece.manifest
    if json_mode:
        sys.stdout.write(json.dumps(manifest, ensure_ascii=False) + "\n")
        return 0
    sys.stdout.write(render_translator_manifest(manifest) + "\n")
    return 0

def _validate(results: list[dict[str, Any]], json_mode: bool) -> int:
    ok = all(r["ok"] for r in results)
    if json_mode:
        sys.stdout.write(json.dumps({"ok": ok, "results": results}, ensure_ascii=False) + "\n")
        return 0 if ok else 1
    sys.stdout.write(render_translator_validation(results) + "\n")
    return 0 if ok else 1

def _map(piece: Any, json_mode: bool) -> int:
    """Preview the encoded request of a sample IR for the given piece."""
    from bago_core.translators import _ensure_ir_types_path  # type: ignore
    _ensure_ir_types_path()
    from ir_types import (  # type: ignore  # noqa: E402  (path injection)
        IRConversation, IRMessage, ROLE_SYSTEM, ROLE_USER,
    )
    ir_in = IRConversation(
        messages=[
            IRMessage(id="m1", role=ROLE_SYSTEM, parts=[{"type": "text", "text": "Eres BAGO."}]),
            IRMessage(id="m2", role=ROLE_USER, parts=[{"type": "text", "text": "Saluda."}]),
        ],
        model_hint=piece.manifest.get("model_id", ""),
    )
    try:
        request = piece.encode.encode(ir_in)
    except Exception as exc:
        sys.stderr.write(f"encode error: {exc!r}\n")
        return 1
    if json_mode:
        sys.stdout.write(json.dumps(request, ensure_ascii=False) + "\n")
        return 0
    sys.stdout.write(render_translator_map(piece.manifest, request) + "\n")
    return 0

def run_translator(args: Any) -> int:
    """Dispatch `bago node translator <subcmd>`.

    Layer: dispatch. Parser shape lives in
    :func:`bago_core.parsers_sections.add_translator_parser`.
    """
    from bago_core.translators import (  # local import keeps facade slim
        get_translator,
        list_translators,
        smoke_test_piece,
    )

    sub_cmd = getattr(args, "translator_command", None) or "list"
    json_mode = bool(getattr(args, "json", False))

    if sub_cmd == "list":
        return _list(list_translators(), json_mode)

    if sub_cmd == "show":
        piece = get_translator(args.piece_id)
        if piece is None:
            sys.stderr.write(f"Pieza traductora '{args.piece_id}' no encontrada.\n")
            return 2
        return _show(piece, json_mode)

    if sub_cmd == "validate":
        if args.piece_id:
            results = [smoke_test_piece(args.piece_id)]
        else:
            results = [
                smoke_test_piece(p["piece_id"])
                for p in list_translators()
                if p["piece_id"] != "translator.shared.base"
            ]
        return _validate(results, json_mode)

    if sub_cmd == "map":
        piece = get_translator(args.piece_id)
        if piece is None:
            sys.stderr.write(f"Pieza traductora '{args.piece_id}' no encontrada.\n")
            return 2
        return _map(piece, json_mode)

    if sub_cmd == "call":
        return _call(args, json_mode)

    if sub_cmd == "audit":
        return _audit(args, json_mode)
    return 1


def _call(args: Any, json_mode: bool) -> int:
    """FASE 12.8: run encode -> caller (default fake) -> decode and write evidence."""
    from bago_core.translators.evidence_gate import call_with_evidence  # type: ignore
    from bago_core.node_control_store import jsonl_append  # type: ignore
    from bago_core.translators import _ensure_ir_types_path  # type: ignore
    _ensure_ir_types_path()
    from ir_types import IRConversation, IRMessage  # type: ignore  # noqa: E402

    ir_in = IRConversation(
        messages=[
            IRMessage(id="m1", role="user", parts=[
                {"type": "text", "text": getattr(args, "prompt", "BAGO smoke test.")},
            ]),
        ],
        model_hint="",
    )
    result = call_with_evidence(args.piece_id, ir_in, base_path=getattr(args, "base_path", None))
    if json_mode:
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        return 0 if result.get("ok") else 1
    if not result.get("ok"):
        sys.stderr.write(f"translator call failed: {result.get('error')}\n")
        return 1
    ev = result["evidence"]
    sys.stdout.write(
        f"piece={ev['piece_id']} family={ev['model_family']} model={ev['model_id']}\n"
        f"  request_hash ={ev['request_hash']}\n"
        f"  response_hash={ev['response_hash']}\n"
        f"  tokens_in/out={ev['tokens_in']}/{ev['tokens_out']}\n"
        f"  latency_ms   ={ev['latency_ms']}\n"
        f"  evidence_id  ={ev['evidence_id']}\n"
    )
    return 0


def _audit(args: Any, json_mode: bool) -> int:
    """Tail the evidence ledger for a piece (FASE 12.8 audit trail)."""
    from bago_core.translators.evidence_gate import last_evidence  # type: ignore
    base_path = getattr(args, "base_path", None)
    limit = int(getattr(args, "limit", 5) or 5)
    entries = last_evidence(args.piece_id, base_path=base_path, limit=limit)
    if json_mode:
        sys.stdout.write(json.dumps({"piece_id": args.piece_id, "entries": entries}, ensure_ascii=False) + "\n")
        return 0
    if not entries:
        sys.stdout.write(f"no evidence yet for {args.piece_id}\n")
        return 0
    for ev in entries:
        sys.stdout.write(
            f"{ev.get('timestamp','?')}  {ev.get('evidence_id','?')}  "
            f"req={ev.get('request_hash','?')}  resp={ev.get('response_hash','?')}  "
            f"tokens_in/out={ev.get('tokens_in',0)}/{ev.get('tokens_out',0)}  "
            f"latency_ms={ev.get('latency_ms',0)}\n"
        )
    return 0

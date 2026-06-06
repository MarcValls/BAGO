#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "BAGO NODE CONTROL",
        f"base path   : {summary['base_path']}",
        f"store root  : {summary['store_root']}",
        f"installs    : {summary['installations']}",
        f"pieces      : {summary['pieces']}",
        f"connectors  : {summary['connectors']}",
        f"compat rows : {summary['compatibility_rows']}",
        f"evidence    : {summary['evidence_file']}",
    ]
    mode_bits = ", ".join(f"{k}={v}" for k, v in summary["modes"].items() if v)
    if mode_bits:
        lines.append(f"modes       : {mode_bits}")
    return "\n".join(lines)

def render_pieces(payload: dict[str, Any]) -> str:
    lines = [
        "BAGO PIECES",
        f"count       : {payload['count']}",
    ]
    for piece in payload["pieces"]:
        lines.append(
            f"- {piece['piece_id']} [{piece['type']}] {piece['version']} "
            f"({piece['scope']}) -> {piece['materialized_path']}"
        )
    return "\n".join(lines)

def render_connectors(payload: dict[str, Any]) -> str:
    lines = [
        "BAGO CONNECTORS",
        f"count       : {payload['count']}",
    ]
    for connector in payload["connectors"]:
        policy = connector["policy"]
        lines.append(
            f"- {connector['connector_id']} {connector['installation_id']} -> {connector['piece_id']} "
            f"[{connector['mode']}] exec={policy['can_execute']} mod={policy['can_modify']}"
        )
    return "\n".join(lines)

def render_matrix(payload: dict[str, Any]) -> str:
    installs = payload["installations"]
    lines = [
        "BAGO MATRIX",
        "piece / installation",
    ]
    header = ["piece_id"] + [item["installation_id"] for item in installs]
    lines.append(" | ".join(header))
    for row in payload["rows"]:
        cells = [row["piece_id"]]
        for cell in row["cells"]:
            cells.append(cell["mode"])
        lines.append(" | ".join(cells))
    return "\n".join(lines)

def render_translator_list(translators: list[dict[str, Any]]) -> str:
    lines = [
        "BAGO TRANSLATOR PIECES",
        f"count       : {len(translators)}",
    ]
    for t in translators:
        lines.append(f"- {t['piece_id']} [{t['model_family']}] {t['model_id']} v{t['version']}")
        lines.append(f"     {t['store_path']}")
    return "\n".join(lines)

def render_translator_manifest(manifest: dict[str, Any]) -> str:
    lines = [
        f"PIECE: {manifest.get('piece_id')}",
        f"family: {manifest.get('model_family')}",
        f"model : {manifest.get('model_id')}",
        f"version: {manifest.get('version')}",
    ]
    sup = manifest.get("supports", {})
    for k, v in sup.items():
        lines.append(f"  supports.{k:22s} = {v}")
    safety = manifest.get("safety", {})
    if safety:
        lines.append("safety:")
        for k, v in safety.items():
            lines.append(f"  {k:14s} = {v}")
    return "\n".join(lines)

def render_translator_validation(results: list[dict[str, Any]]) -> str:
    lines = []
    for r in results:
        status_str = "OK  " if r["ok"] else "FAIL"
        lines.append(f"  [{status_str}] {r['piece_id']}")
        if not r["ok"]:
            for m in r.get("mismatches", []):
                lines.append(f"        - {m}")
            if r.get("error"):
                lines.append(f"        error: {r['error']}")
    return "\n".join(lines)

def render_translator_map(manifest: dict[str, Any], request: dict[str, Any]) -> str:
    lines = [
        f"PIECE: {manifest.get('piece_id')}",
        f"family: {manifest.get('model_family')}",
        "REQUEST (preview):",
    ]
    for k in sorted(request.keys()):
        v = request[k]
        if isinstance(v, list) and len(v) > 3:
            lines.append(f"  {k}: [{len(v)} items, e.g. {v[0]}]")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)

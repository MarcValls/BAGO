#!/usr/bin/env python3
"""Render the versioned BAGO mind map from its structured JSON source."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs/architecture/bago_mind_map.data.json"
HTML_PATH = ROOT / "docs/architecture/bago_mind_map.html"
DATA_START = "/* BAGO_MAP_DATA_START */"
DATA_END = "/* BAGO_MAP_DATA_END */"


def _load_data() -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(data.get("center"), dict) or not isinstance(data.get("branches"), list):
        raise ValueError("map data must contain a center object and branches array")
    branch_ids = [branch.get("id") for branch in data["branches"]]
    if any(not branch_id for branch_id in branch_ids) or len(set(branch_ids)) != len(branch_ids):
        raise ValueError("branch ids must be present and unique")
    if any(not isinstance(branch.get("children"), list) for branch in data["branches"]):
        raise ValueError("each branch must contain a children array")
    return data


def _render(data: dict) -> str:
    html = HTML_PATH.read_text(encoding="utf-8")
    if html.count(DATA_START) != 1 or html.count(DATA_END) != 1:
        raise ValueError("HTML must contain exactly one pair of BAGO map data markers")
    start = html.index(DATA_START) + len(DATA_START)
    end = html.index(DATA_END, start)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    rendered = html[:start] + payload + html[end:]
    _validate_document(rendered)
    return rendered


def _validate_document(html: str) -> None:
    if html.rpartition("</html>")[2].strip():
        raise ValueError("HTML contains content after the closing html element")
    required = (
        "const lines = document.getElementById('lines');",
        "const nodesLayer = document.getElementById('nodes');",
        "let DATA = /* BAGO_MAP_DATA_START */",
        "viewport.addEventListener('pointerdown'",
        "window.addEventListener('pointermove'",
        "window.addEventListener('pointerup'",
        "event.ctrlKey||event.metaKey",
        "viewport.addEventListener('wheel'",
        "function saveDataFile()",
        "document.getElementById('addComment').onclick",
        "id=\"coordinationPanel\"",
        "document.getElementById('coordinationForm').addEventListener('submit'",
        "document.getElementById('exportCoordination').onclick",
        ".node.branch.selected,.node.branch.selected-node{z-index:110!important",
        ".node.child.in-selected-branch{z-index:105!important",
        "#nodes .node.selected-node{\n  z-index:120!important",
    )
    missing = [fragment for fragment in required if fragment not in html]
    if missing:
        raise ValueError("HTML is missing required map bindings or selected-node layering")


def _write_atomically(content: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".bago-mind-map-", dir=HTML_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, HTML_PATH)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the HTML projection is stale")
    args = parser.parse_args()
    try:
        expected = _render(_load_data())
        current = HTML_PATH.read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BAGO mind map: ERROR: {exc}")
        return 2
    if args.check:
        if current != expected:
            print("BAGO mind map is stale; run python scripts/update_bago_mind_map.py")
            return 1
        print("BAGO mind map projection PASS")
        return 0
    _write_atomically(expected)
    print(f"BAGO mind map updated: {HTML_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

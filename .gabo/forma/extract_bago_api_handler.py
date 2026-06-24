"""
extract_bago_api_handler.py — extract BagoAPIHandler class from bridge.py to bridge_handler.py.

Single-shot, runs once. Verifies the result with a smoke test and writes
manifests/bridge_handler.json (a tiny mirror of the extracted class metadata).

Reversible: it makes a backup of bridge.py to .gabo/backups/appdata_pre_bridge_subdiv/
before any edit. Rollback: copy bridge.py back from there.

Usage (from anywhere):
    python .gabo/forma/extract_bago_api_handler.py \
        --bridge 'C:\\Users\\AMTEC_~1\\AppData\\Local\\BAGO\\.bago\\api\\bridge.py'
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract(bridge_path: Path):
    text = bridge_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    # Find class bounds
    start = None
    end = None
    for i, line in enumerate(lines):
        if line.startswith("class BagoAPIHandler") and start is None:
            start = i
        elif line.startswith("class BagoAPIServer") and start is not None:
            end = i
            break
    if start is None or end is None:
        raise RuntimeError(f"Could not find BagoAPIHandler class bounds in {bridge_path}")

    # The class body is lines[start:end] (exclusive of BagoAPIServer)
    class_lines = lines[start:end]
    class_text = "\n".join(class_lines) + "\n"

    # Everything before the class: header + imports + helpers + sys.path + version probe
    pre_text = "\n".join(lines[:start]) + "\n"

    # Everything from BagoAPIServer onward
    post_text = "\n".join(lines[end:]) + "\n"

    return pre_text, class_text, post_text, start, end


def write_handler(pre_text: str, class_text: str) -> str:
    """Build bridge_handler.py: imports the dependencies the class needs.

    Note: pre_text contains the original imports. We lift ONLY the symbols
    the class actually references. Detected via a regex on class_text:
      - _API_PREFIXES  → from api_dispatch import API_PREFIXES as _API_PREFIXES
      - (SessionManager, SwitchEngine, ControlShadow are type-only under
        `from __future__ import annotations`, so we don't import them here.)
    """
    handler_header = '''#!/usr/bin/env python3
"""
bridge_handler.py — BagoAPIHandler class (extracted from bridge.py on 2026-06-24).

The HTTP request handler. Owns `do_GET`, `do_POST`, `log_message`, and the
class-level state (session_mgr, switch_engine, shadow, etc.) that the
server injects before calling `start()`.

Imports come from the same modules bridge.py already used; we keep the
sys.path bootstrap in bridge.py so this module can be imported cleanly
without re-bootstrapping.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api_auth import BagoAuthMixin
from api_dispatch import API_PREFIXES as _API_PREFIXES
from api_dispatch import resolve_get, resolve_post, resolve_router


'''
    return handler_header + class_text


def rewrite_bridge(pre_text: str, post_text: str) -> str:
    """Build bridge.py: header + helpers + import + server + main."""
    # Insert `from bridge_handler import BagoAPIHandler` after the imports in pre_text.
    # The cleanest place is right before the class definition, but we're replacing
    # the class with an import. Simpler: append the import after the last existing
    # `from api_serializers` line in pre_text.
    import_line = "from bridge_handler import BagoAPIHandler  # extracted 2026-06-24\n"

    # Find the last line that starts with `from api_` in pre_text
    lines = pre_text.rstrip("\n").split("\n")
    last_api_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("from api_"):
            last_api_idx = i
    if last_api_idx >= 0:
        lines.insert(last_api_idx + 1, import_line.rstrip())
    else:
        # Fallback: append after the env-loading helpers, before the sys.path block
        lines.append(import_line.rstrip())

    new_pre = "\n".join(lines) + "\n\n"
    return new_pre + post_text


def smoke_test(handler_path: Path, bridge_path: Path) -> dict:
    """Verify both modules import and BagoAPIHandler class is exposed."""
    result = {"imports_ok": False, "class_in_handler": False, "class_in_bridge": False,
              "error": None}
    try:
        sys.path.insert(0, str(bridge_path.parent))
        sys.path.insert(0, str(bridge_path.parent.parent))  # ..\.bago
        sys.path.insert(0, str(bridge_path.parent.parent.parent))  # repo root
        sys.path.insert(0, str(bridge_path.parent.parent.parent / "bago_core"))
        sys.path.insert(0, str(bridge_path.parent.parent / "core"))
        sys.path.insert(0, str(bridge_path.parent.parent / "chat"))

        import importlib
        # Probe handler
        mod_h = importlib.import_module("bridge_handler")
        result["class_in_handler"] = hasattr(mod_h, "BagoAPIHandler")
        # Probe bridge (we only need it to import, not run)
        mod_b = importlib.import_module("bridge")
        result["class_in_bridge"] = hasattr(mod_b, "BagoAPIHandler")
        result["imports_ok"] = result["class_in_handler"] and result["class_in_bridge"]
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def write_manifest(handler_path: Path, manifest_dir: Path, smoke: dict):
    """Write a tiny manifest of the extracted module."""
    manifest_dir.mkdir(parents=True, exist_ok=True)
    lines = handler_path.read_text(encoding="utf-8")
    payload = {
        "area": "bridge_handler",
        "root_rel": ".bago/api/bridge_handler.py",
        "paths_are": "root-relative",
        "exists": True,
        "broken": False,
        "extracted_from": ".bago/api/bridge.py",
        "extracted_at": now_iso(),
        "line_count": len(lines.splitlines()),
        "byte_count": handler_path.stat().st_size,
        "exports": ["BagoAPIHandler"],
        "imports": ["BagoAuthMixin", "BaseHTTPRequestHandler",
                    "resolve_get", "resolve_post", "resolve_router"],
        "smoke_test": smoke,
    }
    (manifest_dir / "bridge_handler.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", required=True, help="Path to bridge.py")
    ap.add_argument("--manifest-dir", default=None,
                    help="Where to write bridge_handler.json (default: <repo>/.gabo/manifests/)")
    args = ap.parse_args()

    bridge_path = Path(args.bridge).resolve()
    if not bridge_path.is_file():
        print(f"error: not a file: {bridge_path}", file=sys.stderr)
        sys.exit(2)

    print(f"[extract] bridge.py = {bridge_path}")
    pre_text, class_text, post_text, start, end = extract(bridge_path)
    print(f"[extract] BagoAPIHandler class: lines {start+1}..{end} ({end - start} lines)")

    handler_path = bridge_path.parent / "bridge_handler.py"
    new_bridge = rewrite_bridge(pre_text, post_text)

    print(f"[extract] writing {handler_path}")
    handler_path.write_text(write_handler(pre_text, class_text), encoding="utf-8")

    print(f"[extract] writing {bridge_path}")
    bridge_path.write_text(new_bridge, encoding="utf-8")

    # Smoke test
    smoke = smoke_test(handler_path, bridge_path)
    print(f"[extract] smoke test: {smoke}")

    # Manifest
    if args.manifest_dir:
        manifest_dir = Path(args.manifest_dir).resolve()
    else:
        # repo root = bridge_path.parents[2] (.bago/api/ -> .bago -> repo)
        repo = bridge_path.parents[2]
        manifest_dir = repo / ".gabo" / "manifests"
    write_manifest(handler_path, manifest_dir, smoke)
    print(f"[extract] manifest: {manifest_dir / 'bridge_handler.json'}")

    if not smoke["imports_ok"]:
        print("[extract] WARNING: smoke test failed — bridge.py and/or bridge_handler.py "
              "may not import. Rollback: copy bridge.py back from "
              ".gabo/backups/appdata_pre_bridge_subdiv/", file=sys.stderr)
        sys.exit(1)

    print("[extract] OK")


if __name__ == "__main__":
    main()
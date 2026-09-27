#!/usr/bin/env python3
"""Portable honeytoken manager for BAGO 4.x.

Usage:
    python bago_canary.py [--root DIR] deploy --type TYPE
    python bago_canary.py [--root DIR] check
    python bago_canary.py [--root DIR] list
    python bago_canary.py [--root DIR] purge

Exit codes:
    0 = ok
    1 = canary anomaly found
    2 = runtime error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from bago_core.cli_execution import execute_cli_effect
from execution_request import build_execution_request

CANARY_TYPES = ["aws_keys", "openai_api", "github_pat", "telegram_bot", "google_api"]


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def state_dir(root: Path) -> Path:
    return root / ".bago" / "state"


def state_file(root: Path) -> Path:
    return state_dir(root) / "canary_tokens.json"


def canary_dir(root: Path) -> Path:
    return root / ".bago" / "canary"


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return path.is_symlink() or bool(int(getattr(metadata, "st_file_attributes", 0) or 0) & reparse)


def _assert_state_paths(root: Path) -> None:
    for path in (root / ".bago", state_dir(root), state_file(root)):
        if _is_reparse(path):
            raise RuntimeError("Canary state may not traverse a link")


def load_state(root: Path) -> dict[str, object]:
    _assert_state_paths(root)
    path = state_file(root)
    if not path.exists():
        return {"tokens": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _state_digest(root: Path) -> str:
    _assert_state_paths(root)
    path = state_file(root)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def _canonical_artifact_path(root: Path, entry: dict[str, object]) -> Path:
    token_type = str(entry.get("type") or "")
    relative = str(entry.get("path") or "")
    prefix = {
        "aws_keys": "aws", "openai_api": "openai", "github_pat": "github",
        "telegram_bot": "telegram", "google_api": "google",
    }.get(token_type)
    extension = ".txt" if token_type == "telegram_bot" else ".env"
    candidate = Path(relative)
    if (
        prefix is None
        or candidate.is_absolute()
        or candidate.parts[:2] != (".bago", "canary")
        or len(candidate.parts) != 3
        or not candidate.name.startswith(prefix + "_")
        or not candidate.name.endswith(extension)
    ):
        raise RuntimeError("Canary state contains a non-canonical artifact path")
    path = root / candidate
    if any(_is_reparse(item) for item in (root / ".bago", canary_dir(root), path)) or (path.exists() and not path.is_file()):
        raise RuntimeError("Canary artifact is not a regular file")
    return path


def deploy(root: Path, token_type: str) -> list[dict[str, object]]:
    types = CANARY_TYPES if token_type == "all" else [token_type]
    if any(item not in CANARY_TYPES for item in types):
        raise ValueError("unsupported canary type")
    created_at = datetime.now(timezone.utc).isoformat()
    request = build_execution_request(
        effect_id="security.canary.manage", actor_kind="user",
        principal_id="interactive-local-user",
        session_id="canary:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20],
        source_surface="cli.security.canary.deploy",
        target={
            "operation": "deploy", "project_root": str(root), "types": types,
            "stamp": now_stamp(), "created_at": created_at,
            "state_sha256": _state_digest(root),
        },
        arguments={}, scope="workspace",
    )
    result, _authorization = execute_cli_effect(
        request,
        confirmation_text=f"desplegar {', '.join(types)} en {root} (tokens sintéticos)",
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Canary deployment returned no success receipt")
    return list(result.get("entries") or [])


def list_tokens(root: Path) -> list[dict[str, object]]:
    state = load_state(root)
    return list(state.get("tokens", []))


def check(root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for entry in list_tokens(root):
        try:
            path = _canonical_artifact_path(root, entry)
        except RuntimeError:
            findings.append({"type": entry.get("type"), "path": entry.get("path"), "status": "invalid_path"})
            continue
        if not path.exists():
            findings.append({"type": entry["type"], "path": entry["path"], "status": "missing"})
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if sha256_text(content) != entry["sha256"]:
            findings.append({"type": entry["type"], "path": entry["path"], "status": "modified"})
    return findings


def purge(root: Path) -> int:
    entries = list_tokens(root)
    if not entries:
        return 0
    artifacts = []
    for entry in entries:
        path = _canonical_artifact_path(root, entry)
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"
        artifacts.append({"type": entry.get("type"), "path": entry.get("path"), "sha256": digest})
    request = build_execution_request(
        effect_id="security.canary.manage", actor_kind="user",
        principal_id="interactive-local-user",
        session_id="canary:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20],
        source_surface="cli.security.canary.purge",
        target={
            "operation": "purge", "project_root": str(root),
            "state_sha256": _state_digest(root), "artifacts": artifacts,
        },
        arguments={}, scope="workspace",
    )
    result, _authorization = execute_cli_effect(
        request,
        confirmation_text=f"eliminar {len(artifacts)} canary(s) registrados en {root}",
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Canary purge returned no success receipt")
    return int(result.get("removed") or 0)


def print_list(entries: list[dict[str, object]]) -> None:
    if not entries:
        print("No canary tokens deployed")
        return
    print("Canary tokens:")
    for idx, entry in enumerate(entries, start=1):
        print(f"  [{idx}] {entry['type']} {entry['path']} {entry['created_at']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable honeytoken manager")
    parser.add_argument("--root", default="", help="Project root")
    sub = parser.add_subparsers(dest="command")
    deploy_parser = sub.add_parser("deploy", help="Deploy fake credential canaries")
    deploy_parser.add_argument("--type", default="aws_keys", choices=CANARY_TYPES + ["all"])
    sub.add_parser("check", help="Check if canary files were modified or removed")
    sub.add_parser("list", help="List deployed canaries")
    sub.add_parser("purge", help="Delete all deployed canaries")
    args = parser.parse_args(argv)

    root = resolve_root(args.root)
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] invalid root: {root}", file=sys.stderr)
        return 2

    try:
        if args.command == "deploy":
            created = deploy(root, args.type)
            print(f"Deployed {len(created)} canary token(s)")
            print_list(created)
            return 0
        if args.command == "check":
            findings = check(root)
            if findings:
                print("Canary alerts:")
                for item in findings:
                    print(f"  {item['type']} {item['path']} -> {item['status']}")
                return 1
            print("Canary check clean")
            return 0
        if args.command == "purge":
            removed = purge(root)
            print(f"Purged {removed} canary token(s)")
            return 0
        print_list(list_tokens(root))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] bago_canary failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

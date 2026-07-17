#!/usr/bin/env python3
"""Portable honeytoken manager for BAGO 4.x.

Usage:
    python bago_canary.py [--root DIR] deploy --type TYPE
    python bago_canary.py [--root DIR] check
    python bago_canary.py [--root DIR] list
    python bago_canary.py [--root DIR] purge
    python bago_canary.py --test

Exit codes:
    0 = ok
    1 = canary anomaly found
    2 = runtime error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

CANARY_TYPES = ["aws_keys", "openai_api", "github_pat", "telegram_bot", "google_api"]


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def state_dir(root: Path) -> Path:
    path = root / ".bago" / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_file(root: Path) -> Path:
    return state_dir(root) / "canary_tokens.json"


def canary_dir(root: Path) -> Path:
    path = root / ".bago" / "canary"
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state(root: Path) -> dict[str, object]:
    path = state_file(root)
    if not path.exists():
        return {"tokens": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(root: Path, data: dict[str, object]) -> None:
    state_file(root).write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def render_token(token_type: str) -> tuple[str, str]:
    stamp = now_stamp()
    if token_type == "aws_keys":
        aws_access_key = "AKIA" + "FAKE123456789012"
        aws_secret = "fakeAwsSecretKeyValue" + "000000000000000000000000"
        return (f"aws_{stamp}.env", f"AWS_ACCESS_KEY_ID={aws_access_key}\nAWS_SECRET_ACCESS_KEY={aws_secret}\n")  # nosec: test fixture
    if token_type == "openai_api":
        openai_key = "sk-" + "fakeOpenAIToken00000000000000000000"
        return (f"openai_{stamp}.env", f"OPENAI_API_KEY={openai_key}\n")  # nosec: test fixture
    if token_type == "github_pat":
        github_pat = "ghp_" + "FAKEGitHubTokenValue123456789012345678"
        return (f"github_{stamp}.env", f"GITHUB_TOKEN={github_pat}\n")  # nosec: test fixture
    if token_type == "telegram_bot":
        telegram_token = "987654321:" + "FAKETelegramBotTokenValue1234567890abcd"
        return (f"telegram_{stamp}.txt", f"{telegram_token}\n")  # nosec: test fixture
    if token_type == "google_api":
        google_key = "AIza" + "FakeGoogleApiKeyValue000000000000"
        return (f"google_{stamp}.env", f"GOOGLE_API_KEY={google_key}\n")  # nosec: test fixture
    raise ValueError(f"unsupported canary type: {token_type}")


def deploy(root: Path, token_type: str) -> list[dict[str, object]]:
    types = CANARY_TYPES if token_type == "all" else [token_type]
    state = load_state(root)
    tokens = list(state.get("tokens", []))
    created: list[dict[str, object]] = []
    for item_type in types:
        filename, content = render_token(item_type)
        path = canary_dir(root) / filename
        path.write_text(content, encoding="utf-8")
        entry = {
            "type": item_type,
            "path": str(path.relative_to(root)),
            "sha256": sha256_text(content),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "size": len(content.encode("utf-8")),
        }
        tokens.append(entry)
        created.append(entry)
    state["tokens"] = tokens
    save_state(root, state)
    return created


def list_tokens(root: Path) -> list[dict[str, object]]:
    state = load_state(root)
    return list(state.get("tokens", []))


def check(root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for entry in list_tokens(root):
        path = root / entry["path"]
        if not path.exists():
            findings.append({"type": entry["type"], "path": entry["path"], "status": "missing"})
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if sha256_text(content) != entry["sha256"]:
            findings.append({"type": entry["type"], "path": entry["path"], "status": "modified"})
    return findings


def purge(root: Path) -> int:
    removed = 0
    for entry in list_tokens(root):
        path = root / entry["path"]
        if path.exists():
            path.unlink()
            removed += 1
    save_state(root, {"tokens": []})
    canary_path = root / ".bago" / "canary"
    if canary_path.exists() and not any(canary_path.iterdir()):
        shutil.rmtree(canary_path)
    return removed


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
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    sub = parser.add_subparsers(dest="command")
    deploy_parser = sub.add_parser("deploy", help="Deploy fake credential canaries")
    deploy_parser.add_argument("--type", default="aws_keys", choices=CANARY_TYPES + ["all"])
    sub.add_parser("check", help="Check if canary files were modified or removed")
    sub.add_parser("list", help="List deployed canaries")
    sub.add_parser("purge", help="Delete all deployed canaries")
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()

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


def run_self_tests() -> int:
    import tempfile

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        created = deploy(root, "aws_keys")
        record("canary:deploy_one", len(created) == 1, f"count={len(created)}")

        clean = check(root)
        record("canary:check_clean", clean == [], f"findings={len(clean)}")

        all_created = deploy(root, "all")
        record("canary:deploy_all", len(all_created) == len(CANARY_TYPES), f"count={len(all_created)}")

        entries = list_tokens(root)
        record("canary:list_state", len(entries) == len(CANARY_TYPES) + 1, f"count={len(entries)}")

        tamper_path = root / entries[0]["path"]
        tamper_path.write_text("tampered\n", encoding="utf-8")
        dirty = check(root)
        record("canary:tamper_detect", any(item["status"] == "modified" for item in dirty), f"findings={dirty}")

        removed = purge(root)
        record("canary:purge", removed >= 1 and list_tokens(root) == [], f"removed={removed}")

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

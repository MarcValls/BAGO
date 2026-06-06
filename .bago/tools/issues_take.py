#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


_DEFAULT_AGENT = "copilot"


def _usage() -> str:
    return "Usage: issues_take.py [--root PATH] [--dry-run] take [--agent AGENT] [REPO]"


def _default_repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY") or "MarcValls/BAGO"


def _normalize_agent(name: str) -> str:
    cleaned = (name or "").strip().lower().lstrip("@")
    return cleaned or _DEFAULT_AGENT


def _pick_issue(issues: object) -> dict | None:
    if not isinstance(issues, list):
        return None
    for item in issues:
        if not isinstance(item, dict):
            continue
        assignees = item.get("assignees")
        if isinstance(assignees, list) and len(assignees) == 0:
            return item
    for item in issues:
        if isinstance(item, dict):
            return item
    return None


def _assign_next_issue(repo: str, agent: str) -> int:
    if shutil.which("gh") is None:
        print("ERROR: GitHub CLI (gh) no está disponible")
        return 2
    list_cmd = ["gh", "issue", "list", "--repo", repo, "--state", "open", "--limit", "20", "--json", "number,title,assignees"]
    listed = subprocess.run(list_cmd, text=True, capture_output=True)
    if listed.returncode != 0:
        print(listed.stdout + listed.stderr, end="")
        return listed.returncode
    try:
        issues = json.loads(listed.stdout or "[]")
    except json.JSONDecodeError:
        print("ERROR: invalid response from gh issue list")
        return 2
    issue = _pick_issue(issues)
    if not issue:
        print(f"No open issues available in {repo}.")
        return 0
    number = issue.get("number")
    title = issue.get("title") or ""
    edit_cmd = ["gh", "issue", "edit", str(number), "--repo", repo, "--add-assignee", agent]
    edited = subprocess.run(edit_cmd, text=True, capture_output=True)
    if edited.returncode != 0:
        print(edited.stdout + edited.stderr, end="")
        return edited.returncode
    print(f"✓ Issue #{number} assigned to @{agent}: {title}")
    return 0


def main(argv: list[str] | None = None) -> int:
    tokens = list(argv or sys.argv[1:])
    if any(token in {"-h", "--help"} for token in tokens):
        print(_usage())
        return 0

    root = Path.cwd()
    dry_run = False
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token == "--root":
            if idx + 1 >= len(tokens):
                print("ERROR: --root requires a value")
                print(_usage())
                return 2
            root = Path(tokens[idx + 1]).expanduser().resolve()
            del tokens[idx:idx + 2]
            continue
        if token == "--dry-run":
            dry_run = True
            tokens.pop(idx)
            continue
        idx += 1

    if not root.exists():
        print(f"ERROR: root path does not exist: {root}")
        return 2

    if not tokens or tokens[0] != "take":
        print(_usage())
        return 2
    args = tokens[1:]

    repo = ""
    explicit_agent = ""
    idx = 0
    while idx < len(args):
        token = args[idx]
        if token == "--agent":
            if idx + 1 >= len(args):
                print("ERROR: --agent requires a value")
                print(_usage())
                return 2
            explicit_agent = args[idx + 1]
            del args[idx:idx + 2]
            continue
        if token.startswith("-"):
            print(f"ERROR: unknown option {token}")
            print(_usage())
            return 2
        if not repo:
            repo = token
            idx += 1
            continue
        print(f"ERROR: unexpected argument {token}")
        print(_usage())
        return 2

    repo = repo or _default_repo()
    agent = _normalize_agent(explicit_agent)

    print(f"→ taking next issue in {repo} as @{agent}")
    if dry_run:
        print("DRY-RUN: assignment skipped")
        return 0
    return _assign_next_issue(repo, agent)


if __name__ == "__main__":
    raise SystemExit(main())

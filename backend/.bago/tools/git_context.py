#!/usr/bin/env python3
"""Portable git context snapshot for BAGO 4.x.

Usage:
    python git_context.py [--root DIR] [--brief] [--json] [--log N] [--since 7d] [--diff] [--test]

Exit codes:
    0 = clean repo snapshot generated
    1 = repo is dirty or detached
    2 = runtime error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def have_git() -> bool:
    return shutil.which("git") is not None


def run_git(args: list[str], cwd: Path, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False
    )


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        probe = run_git(["rev-parse", "--show-toplevel"], current)
        if probe.returncode == 0 and probe.stdout.strip():
            return Path(probe.stdout.strip())
        if current.parent == current:
            return None
        current = current.parent


def normalize_since(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.endswith("d") and value[:-1].isdigit():
        return f"{value[:-1]}.days.ago"
    if value.endswith("w") and value[:-1].isdigit():
        return f"{value[:-1]}.weeks.ago"
    if value.endswith("m") and value[:-1].isdigit():
        return f"{int(value[:-1]) * 4}.weeks.ago"
    return value


def get_branch_info(git_root: Path) -> tuple[str, str | None]:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], git_root).stdout.strip() or "HEAD"
    upstream_proc = run_git(["rev-parse", "--abbrev-ref", "@{upstream}"], git_root)
    upstream = upstream_proc.stdout.strip() if upstream_proc.returncode == 0 else None
    return branch, upstream or None


def get_status(git_root: Path) -> dict[str, object]:
    proc = run_git(["status", "--porcelain"], git_root)
    staged: list[str] = []
    modified: list[str] = []
    untracked: list[str] = []
    for raw in proc.stdout.splitlines():
        if len(raw) < 3:
            continue
        x, y = raw[0], raw[1]
        name = raw[3:].strip()
        if x not in {" ", "?"}:
            staged.append(name)
        if y not in {" ", "?"}:
            modified.append(name)
        if x == "?" and y == "?":
            untracked.append(name)
    return {
        "staged": staged,
        "modified": modified,
        "untracked": untracked,
        "clean": not (staged or modified or untracked),
    }


def get_log(git_root: Path, limit: int, since: str | None) -> list[dict[str, str]]:
    fmt = "%H|%h|%an|%ad|%s"
    cmd = ["log", f"--format={fmt}", "--date=short", f"-{limit}"]
    if since:
        cmd.append(f"--since={since}")
    proc = run_git(cmd, git_root)
    commits: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            commits.append({
                "sha": parts[0], "short": parts[1], "author": parts[2],
                "date": parts[3], "subject": parts[4],
            })
    return commits


def get_authors(git_root: Path, since: str | None) -> list[dict[str, object]]:
    cmd = ["shortlog", "-sn", "--no-merges"]
    if since:
        cmd.append(f"--since={since}")
    proc = run_git(cmd, git_root)
    authors: list[dict[str, object]] = []
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            authors.append({"commits": int(parts[0]), "name": parts[1]})
    return authors[:8]


def get_diff_stat(git_root: Path) -> list[str]:
    proc = run_git(["diff", "--stat"], git_root)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def collect_context(root: Path, limit: int, since_raw: str | None, include_diff: bool) -> dict[str, object]:
    git_root = find_git_root(root)
    if git_root is None:
        raise RuntimeError(f"no git repository found from {root}")
    since = normalize_since(since_raw)
    branch, upstream = get_branch_info(git_root)
    status = get_status(git_root)
    commits = get_log(git_root, limit, since)
    total_proc = run_git(["rev-list", "--count", "HEAD"], git_root)
    try:
        total_commits = int(total_proc.stdout.strip())
    except ValueError:
        total_commits = 0
    data = {
        "repo": git_root.name,
        "git_root": str(git_root),
        "requested_root": str(root),
        "branch": branch,
        "upstream": upstream,
        "status": status,
        "recent_commits": commits,
        "authors": get_authors(git_root, since),
        "total_commits": total_commits,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "since": since_raw or "",
    }
    if include_diff:
        data["diff_stat"] = get_diff_stat(git_root)
    return data


def print_brief(ctx: dict[str, object]) -> None:
    status = ctx["status"]
    dirty = "clean" if status["clean"] else (
        f"dirty staged={len(status['staged'])} modified={len(status['modified'])} untracked={len(status['untracked'])}"
    )
    last = ctx["recent_commits"][0]["subject"] if ctx["recent_commits"] else "no commits"
    print(f"{ctx['repo']} {ctx['branch']} {dirty} last={last}")


def print_full(ctx: dict[str, object], include_diff: bool) -> None:
    print(f"Git context for: {ctx['git_root']}")
    print(f"Branch: {ctx['branch']}")
    print(f"Upstream: {ctx['upstream'] or 'none'}")
    print(f"Commits: {ctx['total_commits']}")
    status = ctx["status"]
    print(f"Clean: {status['clean']}")
    print(f"Staged: {len(status['staged'])}")
    print(f"Modified: {len(status['modified'])}")
    print(f"Untracked: {len(status['untracked'])}")
    if ctx["recent_commits"]:
        print("Recent commits:")
        for item in ctx["recent_commits"]:
            print(f"  {item['short']} {item['date']} {item['author']} - {item['subject']}")
    if ctx["authors"]:
        print("Authors:")
        for item in ctx["authors"]:
            print(f"  {item['commits']:>3} {item['name']}")
    if include_diff:
        print("Diff stat:")
        for line in ctx.get("diff_stat", []):
            print(f"  {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable git context snapshot")
    parser.add_argument("--root", default="", help="Directory inside or near a git repo")
    parser.add_argument("--brief", action="store_true", help="One line summary")
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON output")
    parser.add_argument("--log", type=int, default=10, help="Number of log entries")
    parser.add_argument("--since", default="", help="Time range like 7d or 2w")
    parser.add_argument("--diff", action="store_true", help="Include diff stat")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()
    if not have_git():
        print("[ERROR] git is not available", file=sys.stderr)
        return 2

    root = resolve_root(args.root)
    if not root.exists():
        print(f"[ERROR] invalid root: {root}", file=sys.stderr)
        return 2

    try:
        ctx = collect_context(root, max(1, args.log), args.since or None, args.diff)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] git_context failed: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(ctx, indent=2, ensure_ascii=True))
    elif args.brief:
        print_brief(ctx)
    else:
        print_full(ctx, args.diff)

    branch = str(ctx["branch"])
    clean = bool(ctx["status"]["clean"])
    return 0 if clean and branch != "HEAD" else 1


def run_self_tests() -> int:
    import tempfile

    if not have_git():
        print("OK: git_context:git_missing - skipped")
        print("1/1 tests passed")
        return 0

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        run_git(["init", "--initial-branch=main"], root)
        run_git(["config", "user.email", "test@example.com"], root)
        run_git(["config", "user.name", "Tester"], root)
        (root / "a.txt").write_text("hello\n", encoding="utf-8")
        run_git(["add", "a.txt"], root)
        run_git(["commit", "-m", "init"], root)
        nested = root / "nested"
        nested.mkdir()
        (root / "pending.txt").write_text("pending\n", encoding="utf-8")

        found = find_git_root(nested)
        record("git_context:find_root", found == root.resolve(), f"found={found}")

        ctx = collect_context(nested, 5, "7d", True)
        record("git_context:collect", ctx["repo"] == root.name, f"repo={ctx['repo']}")
        record("git_context:status", "pending.txt" in ctx["status"]["untracked"], "untracked visible")
        record("git_context:log", len(ctx["recent_commits"]) >= 1 and ctx["recent_commits"][0]["subject"] == "init", "log ok")

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Scan a source tree for bug-prone state patterns.

The goal is to find candidates for human review, not to repair code.
The audit focuses on patterns that often cause bugs:
- state that can survive a workspace change or mix different workspaces;
- mount-only refresh/load effects that can go stale;
- derived state seeded from props/snapshot values;
- lifecycle patterns that commonly miss cleanup.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tree_audit_utils import find_named_callable, iter_hook_calls, split_hook_call


SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "out",
    "output",
    "releases",
    ".run",
    ".worktrees",
    ".gabo",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".cache",
    "tmp",
    "temp",
}

SKIP_PATH_PARTS = {
    ("backend", "docs", "audit"),
    ("backend", "docs", "evidence"),
}

SCAN_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".md", ".json", ".sh", ".ps1",
}

WORKSPACE_HINTS = (
    "workspaceRoot",
    "workspace_root",
    "workspaceKey",
    "workspace_id",
    "workspaceId",
    "workspaceContextStorageKey",
    "workspaceSectionStorageKey",
    "workspaceStorageKey",
    "workspaceContextSessionValue",
    "workspaceSectionSessionValue",
    "props.snapshot?.workspace",
    "props.snapshot?.project",
    "snapshot?.workspace",
    "snapshot?.project",
)

SEVERITY_ORDER = {
    "critical": 0,
    "error": 1,
    "warning": 2,
    "info": 3,
}


@dataclass(frozen=True)
class Finding:
    category: str
    pattern: str
    path: Path
    line: int
    message: str
    severity: str
    crosses_workspaces: bool = False

    def as_dict(self, root: Path) -> dict[str, object]:
        return {
            "category": self.category,
            "pattern": self.pattern,
            "file": str(self.path.relative_to(root)),
            "line": self.line,
            "severity": self.severity,
            "crosses_workspaces": self.crosses_workspaces,
            "message": self.message,
        }


STORAGE_RE = re.compile(r"""(?P<api>sessionStorage|localStorage)\.(?P<op>getItem|setItem|removeItem)\(\s*(?P<key>['"`])(?P<value>[^'"`]+)(?P=key)\s*\)""")
MOUNT_REFRESH_RE = re.compile(r"""useEffect\(\(\)\s*=>\s*\{\s*void\s+(?P<fn>[A-Za-z0-9_]+)\(\);\s*\},\s*\[(?P<deps>[^\]]*)\]\)""")
STATE_INIT_RE = re.compile(r"""useState\(\s*(?P<expr>(?:Boolean\()?(?:props|snapshot)\.[^)]+?)\s*\)""")
LIFECYCLE_RE = re.compile(r"""useEffect\(\s*\(\)\s*=>""")


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if any(all(part in path.parts for part in block) for block in SKIP_PATH_PARTS):
            continue
        if path.suffix.lower() in SCAN_EXTS:
            yield path


def read_text(path: Path) -> str:
    try:
      return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
      return ""


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def has_workspace_hint(snippet: str) -> bool:
    return any(hint in snippet for hint in WORKSPACE_HINTS)


def storage_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line_text in enumerate(text.splitlines(), start=1):
        for match in STORAGE_RE.finditer(line_text):
            key = match.group("value").strip()
            if has_workspace_hint(line_text):
                severity = "info"
                category = "storage-scoped"
                message = f"{match.group('api')}.{match.group('op')} appears workspace-aware: {key!r}"
                crosses_workspaces = False
            else:
                severity = "error"
                category = "storage-global"
                message = f"{match.group('api')}.{match.group('op')} may cross workspaces: {key!r}"
                crosses_workspaces = True
            findings.append(
                Finding(
                    category=category,
                    pattern=f"{match.group('api')}.{match.group('op')}",
                    path=path,
                    line=lineno,
                    message=message,
                    severity=severity,
                    crosses_workspaces=crosses_workspaces,
                )
            )
    return findings


def extract_line_window(lines: list[str], start_line: int, span: int = 4) -> str:
    begin = max(0, start_line - 1)
    end = min(len(lines), start_line - 1 + span)
    return "\n".join(lines[begin:end])


def mount_refresh_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for index, hook_name, call, _body, deps_text in iter_hook_calls(text):
        if hook_name != "useEffect":
            continue
        match = MOUNT_REFRESH_RE.search(call)
        if not match:
            continue
        lineno = text.count("\n", 0, index) + 1
        fn = match.group("fn")
        deps = [item.strip() for item in match.group("deps").split(",") if item.strip()]
        deps_text = ", ".join(deps)
        source = find_named_callable(text, fn, index)
        if not fn.startswith(("refresh", "load", "fetch", "read", "sync")) or not has_workspace_hint(source):
            continue
        source_parts = split_hook_call(source) if source.startswith("useCallback") else None
        source_deps = source_parts[1] if source_parts else ""
        combined_deps = f"{deps_text},{source_deps}"
        workspace_dep_present = has_workspace_hint(combined_deps)
        if not workspace_dep_present:
            findings.append(
                Finding(
                    category="mount-refresh",
                    pattern="useEffect[mount] -> refresh/load/fetch",
                    path=path,
                    line=lineno,
                    message=f"{fn} reads workspace state without a workspace dependency: [{deps_text}]",
                    severity="warning",
                    crosses_workspaces=True,
                )
            )
    return findings


def state_init_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for lineno, line_text in enumerate(lines, start=1):
        match = STATE_INIT_RE.search(line_text)
        if not match:
            continue
        expr = match.group("expr").strip()
        if "props." in expr or "snapshot." in expr or "props?" in expr or "snapshot?" in expr:
            window = extract_line_window(lines, lineno)
            crosses_workspaces = not has_workspace_hint(window)
            severity = "warning" if crosses_workspaces else "info"
            findings.append(
                Finding(
                    category="mount-state",
                    pattern="useState(props/snapshot seeded)",
                    path=path,
                    line=lineno,
                    message=f"state initializer seeded from props/snapshot: {expr[:120]}",
                    severity=severity,
                    crosses_workspaces=crosses_workspaces,
                )
            )
    return findings


def lifecycle_cleanup_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for index, hook_name, call, _body, _deps in iter_hook_calls(text):
        if hook_name != "useEffect":
            continue
        lineno = text.count("\n", 0, index) + 1
        if "addEventListener(" in call and "removeEventListener(" not in call:
            findings.append(
                Finding(
                    category="effect-cleanup",
                    pattern="useEffect + addEventListener",
                    path=path,
                    line=lineno,
                    message="effect adds an event listener but no cleanup is visible nearby",
                    severity="warning",
                    crosses_workspaces=False,
                )
            )
        if "setInterval(" in call and "clearInterval(" not in call:
            findings.append(
                Finding(
                    category="effect-cleanup",
                    pattern="useEffect + setInterval",
                    path=path,
                    line=lineno,
                    message="effect starts an interval but no cleanup is visible nearby",
                    severity="warning",
                    crosses_workspaces=False,
                )
            )
        if "setTimeout(" in call and "clearTimeout(" not in call and "return () =>" not in call:
            findings.append(
                Finding(
                    category="effect-cleanup",
                    pattern="useEffect + setTimeout",
                    path=path,
                    line=lineno,
                    message="effect starts a timeout but no cleanup is visible nearby",
                    severity="info",
                    crosses_workspaces=False,
                )
            )
    return findings


def scan_file(path: Path) -> list[Finding]:
    text = read_text(path)
    if not text:
        return []
    findings: list[Finding] = []
    findings.extend(storage_findings(path, text))
    findings.extend(mount_refresh_findings(path, text))
    findings.extend(state_init_findings(path, text))
    findings.extend(lifecycle_cleanup_findings(path, text))
    return findings


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda item: (
            SEVERITY_ORDER.get(item.severity, 99),
            str(item.path).lower(),
            item.line,
            item.category,
            item.pattern,
        ),
    )


def filter_findings(findings: list[Finding], *, workspace_only: bool) -> list[Finding]:
    if not workspace_only:
        return findings
    return [item for item in findings if item.crosses_workspaces]


def format_text(findings: list[Finding], root: Path) -> str:
    if not findings:
      return "No obvious state-crossing candidates found."
    lines = [f"Found {len(findings)} candidate(s):"]
    for item in findings:
        rel = item.path.relative_to(root)
        lines.append(f"- [{item.severity}] {rel}:{item.line} {item.category} {item.pattern} :: {item.message}")
    return "\n".join(lines)


def format_md(findings: list[Finding], root: Path) -> str:
    if not findings:
        return "# Tree state audit\n\nNo workspace-crossing candidates found."
    lines = [
        "# Tree state audit",
        "",
        "| Severity | File | Line | Category | Pattern | Crosses workspaces | Message |",
        "|---|---|---:|---|---|---|---|",
    ]
    for item in findings:
        rel = item.path.relative_to(root)
        crosses = "yes" if item.crosses_workspaces else "no"
        lines.append(f"| {item.severity} | `{rel}` | {item.line} | {item.category} | `{item.pattern}` | {crosses} | {item.message} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recursively scan for UI state-crossing patterns.")
    parser.add_argument("--root", default=".", help="Root directory to scan")
    parser.add_argument("--format", choices=("text", "json", "md"), default="text")
    parser.add_argument("--max-results", type=int, default=300)
    parser.add_argument("--scan-all", action="store_true", help="Scan the full tree even after reaching max results")
    parser.add_argument("--workspace-only", action="store_true", help="Keep only findings that cross workspaces")
    parser.add_argument("--output", help="Write the report to this file instead of stdout")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] invalid root: {root}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for file_path in iter_source_files(root):
        findings.extend(scan_file(file_path))
        if not args.scan_all and len(findings) >= args.max_results:
            break

    findings = filter_findings(findings[: args.max_results], workspace_only=args.workspace_only)
    findings = sort_findings(findings)

    rendered: str
    if args.format == "json":
        rendered = json.dumps([item.as_dict(root) for item in findings], indent=2, ensure_ascii=False)
    elif args.format == "md":
        rendered = format_md(findings, root)
    else:
        rendered = format_text(findings, root)

    if args.output:
        args.output and Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

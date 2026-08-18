#!/usr/bin/env python3
"""Scan a source tree for common bug-prone patterns.

This battery is for review only. It does not repair code.
It looks for:
- effects that allocate resources without an obvious cleanup;
- stale effects with empty dependency lists that still read live values;
- mirrored state that can create a second source of truth.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tree_audit_utils import iter_hook_calls, mask_literals_and_comments


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
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".md",
    ".json",
    ".sh",
    ".ps1",
}

SEVERITY_ORDER = {
    "critical": 0,
    "error": 1,
    "warning": 2,
    "info": 3,
}

LIVE_VALUE_HINTS = (
    "props.",
    "snapshot.",
    "client",
    "workspace",
    "selected",
    "active",
    "query",
    "filter",
    "loading",
    "open",
    "visible",
    "count",
    "current",
)


@dataclass(frozen=True)
class Finding:
    category: str
    pattern: str
    path: Path
    line: int
    message: str
    severity: str

    def as_dict(self, root: Path) -> dict[str, object]:
        return {
            "category": self.category,
            "pattern": self.pattern,
            "file": str(self.path.relative_to(root)),
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
        }


USE_EFFECT_RE = re.compile(r"\buseEffect\s*\(")
USE_CALLBACK_RE = re.compile(r"\buseCallback\s*\(")
USE_MEMO_RE = re.compile(r"\buseMemo\s*\(")
USE_STATE_RE = re.compile(r"""useState\(\s*(?P<expr>[^)]*)\)""")


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


def extract_window(lines: list[str], start_line: int, span: int = 12) -> str:
    begin = max(0, start_line - 1)
    end = min(len(lines), start_line - 1 + span)
    return "\n".join(lines[begin:end])


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


def effect_cleanup_findings(path: Path, text: str) -> list[Finding]:
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
                    message="effect adds a listener but no cleanup is visible nearby",
                    severity="warning",
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
                )
            )
        if "fetch(" in call and "AbortController" not in call and "abort(" not in call:
            findings.append(
                Finding(
                    category="effect-cleanup",
                    pattern="useEffect + fetch",
                    path=path,
                    line=lineno,
                    message="effect fetches without an obvious abort path",
                    severity="warning",
                )
            )
    return findings


def stale_effect_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    state_names = set(re.findall(r"\bconst\s*\[\s*([A-Za-z_$][\w$]*)\s*,\s*[A-Za-z_$][\w$]*\s*\]\s*=\s*useState", text))
    for index, hook_name, _call, body, deps in iter_hook_calls(text):
        if hook_name != "useEffect" or deps:
            continue
        lineno = text.count("\n", 0, index) + 1
        searchable_body = mask_literals_and_comments(body)
        local_names = {
            name
            for groups in re.findall(
                r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)|\bcatch\s*\(\s*([A-Za-z_$][\w$]*)",
                searchable_body,
            )
            for name in groups
            if name
        }
        local_names.update(
            name
            for groups in re.findall(
                r"(?:\(\s*([A-Za-z_$][\w$]*)\s*\)|\b([A-Za-z_$][\w$]*))\s*=>",
                searchable_body,
            )
            for name in groups
            if name
        )
        direct_live_read = re.search(r"\b(?:props|snapshot)(?:\?*\.[A-Za-z_$][\w$]*)+", searchable_body)
        state_read = any(
            re.search(rf"(?<![.\w$]){re.escape(name)}\b(?!\s*\??\.)", searchable_body)
            for name in state_names
            if name not in local_names
        )
        if direct_live_read or state_read:
            findings.append(
                Finding(
                    category="stale-effect",
                    pattern="useEffect([], live value reads)",
                    path=path,
                    line=lineno,
                    message="empty-deps effect still reads live props/state-like values",
                    severity="warning",
                )
            )
    return findings


def mirrored_state_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for lineno, line_text in enumerate(lines, start=1):
        match = USE_STATE_RE.search(line_text)
        if not match:
            continue
        expr = match.group("expr")
        if "props." not in expr and "snapshot." not in expr:
            continue
        window = extract_window(lines, lineno, span=18)
        if "setState(" in window:
            continue
        if "set" in window and "props." in window:
            findings.append(
                Finding(
                    category="dual-source",
                    pattern="useState(props) + sync",
                    path=path,
                    line=lineno,
                    message="state is seeded from props and appears to be mirrored locally",
                    severity="info",
                )
            )
    return findings


def scan_file(path: Path) -> list[Finding]:
    text = read_text(path)
    if not text:
        return []
    findings: list[Finding] = []
    findings.extend(effect_cleanup_findings(path, text))
    findings.extend(stale_effect_findings(path, text))
    findings.extend(mirrored_state_findings(path, text))
    return findings


def format_text(findings: list[Finding], root: Path) -> str:
    if not findings:
        return "No obvious bug-prone candidates found."
    lines = [f"Found {len(findings)} candidate(s):"]
    for item in findings:
        rel = item.path.relative_to(root)
        lines.append(f"- [{item.severity}] {rel}:{item.line} {item.category} {item.pattern} :: {item.message}")
    return "\n".join(lines)


def format_md(findings: list[Finding], root: Path) -> str:
    if not findings:
        return "# Tree bug audit\n\nNo obvious bug-prone candidates found."
    lines = [
        "# Tree bug audit",
        "",
        "| Severity | File | Line | Category | Pattern | Message |",
        "|---|---|---:|---|---|---|",
    ]
    for item in findings:
        rel = item.path.relative_to(root)
        lines.append(f"| {item.severity} | `{rel}` | {item.line} | {item.category} | `{item.pattern}` | {item.message} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recursively scan for bug-prone patterns.")
    parser.add_argument("--root", default=".", help="Root directory to scan")
    parser.add_argument("--format", choices=("text", "json", "md"), default="text")
    parser.add_argument("--max-results", type=int, default=300)
    parser.add_argument("--scan-all", action="store_true", help="Scan the full tree even after reaching max results")
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

    findings = sort_findings(findings[: args.max_results])

    if args.format == "json":
        rendered = json.dumps([item.as_dict(root) for item in findings], indent=2, ensure_ascii=False)
    elif args.format == "md":
        rendered = format_md(findings, root)
    else:
        rendered = format_text(findings, root)

    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

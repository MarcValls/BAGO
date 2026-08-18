#!/usr/bin/env python3
"""Scan a source tree for truth-source and dependency-surface bugs.

This battery is for review only. It does not repair code.
It looks for:
- hooks with incomplete or empty dependency surfaces that still read live values;
- mirrored state seeded from props/snapshot and kept locally;
- files that mix backend snapshot reads with local persistent state.
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

LIVE_HINTS = (
    "props.",
    "snapshot.",
    "workspace",
    "client",
    "query",
    "filter",
    "loading",
    "open",
    "visible",
    "selected",
    "active",
    "count",
    "current",
    "value",
)

STATE_SEED_RE = re.compile(r"""useState\(\s*(?P<expr>[^)]*)\)""")
STORAGE_RE = re.compile(r"""\b(?:sessionStorage|localStorage)\.""")
JS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
STATE_NAME_RE = re.compile(r"\bconst\s*\[\s*([A-Za-z_$][\w$]*)\s*,\s*[A-Za-z_$][\w$]*\s*\]\s*=\s*useState")
DIRECT_LIVE_RE = re.compile(r"\b(?:props|snapshot|client)(?:\?*\.[A-Za-z_$][\w$]*)+")
LOCAL_NAME_RE = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)|\bcatch\s*\(\s*([A-Za-z_$][\w$]*)")
ARROW_PARAM_RE = re.compile(r"(?:\(\s*([A-Za-z_$][\w$]*)\s*\)|\b([A-Za-z_$][\w$]*))\s*=>")


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


def extract_window(lines: list[str], start_line: int, span: int = 14) -> str:
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


def hook_dependency_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    state_names = set(STATE_NAME_RE.findall(text))
    for index, hook_name, _call, body, deps_text in iter_hook_calls(text):
        hook = hook_name.removeprefix("use")
        lineno = text.count("\n", 0, index) + 1
        deps = [re.sub(r"\s+", "", item.replace("?.", ".")) for item in deps_text.split(",") if item.strip()]
        searchable_body = mask_literals_and_comments(body)
        local_names = {name for groups in LOCAL_NAME_RE.findall(searchable_body) for name in groups if name}
        local_names.update(name for groups in ARROW_PARAM_RE.findall(searchable_body) for name in groups if name)
        references = {match.group(0).replace("?.", ".") for match in DIRECT_LIVE_RE.finditer(searchable_body)}
        references.update(
            name for name in state_names
            if re.search(rf"(?<![.\w$]){re.escape(name)}\b(?!\s*:)", searchable_body)
            and name not in local_names
            and not any(reference.startswith(f"{name}.") for reference in references)
        )

        def covered(reference: str) -> bool:
            return any(
                reference == dep
                or reference.startswith(f"{dep}.")
                or dep.startswith(f"{reference}.")
                for dep in deps
            )

        missing = sorted(reference for reference in references if not covered(reference))
        if not missing:
            continue
        if not deps and hook in {"Effect", "Callback"}:
            findings.append(
                Finding(
                    category="deps-gap",
                    pattern=f"use{hook}([])",
                    path=path,
                    line=lineno,
                    message=f"use{hook} has empty deps but reads: {', '.join(missing[:4])}",
                    severity="warning",
                )
            )
        else:
            findings.append(
                Finding(
                    category="deps-gap",
                    pattern=f"use{hook}(missing refs)",
                    path=path,
                    line=lineno,
                    message=f"dependency review needed for: {', '.join(missing[:4])}",
                    severity="info",
                )
            )
    return findings


def mirrored_state_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for lineno, line_text in enumerate(lines, start=1):
        match = STATE_SEED_RE.search(line_text)
        if not match:
            continue
        expr = match.group("expr")
        if "props." not in expr and "snapshot." not in expr:
            continue
        window = extract_window(lines, lineno, span=18)
        if "useEffect" in window and "set" in window and ("props." in window or "snapshot." in window):
            findings.append(
                Finding(
                    category="mirror-state",
                    pattern="useState(props/snapshot) + sync effect",
                    path=path,
                    line=lineno,
                    message="state is seeded from props/snapshot and then mirrored locally",
                    severity="warning",
                )
            )
        else:
            findings.append(
                Finding(
                    category="mirror-state",
                    pattern="useState(props/snapshot)",
                    path=path,
                    line=lineno,
                    message="state is seeded from props/snapshot and should be checked for single-source ownership",
                    severity="info",
                )
            )
    return findings


def dual_source_findings(path: Path, text: str) -> list[Finding]:
    if "snapshot." not in text and "props.snapshot" not in text:
        return []
    if not STORAGE_RE.search(text):
        return []
    findings: list[Finding] = []
    for lineno, line_text in enumerate(text.splitlines(), start=1):
        if STORAGE_RE.search(line_text):
            findings.append(
                Finding(
                    category="dual-source",
                    pattern="snapshot + storage",
                    path=path,
                    line=lineno,
                    message="file mixes backend snapshot reads with local persistent storage writes/reads",
                    severity="warning",
                )
            )
            break
    return findings


def scan_file(path: Path) -> list[Finding]:
    text = read_text(path)
    if not text:
        return []
    findings: list[Finding] = []
    if path.suffix.lower() in JS_EXTS:
        findings.extend(hook_dependency_findings(path, text))
        findings.extend(mirrored_state_findings(path, text))
        findings.extend(dual_source_findings(path, text))
    return findings


def format_text(findings: list[Finding], root: Path) -> str:
    if not findings:
        return "No obvious truth-source candidates found."
    lines = [f"Found {len(findings)} candidate(s):"]
    for item in findings:
        rel = item.path.relative_to(root)
        lines.append(f"- [{item.severity}] {rel}:{item.line} {item.category} {item.pattern} :: {item.message}")
    return "\n".join(lines)


def format_md(findings: list[Finding], root: Path) -> str:
    if not findings:
        return "# Tree truth audit\n\nNo obvious truth-source candidates found."
    lines = [
        "# Tree truth audit",
        "",
        "| Severity | File | Line | Category | Pattern | Message |",
        "|---|---|---:|---|---|---|",
    ]
    for item in findings:
        rel = item.path.relative_to(root)
        lines.append(f"| {item.severity} | `{rel}` | {item.line} | {item.category} | `{item.pattern}` | {item.message} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recursively scan for truth-source and dependency-surface bugs.")
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

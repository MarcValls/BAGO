#!/usr/bin/env python3
"""Rebuild the consolidated tree audit report from the latest JSON scans."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "backend" / "docs" / "audit"
OUTPUT = AUDIT_DIR / "tree-audit-full-prioritized.md"

SEVERITY_ORDER = {
    "critical": 0,
    "error": 1,
    "warning": 2,
    "info": 3,
}

SOURCES = [
    ("tree-state-audit.full.json", "tree-state-audit.full.json"),
    ("tree-bug-audit.full.json", "tree-bug-audit.full.json"),
    ("tree-truth-audit.full.json", "tree-truth-audit.full.json"),
]


def load_findings() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for filename, source_label in SOURCES:
        path = AUDIT_DIR / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data:
            row = dict(item)
            row["_source"] = source_label
            findings.append(row)
    return findings


def severity_rank(value: str) -> int:
    return SEVERITY_ORDER.get(value, 99)


def build_markdown(findings: list[dict[str, object]]) -> str:
    counts = Counter(str(item.get("severity", "info")) for item in findings)
    lines = [
        "# Tree audit full prioritized",
        "",
        "Generated with:",
        "",
        "```powershell",
        "python scripts\\tree_state_audit.py --root . --format json --workspace-only --scan-all --max-results 100000 --output backend/docs/audit/tree-state-audit.full.json",
        "python scripts\\tree_bug_audit.py --root . --format json --scan-all --max-results 100000 --output backend/docs/audit/tree-bug-audit.full.json",
        "python scripts\\tree_truth_audit.py --root . --format json --scan-all --max-results 100000 --output backend/docs/audit/tree-truth-audit.full.json",
        "```",
        "",
        f"- Total findings: {len(findings)}",
        f"- Severity counts: {dict(counts)}",
        "",
        "| Severity | File | Line | Category | Pattern | Source | Message |",
        "|---|---|---:|---|---|---|---|",
    ]
    for item in sorted(
        findings,
        key=lambda row: (
            severity_rank(str(row.get("severity", "info"))),
            str(row.get("file", "")).lower(),
            int(row.get("line", 0) or 0),
            str(row.get("category", "")),
            str(row.get("pattern", "")),
        ),
    ):
        lines.append(
            f"| {item.get('severity', 'info')} | `{item.get('file', '')}` | {item.get('line', '')} | "
            f"{item.get('category', '')} | `{item.get('pattern', '')}` | {item.get('_source', '')} | {item.get('message', '')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    findings = load_findings()
    OUTPUT.write_text(build_markdown(findings), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} with {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

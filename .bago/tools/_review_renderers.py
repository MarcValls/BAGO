from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

from typing import Any

from _review_collectors import REVIEW_COMMAND, STATUS_OK, STATUS_SKIPPED, STATUS_WARN

_GRN = "\033[0;32m"
_YEL = "\033[0;33m"
_RED = "\033[0;31m"
_RST = "\033[0m"
_BOLD = "\033[1m"


def verdict_id(verdict: Any) -> str:
    if isinstance(verdict, dict):
        return str(verdict.get("id", ""))
    if isinstance(verdict, str):
        if "MERGE OK" in verdict:
            return "mergeable"
        if "REVIEW REQUIRED" in verdict:
            return "review-required"
        return "no-merge"
    return "no-merge"


def verdict_label(verdict: Any) -> str:
    if isinstance(verdict, dict):
        return str(verdict.get("label", ""))
    return str(verdict)


def verdict_icon(verdict: Any) -> str:
    current = verdict_id(verdict)
    if current == "mergeable":
        return "🟢"
    if current == "review-required":
        return "🟡"
    return "🔴"


def generate_text(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    current = verdict_id(verdict)
    score = report["score"]
    color = _GRN if current == "mergeable" else (_YEL if current == "review-required" else _RED)
    blocker_count = report.get("blocker_count", 0)
    scanner_failures = report.get("scanner_failures", 0)

    lines = [
        f"{_BOLD}╔══ BAGO Review ══╗{_RST}",
        f"  Score:   {color}{score}/100{_RST}",
        f"  Verdict: {_BOLD}{verdict_label(verdict)}{_RST}",
        f"  Lines:   {report['total_lines']}  |  Findings: {report['total_findings']}  |  Blockers: {blocker_count}  |  Scanner failures: {scanner_failures}  |  Time: {report['elapsed_s']}s",
        "",
    ]
    for section in report["sections"].values():
        icon = "✅" if section["status"] == STATUS_OK else ("⚠️" if section["status"] == STATUS_WARN else ("⏭️" if section["status"] == STATUS_SKIPPED else "❌"))
        lines.append(
            f"  {icon} {section['name']:20s}  {section['findings']} finding(s)  [scanner={section['scanner_status']}, rc={section['exit_code']}, parse={section['parse_status']}]"
        )
        if section["error"]:
            lines.append(f"      ↳ {section['error']}")
    lines += ["", f"  {_BOLD}{'-' * 40}{_RST}"]
    return "\n".join(lines)


def generate_markdown(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    blocker_count = report.get("blocker_count", 0)
    schema_version = report.get("schema_version", 1)
    scanner_failures = report.get("scanner_failures", 0)
    scanner_errors = report.get("scanner_errors", {})
    lines = [
        "# BAGO Review",
        "",
        f"**Score:** {verdict_icon(verdict)} {report['score']}/100  |  **Verdict:** {verdict_label(verdict)}  |  **Blockers:** {blocker_count}",
        "",
        "| Scanner | Findings | Review status | Scanner status | Parse |",
        "|---------|----------|---------------|----------------|-------|",
    ]
    for section in report["sections"].values():
        icon = "✅" if section["status"] == STATUS_OK else ("⚠️" if section["status"] == STATUS_WARN else ("⏭️" if section["status"] == STATUS_SKIPPED else "❌"))
        scanner_status = section["scanner_status"]
        if section["error"]:
            scanner_status = f"{scanner_status} (`rc={section['exit_code']}`)"
        lines.append(
            f"| {section['name']} | {section['findings']} | {icon} {section['status']} | {scanner_status} | {section['parse_status']} |"
        )
    lines += [
        "",
        "**Scanner status legend:** passed/findings/error/skipped",
        f"**Lines analyzed:** {report['total_lines']}  | **Time:** {report['elapsed_s']}s  | **Scanner failures:** {scanner_failures}",
        "",
        "---",
        f"*Generated with `{REVIEW_COMMAND}` · schema v{schema_version}*",
    ]
    if scanner_errors:
        lines += ["", "## Scanner errors"]
        for key, error in scanner_errors.items():
            lines.append(f"- `{key}`: {error}")
    return "\n".join(lines)

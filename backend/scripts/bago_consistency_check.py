#!/usr/bin/env python3
"""bago_consistency_check.py — BAGO consistency and drift checker.

Emits JSON with structure:
    {
      "status": "ok" | "warn" | "fail",
      "errors": <int>,
      "warnings": <int>,
      "issues": [{"check": str, "severity": "error"|"warning", "message": str}]
    }

Usage:
    python3 bago_consistency_check.py [--json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _check_version_files() -> list[dict]:
    issues = []
    rv_file = REPO_ROOT / "release_version.txt"
    vj_file = REPO_ROOT / "versions.json"
    init_file = REPO_ROOT / "bago_core" / "__init__.py"

    rv = rv_file.read_text(encoding="utf-8").strip() if rv_file.exists() else None
    if not rv:
        issues.append({"check": "version-files", "severity": "error",
                       "message": "release_version.txt missing or empty"})
        return issues

    if vj_file.exists():
        current = json.loads(vj_file.read_text(encoding="utf-8")).get("current")
        if current != rv:
            issues.append({"check": "version-files", "severity": "error",
                           "message": f"versions.json.current={current!r} != release_version.txt={rv!r}"})

    if init_file.exists():
        import re
        src = init_file.read_text(encoding="utf-8")
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
        if m and m.group(1) != rv:
            issues.append({"check": "version-files", "severity": "warning",
                           "message": f"bago_core/__init__.py __version__={m.group(1)!r} != {rv!r}"})

    return issues


def _check_no_hardcoded_secrets() -> list[dict]:
    issues = []
    import re
    PATTERNS = [
        (r"sk-[A-Za-z0-9]{32,}", "OpenAI key"),
        (r"\d{8,12}:AA[A-Za-z0-9_-]{30,}", "Telegram token"),
    ]
    # Intentional canary/decoy/fixture files — skip secret scan
    EXCLUDE_NAMES = {"bago_canary.py", "bago_backup_vault.py"}
    # Exclude build artifacts and dist dirs
    EXCLUDE_DIR_PARTS = {"dist", "node_modules", "__pycache__", ".git", "bago-release"}
    for p in sorted(REPO_ROOT.rglob("*.py")):
        parts = set(p.parts)
        if parts & EXCLUDE_DIR_PARTS:
            continue
        if p.name in EXCLUDE_NAMES:
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in PATTERNS:
            if re.search(pattern, src):
                rel = str(p.relative_to(REPO_ROOT))
                issues.append({"check": "secrets", "severity": "error",
                               "message": f"{label} pattern found in {rel}"})
    return issues


def main() -> int:
    all_issues: list[dict] = []
    all_issues.extend(_check_version_files())
    all_issues.extend(_check_no_hardcoded_secrets())

    errors = sum(1 for i in all_issues if i["severity"] == "error")
    warnings = sum(1 for i in all_issues if i["severity"] == "warning")

    if errors:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "ok"

    payload = {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "issues": all_issues,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

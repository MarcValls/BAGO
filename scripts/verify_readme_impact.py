#!/usr/bin/env python3
"""Require README.md updates when public README-impacting surfaces change.

This complements the generated README truth projection. The projection covers
machine-derived facts; this gate covers hand-maintained explanatory sections
such as installation, lifecycle, commands, security and public architecture.

In GitHub Actions the changed-file set is derived from the event's base/head
SHAs. If an impacting file changes without README.md in the same diff, CI
fails closed.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ImpactRule:
    reason: str
    patterns: tuple[str, ...]


IMPACT_RULES: tuple[ImpactRule, ...] = (
    ImpactRule(
        "version or runtime contract changed",
        (
            "release_version.txt",
            "backend/release_version.txt",
            "package.json",
            "frontend/package.json",
            "electron-viewer/package.json",
            "frontend/public/ui_config.json",
            "versions.json",
            "backend/versions.json",
        ),
    ),
    ImpactRule(
        "public architecture, security or governance changed",
        (
            "backend/docs/ARCHITECTURE.md",
            "backend/docs/SECURITY.md",
            "backend/docs/MODULES.md",
            "backend/docs/MVP.md",
            "backend/docs/support-matrix.md",
            "backend/docs/contracts/*.md",
            "backend/.bago/contracts/*.json",
        ),
    ),
    ImpactRule(
        "execution or authorization boundary changed",
        (
            "backend/.bago/core/effect_registry.py",
            "backend/.bago/core/execution_request.py",
            "backend/.bago/core/authorization_boundary.py",
            "backend/.bago/core/execution_gateway.py",
            "backend/.bago/core/delegation_grant.py",
            "backend/.bago/core/schedule_registry.py",
            "backend/.bago/api/handlers_schedule.py",
            "backend/.bago/api/handlers_capability_packages.py",
        ),
    ),
    ImpactRule(
        "installation, release or lifecycle behavior changed",
        (
            "install-remote.ps1",
            "ARRANCAR_BAGO.bat",
            "backend/install-v4.ps1",
            "scripts/dev.ps1",
            "scripts/dev.sh",
            "electron-viewer/**",
            "releases/**",
            ".github/workflows/build-installer.yml",
            ".github/workflows/build-release-installer.yml",
        ),
    ),
    ImpactRule(
        "public command or documentation entrypoint changed",
        (
            "DOCUMENTATION.md",
            "backend/docs/README.md",
            "backend/bago_core/cli.py",
            "backend/.bago/chat/**",
        ),
    ),
)


def _matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def validate_impact(changed_files: list[str]) -> list[str]:
    normalized = [path.replace("\\", "/") for path in changed_files]
    if not normalized or "README.md" in normalized:
        return []

    findings: list[str] = []
    for rule in IMPACT_RULES:
        matched = sorted(path for path in normalized if _matches(path, rule.patterns))
        if matched:
            findings.append(f"- {rule.reason}: {', '.join(matched)}")

    if not findings:
        return []

    return [
        "README update required: README-impacting surfaces changed but README.md is unchanged.",
        *findings,
        "Run npm run docs:sync for generated facts and update explanatory README prose when needed.",
    ]


def _read_event(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("GitHub event payload must be an object")
    return data


def _event_range() -> tuple[str, str] | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip()
    if not event_path or not event_name:
        return None

    payload = _read_event(Path(event_path))
    if event_name == "pull_request":
        pr = payload.get("pull_request")
        if not isinstance(pr, dict):
            raise ValueError("pull_request payload missing")
        base = pr.get("base")
        head = pr.get("head")
        if not isinstance(base, dict) or not isinstance(head, dict):
            raise ValueError("pull_request base/head missing")
        return str(base.get("sha") or ""), str(head.get("sha") or "")

    if event_name == "push":
        return str(payload.get("before") or ""), str(payload.get("after") or "")

    return None


def _changed_files(root: Path) -> list[str]:
    event_range = _event_range()
    if event_range is None:
        return []

    base, head = event_range
    if not base or not head or set(base) == {"0"}:
        return []

    attempts = (f"{base}...{head}", f"{base}..{head}")
    errors: list[str] = []
    for spec in attempts:
        result = subprocess.run(
            ["git", "diff", "--name-only", spec],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return [
                line.strip().replace("\\", "/")
                for line in result.stdout.splitlines()
                if line.strip()
            ]
        errors.append(result.stderr.strip())

    raise RuntimeError(
        "Cannot resolve README impact diff. Canonical CI must checkout full history. "
        + " | ".join(error for error in errors if error)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Explicit changed files for local/test use; otherwise derive from GitHub event.",
    )
    args = parser.parse_args()

    try:
        changed = args.files if args.files is not None else _changed_files(args.root.resolve())
        errors = validate_impact(list(changed))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"[readme-impact] error: {exc}")
        return 2

    if errors:
        for error in errors:
            print(f"[readme-impact] {error}")
        return 2

    print(f"[readme-impact] PASS ({len(changed)} changed files inspected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

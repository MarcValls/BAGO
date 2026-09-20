#!/usr/bin/env python3
"""Fail closed when README.md drifts from canonical repository truth.

The script has two layers:

1. Static truth checks: version/runtime/governance claims in README must match
   canonical repository sources.
2. Impact checks in CI: if a PR/push changes a README-impacting surface, the
   same change set must also update README.md.

This is intentionally a gate, not an auto-commit bot. CI must never rewrite
source truth behind the author's back.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
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
        "canonical version or runtime requirements changed",
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
        "public architecture/security/governance changed",
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
        "execution/authorization boundary changed",
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
        "installation/release/distribution behavior changed",
        (
            "install-remote.ps1",
            "backend/install-v4.ps1",
            "releases/**",
            ".github/workflows/build-installer.yml",
            ".github/workflows/build-release-installer.yml",
            ".github/workflows/canonical-ci.yml",
        ),
    ),
    ImpactRule(
        "public documentation index changed",
        (
            "DOCUMENTATION.md",
            "backend/docs/README.md",
        ),
    ),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json(path: Path) -> dict:
    value = json.loads(_read(path))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _canonical_version(root: Path) -> str:
    version = _read(root / "release_version.txt").strip()
    if not version:
        raise ValueError("release_version.txt is empty")
    return version


def _node_minimum(root: Path) -> str:
    engine = str(_json(root / "package.json").get("engines", {}).get("node", "")).strip()
    match = re.fullmatch(r">=\s*([0-9]+(?:\.[0-9]+){1,2})", engine)
    if not match:
        raise ValueError(f"Unsupported package.json engines.node format: {engine!r}")
    return match.group(1)


def _first_state_line(path: Path) -> str:
    for line in _read(path).splitlines():
        if line.startswith("Estado: "):
            return line.removeprefix("Estado: ").strip("* ")
    raise ValueError(f"No Estado line found in {path}")


def validate_static_truth(root: Path) -> list[str]:
    errors: list[str] = []
    readme = _read(root / "README.md")
    version = _canonical_version(root)
    node_min = _node_minimum(root)
    plan_state = _first_state_line(
        root / "backend/docs/contracts/execution_gateway_unification_plan.v1.md"
    )

    required = {
        "title version": f"# BAGO v{version}",
        "version badge": f"version-{version}-blue",
        "release link": f"/releases/tag/v{version}",
        "installer artifact": f"bago-{version}-setup.exe",
        "Node requirement": f"| Node.js | ≥ {node_min} |",
        "execution plan state": plan_state,
        "boundary status": "UNIQUE_EXECUTION_BOUNDARY = NOT_YET",
        "strong-human status": "STRONG_HUMAN_IDENTITY_VERIFIED = NO",
        "P4 state": "P4 · Scheduler + DelegationGrant",
    }
    for label, text in required.items():
        if text not in readme:
            errors.append(f"README drift: missing {label}: {text!r}")

    wrong_node_badges = re.findall(r"node-([0-9.]+)%2B-green", readme)
    if wrong_node_badges and node_min not in wrong_node_badges:
        errors.append(
            "README drift: Node badge does not match package.json "
            f"(expected {node_min}, found {wrong_node_badges})"
        )

    # Published 4.11.1 is signed. Keep this explicit until release metadata is
    # projected automatically from a canonical release manifest.
    if version == "4.11.1":
        forbidden = (
            "pre-release, **sin firmar**",
            "no hay credenciales de firma Authenticode configuradas",
        )
        for text in forbidden:
            if text in readme:
                errors.append(f"README drift: obsolete v4.11.1 release claim: {text!r}")
        if "Authenticode" not in readme or "firmad" not in readme.lower():
            errors.append("README drift: v4.11.1 signing state is not documented")

    return errors


def _changed_files_from_event(root: Path) -> list[str]:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return []
    path = Path(event_path)
    if not path.exists():
        return []
    payload = json.loads(_read(path))
    event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip()

    base = ""
    head = ""
    if event_name == "pull_request":
        base = str(payload.get("pull_request", {}).get("base", {}).get("sha", ""))
        head = str(payload.get("pull_request", {}).get("head", {}).get("sha", ""))
    elif event_name == "push":
        base = str(payload.get("before", ""))
        head = str(payload.get("after", ""))

    if not base or not head or set(base) == {"0"}:
        return []

    for spec in (f"{base}...{head}", f"{base}..{head}"):
        proc = subprocess.run(
            ["git", "diff", "--name-only", spec],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]
    raise RuntimeError(
        "Unable to calculate README impact diff. Ensure actions/checkout uses fetch-depth: 0."
    )


def _matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def validate_impact(changed_files: list[str]) -> list[str]:
    if not changed_files or "README.md" in changed_files:
        return []

    hits: list[str] = []
    for rule in IMPACT_RULES:
        matched = sorted(path for path in changed_files if _matches(path, rule.patterns))
        if matched:
            hits.append(f"- {rule.reason}: {', '.join(matched)}")

    if not hits:
        return []

    return [
        "README update required: this change touches README-impacting surfaces "
        "but README.md is unchanged.",
        *hits,
        "Update README.md in the same PR/push, then rerun CI.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--skip-impact",
        action="store_true",
        help="Run only static truth checks.",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    errors = validate_static_truth(root)
    changed_files: list[str] = []
    if not args.skip_impact:
        changed_files = _changed_files_from_event(root)
        errors.extend(validate_impact(changed_files))

    if errors:
        for error in errors:
            print(f"error: {error}")
        return 2

    version = _canonical_version(root)
    if changed_files:
        print(f"README freshness PASS: version={version}; changed_files={len(changed_files)}")
    else:
        print(f"README freshness PASS: version={version}; static truth only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

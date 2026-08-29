#!/usr/bin/env python3
"""Re-record the required remediation gates for the current candidate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from package_remediation_audit import REQUIRED_GATES, ROOT


EVIDENCE_DIR = ROOT / ".bago" / "evidence" / "remediation-gates"


def gate_metadata(name: str) -> dict:
    path = EVIDENCE_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing prior gate metadata: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_command(command: list[str], name: str, stamp: str) -> list[str]:
    normalized = list(command)
    for index, arg in enumerate(normalized):
        if arg == "--basetemp" and index + 1 < len(normalized):
            normalized[index + 1] = f".run/gate-{stamp}-{name}"
        elif arg.startswith("--basetemp="):
            normalized[index] = f"--basetemp=.run/gate-{stamp}-{name}"
    return normalized


def extra_repositories(metadata: dict) -> list[str]:
    current_root = ROOT.resolve()
    repositories = metadata.get("candidate_repositories_after") or {}
    return [
        str(Path(path).resolve())
        for path in repositories
        if Path(path).resolve() != current_root
    ]


def with_safe_directories(extra_repos: list[str]) -> dict[str, str]:
    env = os.environ.copy()
    start = int(env.get("GIT_CONFIG_COUNT") or "0")
    for offset, repo in enumerate(dict.fromkeys(extra_repos)):
        index = start + offset
        env[f"GIT_CONFIG_KEY_{index}"] = "safe.directory"
        env[f"GIT_CONFIG_VALUE_{index}"] = Path(repo).resolve().as_posix()
    if extra_repos:
        env["GIT_CONFIG_COUNT"] = str(start + len(dict.fromkeys(extra_repos)))
    return env


def run_gate(name: str, stamp: str) -> int:
    metadata = gate_metadata(name)
    extras = extra_repositories(metadata)
    command = normalize_command(list(metadata["command"]), name, stamp)
    recorder = [sys.executable, str(ROOT / "scripts" / "record_remediation_gate.py"), "--name", name]
    for extra in extras:
        recorder += ["--extra-repo", extra]
    recorder += ["--", *command]
    result = subprocess.run(
        recorder,
        cwd=ROOT,
        env=with_safe_directories(extras),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'} rc={result.returncode}")
    if result.returncode:
        if result.stdout:
            print(result.stdout[-6000:])
        if result.stderr:
            print(result.stderr[-6000:], file=sys.stderr)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stamp", default="current", help="Suffix for pytest basetemp directories")
    parser.add_argument("--only", action="append", default=[], help="Run only the named gate")
    args = parser.parse_args()

    gates = tuple(args.only) if args.only else REQUIRED_GATES
    unknown = sorted(set(gates) - set(REQUIRED_GATES))
    if unknown:
        parser.error(f"unknown required gate: {', '.join(unknown)}")

    for gate in gates:
        rc = run_gate(gate, args.stamp)
        if rc:
            return rc
    print("ALL_GATES_RECORDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

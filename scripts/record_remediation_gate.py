#!/usr/bin/env python3
"""Run one gate and persist raw, candidate-bound evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from bago_core.candidate_identity import fingerprint  # noqa: E402


def _version(command: list[str], cwd: Path = ROOT) -> str | None:
    executable = command[0]
    if os.name == "nt" and executable.lower() in {"npm", "npx", "node"}:
        executable = executable + ".cmd" if executable.lower() != "node" else executable + ".exe"
    if not shutil.which(executable):
        return None
    try:
        result = subprocess.run(
            [executable, *command[1:]],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr).strip()
    return output if result.returncode == 0 and output else None


def runtime_versions(repositories: list[Path]) -> dict:
    """Capture the actual runtimes capable of executing the recorded gate."""
    runtime: dict[str, object] = {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "node": _version(["node", "--version"]),
        "npm": _version(["npm", "--version"]),
    }
    package_versions: dict[str, dict[str, str]] = {}
    probes = {
        "playwright": "for (const p of ['@playwright/test/package.json','playwright/package.json']) { try { console.log(require(p).version); process.exit(0) } catch {} } process.exit(1)",
        "electron": "try { console.log(require('electron/package.json').version) } catch { process.exit(1) }",
        "vitest": "try { console.log(require('vitest/package.json').version) } catch { process.exit(1) }",
    }
    for repo in repositories:
        found: dict[str, str] = {}
        for name, probe in probes.items():
            value = _version(["node", "-e", probe], cwd=repo)
            if value:
                found[name] = value.splitlines()[-1].strip()
        if found:
            package_versions[str(repo)] = found
    runtime["node_packages"] = package_versions
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--repo", default=str(ROOT), help="Repositorio principal al que ligar el gate")
    parser.add_argument("--extra-repo", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("command required after --")
    if os.name == "nt" and command[0].lower() in {"npm", "npx", "yarn", "pnpm"}:
        command[0] += ".cmd"
    primary_repo = Path(args.repo).resolve()
    repositories = [primary_repo, *(Path(value).resolve() for value in args.extra_repo)]
    started = datetime.now(timezone.utc).isoformat()
    before_repositories = {str(repo): fingerprint(repo) for repo in repositories}
    before = before_repositories[str(primary_repo)]
    result = subprocess.run(command, cwd=primary_repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    finished = datetime.now(timezone.utc).isoformat()
    after_repositories = {str(repo): fingerprint(repo) for repo in repositories}
    after = after_repositories[str(primary_repo)]
    evidence_dir = primary_repo / ".bago" / "evidence" / "remediation-gates"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in args.name)
    stdout_path = evidence_dir / f"{safe_name}.stdout.log"
    stderr_path = evidence_dir / f"{safe_name}.stderr.log"
    metadata_path = evidence_dir / f"{safe_name}.json"
    stdout_path.write_text(result.stdout, encoding="utf-8", newline="\n")
    stderr_path.write_text(result.stderr, encoding="utf-8", newline="\n")
    metadata = {
        "contract": "bago.gate-evidence.v1",
        "name": args.name,
        "command": command,
        "exit_code": result.returncode,
        "started_at": started,
        "finished_at": finished,
        "runtime": runtime_versions(repositories),
        "candidate_before": before,
        "candidate_after": after,
        "candidate_repositories_before": before_repositories,
        "candidate_repositories_after": after_repositories,
        "candidate_stable": before_repositories == after_repositories,
        "stdout": stdout_path.name,
        "stderr": stderr_path.name,
        "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    print(json.dumps({"gate": args.name, "exit_code": result.returncode, "evidence": str(metadata_path)}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read-only contract gate for the scoped BAGOx Codex overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
PRODUCT_VERSION_RE = re.compile(r"BAGO monorepo\s*\(v?\d+\.\d+\.\d+", re.IGNORECASE)
HANDOFF_CANDIDATE_RE = re.compile(r"^Candidate:\s*([0-9a-f]{40})\b", re.MULTILINE)
SHA256_RE = re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def verify_manifest(package_root: Path, errors: list[str]) -> str | None:
    manifest = package_root / "MANIFEST.sha256"
    if not manifest.is_file():
        errors.append(f"missing package manifest: {manifest}")
        return None

    manifest_hash = sha256_file(manifest)
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            errors.append(f"invalid manifest entry: {line!r}")
            continue
        relative = parts[1].strip().removeprefix("./")
        candidate = (package_root / relative).resolve()
        try:
            candidate.relative_to(package_root.resolve())
        except ValueError:
            errors.append(f"manifest path escapes package: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"manifest file missing: {relative}")
        elif sha256_file(candidate) != parts[0].lower():
            errors.append(f"manifest digest mismatch: {relative}")
    return manifest_hash


def verify(
    repo_root: Path,
    package_root: Path | None = None,
    state_file: Path | None = None,
    handoff_file: Path | None = None,
    require_verification: bool = False,
) -> list[str]:
    """Return contract errors without changing repository or state files."""
    errors: list[str] = []
    repo_root = repo_root.resolve()
    head = git_head(repo_root)
    agents = (repo_root / "AGENTS.md")
    release = repo_root / "release_version.txt"

    if not agents.is_file():
        errors.append("missing AGENTS.md")
    else:
        agents_text = agents.read_text(encoding="utf-8")
        if PRODUCT_VERSION_RE.search(agents_text):
            errors.append("AGENTS.md publishes a mutable product version")
        if "`release_version.txt`" not in agents_text:
            errors.append("AGENTS.md does not name release_version.txt as version authority")
        if "BAGOx Behavior Package v1.3-RC1-FIX2" not in agents_text:
            errors.append("AGENTS.md does not identify the scoped BAGOx package")
    if not release.is_file():
        errors.append("missing release_version.txt")
    else:
        version = release.read_text(encoding="utf-8").strip()
        if not SEMVER_RE.fullmatch(version):
            errors.append(f"release_version.txt is not SemVer: {version!r}")

    if package_root is not None:
        manifest_hash = verify_manifest(package_root.resolve(), errors)
        if agents.is_file() and manifest_hash:
            pinned_hashes = {value.lower() for value in SHA256_RE.findall(agents.read_text(encoding="utf-8"))}
            if manifest_hash not in pinned_hashes:
                errors.append("AGENTS.md does not pin the supplied package MANIFEST.sha256")

    state_file = state_file or repo_root / ".bago" / "state" / "PROJECT_STATE.json"
    if state_file.is_file():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid PROJECT_STATE.json: {exc.msg}")
        else:
            for field in ("commit",):
                if state.get(field) != head:
                    errors.append(f"state {field} does not match HEAD")
            fingerprint = state.get("fingerprint")
            if not isinstance(fingerprint, dict) or fingerprint.get("commit") != head:
                errors.append("state fingerprint commit does not match HEAD")
            verification = state.get("last_verification")
            if require_verification and not isinstance(verification, dict):
                errors.append("state has no current verification receipt")
            elif isinstance(verification, dict) and verification.get("commit") != head:
                errors.append("last verification commit does not match HEAD")
            if state.get("candidate_sha") not in (None, head):
                errors.append("state candidate_sha conflicts with current HEAD")
            if "validation" in state:
                errors.append("current state must not carry a historical validation marker")

    handoff_file = handoff_file or repo_root / ".bago" / "runtime" / "ACTIVE_HANDOFF.md"
    if handoff_file.is_file():
        match = HANDOFF_CANDIDATE_RE.search(handoff_file.read_text(encoding="utf-8"))
        if not match:
            errors.append("handoff does not declare a candidate SHA")
        elif match.group(1) != head:
            errors.append("handoff candidate does not match HEAD")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the read-only BAGOx overlay contract.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--handoff-file", type=Path)
    parser.add_argument(
        "--require-verification",
        action="store_true",
        help="Require an existing current-candidate verification receipt.",
    )
    args = parser.parse_args()

    errors = verify(
        args.repo_root,
        args.package_root,
        args.state_file,
        args.handoff_file,
        args.require_verification,
    )
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

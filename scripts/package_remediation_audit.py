#!/usr/bin/env python3
"""Build a reproducible third-party remediation evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_PATTERNS = ("pi-session-", "session-export", "session_export")
SOURCE_AUDIT_SHA256 = "8f92998edbc7f815450aa246197a0b16ee68be6af27006cc9d523b762da3764d"
REQUIRED_GATES = (
    "focused-remediation",
    "backend-full",
    "frontend-tests",
    "frontend-typecheck",
    "frontend-build",
    "ui-live-smoke",
    "electron-manager-smoke",
    "release-manager",
    "release-resume",
    "gestor-typecheck",
    "gestor-build",
    "gestor-e2e",
    "workflow-yaml",
    "diff-check",
    "session-export-hygiene",
    "source-package-tests",
)


def run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=check)


def text(repo: Path, *args: str) -> str:
    result = run(repo, *args, check=False)
    return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else ""


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_patch(repo: Path, baseline_ref: str, candidate_ref: str) -> bytes:
    result = run(repo, "diff", "--binary", "--no-ext-diff", baseline_ref, candidate_ref, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed for {repo}: {result.stderr.decode('utf-8', 'replace')}")
    raw = result.stdout
    return raw.replace(b"\r\n", b"\n")


def provenance(repo: Path, baseline_ref: str, candidate_ref: str) -> dict:
    baseline = text(repo, "rev-parse", baseline_ref)
    candidate = text(repo, "rev-parse", candidate_ref)
    remote = text(repo, "remote", "get-url", "origin") or None
    branch = text(repo, "branch", "--show-current") or None
    upstream = text(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or None
    status = text(repo, "status", "--porcelain=v1", "--untracked-files=all")
    identity_seed = f"{repo.resolve()}\n{baseline}\n{candidate}\n{remote or 'local-only'}".encode("utf-8")
    return {
        "repository_id": sha_bytes(identity_seed),
        "path_at_capture": str(repo.resolve()),
        "baseline_sha": baseline,
        "candidate_sha": candidate,
        "branch": branch,
        "upstream": upstream,
        "remote": remote,
        "remote_status": "configured" if remote else "local-only-explicit",
        "dirty": bool(status),
        "status": status.splitlines(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def changed_files(repo: Path, baseline_ref: str, candidate_ref: str) -> list[str]:
    tracked = text(repo, "diff", "--name-only", "--diff-filter=ACMRT", baseline_ref, candidate_ref).splitlines()
    return sorted(set(filter(None, tracked)))


def forbidden(relative: str) -> bool:
    lowered = relative.replace("\\", "/").lower()
    return lowered.endswith(".html") and any(pattern in lowered for pattern in SESSION_PATTERNS)


def archive_ref(repo: Path, ref: str, destination: Path) -> None:
    archive = run(repo, "archive", "--format=zip", ref).stdout
    with zipfile.ZipFile(__import__("io").BytesIO(archive)) as source:
        source.extractall(destination)


def validate_patch(repo: Path, baseline_ref: str, patch: bytes) -> None:
    with tempfile.TemporaryDirectory(prefix="bago-patch-check-") as td:
        baseline = Path(td) / "baseline"
        baseline.mkdir()
        archive_ref(repo, baseline_ref, baseline)
        patch_path = Path(td) / "delta.patch"
        patch_path.write_bytes(patch)
        result = subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=baseline, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", "replace"))


def copy_delta(repo: Path, baseline_ref: str, candidate_ref: str, destination: Path) -> list[str]:
    copied = []
    for relative in changed_files(repo, baseline_ref, candidate_ref):
        if forbidden(relative):
            continue
        result = run(repo, "show", f"{candidate_ref}:{relative}", check=False)
        if result.returncode != 0:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.stdout)
        copied.append(relative.replace("\\", "/"))
    return copied


def add_tree(zf: zipfile.ZipFile, source: Path) -> list[dict]:
    entries = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        if forbidden(relative):
            raise RuntimeError(f"session export forbidden in audit bundle: {relative}")
        zf.write(path, relative)
        entries.append({"path": relative, "size": path.stat().st_size, "sha256": sha_file(path)})
    return entries


def ingest_source_audit(source_zip: Path, destination: Path, bago_baseline: str) -> dict:
    """Copy only provenance-bearing, non-session evidence from the original audit."""
    if not source_zip.is_file():
        raise RuntimeError(f"source audit missing: {source_zip}")
    digest = sha_file(source_zip)
    if digest != SOURCE_AUDIT_SHA256:
        raise RuntimeError(f"source audit SHA mismatch: {digest}")
    copied: list[str] = []
    destination.mkdir(parents=True, exist_ok=True)
    allowed_audit = {"audit/README.md", "audit/git-diff.patch", "audit/git-diff-stat.txt", "audit/git-log-40.txt", "audit/git-status.txt"}
    with zipfile.ZipFile(source_zip) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir() or ".." in Path(name).parts or name.lower().endswith(".html"):
                continue
            if name in allowed_audit:
                relative = f"original-{Path(name).name}"
            elif name.startswith("worktree-changes/gestor-con-bago/"):
                relative = "gestor-snapshot/" + name.removeprefix("worktree-changes/gestor-con-bago/")
            else:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            copied.append(relative)
    raw_patch = destination / "original-git-diff.patch"
    if not raw_patch.exists():
        raise RuntimeError("original audit patch missing")
    normalized = raw_patch.read_bytes().replace(b"\r\n", b"\n")
    normalized_path = destination / "original-git-diff.lf.patch"
    normalized_path.write_bytes(normalized)
    validate_patch(ROOT, bago_baseline, normalized)
    copied.append(normalized_path.name)
    provenance = {
        "contract": "bago.source-audit-provenance.v1", "source_name": source_zip.name,
        "source_sha256": digest, "session_html": "excluded", "copied": sorted(copied),
        "original_patch_raw_sha256": sha_file(raw_patch), "normalized_patch_sha256": sha_file(normalized_path),
        "normalized_patch_apply_check": "PASS", "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    (destination / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n")
    return provenance


def build(
    output: Path,
    gestor: Path,
    logs: Path | None,
    bago_baseline: str,
    gestor_baseline: str,
    candidate_ref: str = "HEAD",
    source_audit: Path | None = None,
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bago-remediation-bundle-") as td:
        stage = Path(td)
        audit = stage / "audit"
        audit.mkdir()
        if source_audit is not None:
            ingest_source_audit(source_audit, audit / "source-audit", bago_baseline)

        repositories = (
            ("bago", ROOT, bago_baseline),
            ("gestor", gestor.resolve(), gestor_baseline),
        )
        for label, repo, baseline_ref in repositories:
            if not (repo / ".git").exists():
                raise RuntimeError(f"{label} has no Git baseline: {repo}")
            patch = canonical_patch(repo, baseline_ref, candidate_ref)
            validate_patch(repo, baseline_ref, patch)
            (audit / f"{label}-git-diff.patch").write_bytes(patch)
            info = provenance(repo, baseline_ref, candidate_ref)
            if info["dirty"]:
                raise RuntimeError(f"{label} candidate is dirty; commit or remove drift before packaging")
            (audit / f"{label}-provenance.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            archive_ref(repo, baseline_ref, stage / f"{label}-baseline-git")
            copied = copy_delta(repo, baseline_ref, candidate_ref, stage / f"{label}-candidate-changes")
            (audit / f"{label}-delta-files.json").write_text(json.dumps(copied, indent=2) + "\n", encoding="utf-8", newline="\n")

        handoff = ROOT / ".bago" / "audits" / "remediation-handoff-20260824.md"
        if not handoff.exists():
            raise RuntimeError("tracked remediation handoff is missing")
        shutil.copy2(handoff, audit / "REMEDIATION_HANDOFF.md")
        if logs and logs.exists():
            shutil.copytree(
                logs, audit / "raw-gate-logs", dirs_exist_ok=True,
                ignore=lambda _directory, names: {name for name in names if name.startswith("audit-package-verify")},
            )

        package_meta = {
            "contract": "bago.third-party-remediation.v1",
            "findings": [f"BAGO-AUD-{index:03d}" for index in range(1, 11)],
            "session_exports": "excluded",
            "patch_validation": "git apply --check PASS for both baselines",
            "candidate_ref": candidate_ref,
            "required_gates": list(REQUIRED_GATES),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "known_limitations": [
                "Initial dirty remediation boundary hash 943f59fd339f0f57c63f21beb785c0d3c35f6977ecf7bf569b74c324a523bb79 has no retained patch bytes; exact attribution is UNRESOLVED."
            ],
        }
        (audit / "bundle-contract.json").write_text(json.dumps(package_meta, indent=2) + "\n", encoding="utf-8", newline="\n")

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            entries = add_tree(zf, stage)
            manifest = {"contract": package_meta["contract"], "files": entries}
            manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            zf.writestr("MANIFEST.sha256.json", manifest_bytes)

    checksums = output.with_suffix(output.suffix + ".sha256")
    checksums.write_text(f"{sha_file(output)}  {output.name}\n", encoding="utf-8", newline="\n")
    return {"package": str(output), "sha256": sha_file(output), "checksums": str(checksums)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "output" / "BAGO-remediation-audit.zip"))
    parser.add_argument("--gestor", default=str(ROOT.parent / "gestor-con-bago"))
    parser.add_argument("--logs", default=str(ROOT / ".bago" / "evidence" / "remediation-gates"))
    parser.add_argument("--bago-baseline", default="e76b01b0a0552d8eee7c536f8c4eef25e3a82a42")
    parser.add_argument("--gestor-baseline", default="0cb2038b118281db750263f14547b00788618816")
    parser.add_argument("--candidate-ref", default="HEAD")
    parser.add_argument("--source-audit", default=str(ROOT / ".run" / "BAGO-third-party-audit-20260822-173517.zip"))
    args = parser.parse_args()
    result = build(
        Path(args.output),
        Path(args.gestor),
        Path(args.logs),
        args.bago_baseline,
        args.gestor_baseline,
        args.candidate_ref,
        Path(args.source_audit) if args.source_audit else None,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

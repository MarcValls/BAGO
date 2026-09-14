#!/usr/bin/env python3
"""Generate a GitHub-revalidated receipt for the tracked single-maintainer exception."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BAGO_RUNTIME = ROOT / ".bago" / "bin" / "bago.py"


def _runtime() -> Any:
    spec = importlib.util.spec_from_file_location("bago_runtime", BAGO_RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_receipt(
    module: Any, repository: str, pull_request: int, package: Path, candidate: str | None, target_status: str,
) -> dict[str, Any]:
    package_sha = _sha256(package)
    candidate_sha = candidate or module._remediation_candidate(package)
    receipt = {
        "contract": "bago.single-maintainer.github.v1",
        "result": "PASS",
        "maintainer": module._github_current_login(),
        "candidate_sha": candidate_sha,
        "package_sha256": package_sha,
        "github": {"repository": repository, "pull_request": pull_request},
    }
    fingerprint = module._git_fingerprint()
    if not module._verify_single_maintainer_receipt(
        receipt, fingerprint, candidate_sha, package_sha, target_status
    ):
        raise ValueError("current identity, pull request, or live GitHub policy is not eligible for single-maintainer receipt")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=None)
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--candidate-sha", default=None)
    parser.add_argument("--status", choices=("VERIFIED", "VALIDATED"), default="VERIFIED")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    module = _runtime()
    package = Path(args.package).resolve()
    if not package.is_file():
        print(f"error: remediation package not found: {package}", file=sys.stderr)
        return 2
    try:
        repository = args.repository or module._github_repository_from_origin(module._git_fingerprint().get("remote"))
        receipt = build_receipt(
            module, repository, args.pull_request, package, args.candidate_sha, args.status
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Single-maintainer receipt written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

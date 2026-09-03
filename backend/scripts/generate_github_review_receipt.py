#!/usr/bin/env python3
"""generate_github_review_receipt.py

Build a `bago.independent-review.github.v2` receipt directly from the GitHub
API instead of hand-authoring the JSON. The local file this script writes is
never itself the authority: `.bago/bin/bago.py consume-remediation-receipt`
re-queries GitHub for the same review before accepting VERIFIED/VALIDATED, so
editing this file locally, or GitHub later dismissing/changing the review,
cannot promote a protected state.

Usage:
    python backend/scripts/generate_github_review_receipt.py \\
        --pull-request 204 --review-id 123456 \\
        --package output/BAGO-remediation-audit-<sha>.zip \\
        --out output/BAGO-remediation-audit-<sha>.independent-review.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BAGO_RUNTIME = ROOT / ".bago" / "bin" / "bago.py"


def _load_bago_runtime():
    """Import `.bago/bin/bago.py` as a module so the GitHub-authority checks
    (attestation matching, PR/permission fetch) have a single implementation
    shared with the consumer, instead of a second hand-copied one here."""
    spec = importlib.util.spec_from_file_location("bago_runtime", BAGO_RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_login() -> str:
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
        raise ValueError(f"cannot resolve authenticated GitHub login: {detail[-300:]}")
    login = result.stdout.strip()
    if not login:
        raise ValueError("authenticated GitHub login is empty")
    return login


def build_receipt(
    module: Any, repository: str, pull_request: int, review_id: int, package: Path, candidate: str | None,
) -> dict[str, Any]:
    package_sha = _sha256_file(package)
    candidate_sha = candidate or module._remediation_candidate(package)

    pull = module._github_pull_request(repository, pull_request)
    review = module._github_pull_review(repository, pull_request, review_id)

    pull_author = pull.get("user") or {}
    reviewer = (review.get("user") or {}).get("login")
    authenticated_login = _current_login()

    if not isinstance(reviewer, str) or not reviewer:
        raise ValueError("GitHub review has no authenticated reviewer login")
    if reviewer != authenticated_login:
        raise ValueError(
            f"authenticated GitHub session ({authenticated_login}) does not match the review author ({reviewer}); "
            "run this tool as the reviewer who submitted the approval"
        )
    if reviewer == pull_author.get("login"):
        raise ValueError("reviewer is the pull request author; self-review is never eligible")
    if review.get("state") != "APPROVED":
        raise ValueError(f"GitHub review state is not APPROVED: {review.get('state')!r}")
    if review.get("commit_id") != candidate_sha:
        raise ValueError(
            f"GitHub review commit_id ({review.get('commit_id')!r}) does not match the candidate ({candidate_sha!r}); "
            "the review is stale relative to the last push"
        )
    if not module._github_review_attestation_matches(review, candidate_sha, package_sha):
        raise ValueError("GitHub review body does not contain the required, unambiguous attestation fields")
    if not module._github_requires_fresh_approval(repository):
        raise ValueError("main does not require a fresh approving review in live GitHub branch protection")

    permission = module._github_collaborator_permission(repository, reviewer)
    if permission not in module._AUTHORIZED_REVIEW_PERMISSIONS:
        raise ValueError(f"reviewer {reviewer!r} does not hold an authorized repository permission ({permission!r})")

    return {
        "contract": "bago.independent-review.github.v2",
        "result": "PASS",
        "reviewer": reviewer,
        "candidate_sha": candidate_sha,
        "package_sha256": package_sha,
        "github": {
            "repository": repository,
            "pull_request": pull_request,
            "review_id": review_id,
        },
        # Captured only for audit traceability; consumption re-queries GitHub
        # and never trusts these recorded values on their own.
        "captured": {
            "pull_request_author": pull_author.get("login"),
            "pull_request_base_ref": (pull.get("base") or {}).get("ref"),
            "pull_request_state": pull.get("state"),
            "pull_request_merged": pull.get("merged"),
            "reviewer_permission": permission,
            "review_body": review.get("body"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=None, help="owner/repo (defaults to the current origin)")
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--review-id", type=int, required=True)
    parser.add_argument("--package", required=True, help="Immutable remediation ZIP bound to the candidate SHA")
    parser.add_argument("--candidate-sha", default=None, help="Override candidate SHA (defaults to the package provenance)")
    parser.add_argument("--out", required=True, help="Path to write the independent review receipt JSON")
    args = parser.parse_args(argv)

    module = _load_bago_runtime()
    package = Path(args.package).resolve()
    if not package.is_file():
        print(f"error: remediation package not found: {package}", file=sys.stderr)
        return 2

    try:
        repository = args.repository or module._github_repository_from_origin(module._git_fingerprint().get("remote"))
        receipt = build_receipt(module, repository, args.pull_request, args.review_id, package, args.candidate_sha)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Independent review receipt written: {out_path}")
    print(f"  reviewer={receipt['reviewer']} candidate_sha={receipt['candidate_sha']} package_sha256={receipt['package_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

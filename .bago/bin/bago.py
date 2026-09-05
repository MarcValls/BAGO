#!/usr/bin/env python3
"""BAGO runtime wrapper for the working tree.

Maintains durable project state under `.bago/` so that long-running work
survives between Pi/Codex sessions.  It is intentionally small: it does not
create authority, only records authority already present in the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LIFECYCLE = ("PROPOSED", "PREPARED", "EXECUTED", "VERIFIED", "VALIDATED")
_MANUAL_STATES = frozenset(_LIFECYCLE[:3])
_REMEDIATION_RECEIPT_CONTRACT = "bago.third-party-remediation-verification.v1"
_INDEPENDENT_REVIEW_CONTRACT = "bago.independent-review.github.v2"
_SINGLE_MAINTAINER_RECEIPT_CONTRACT = "bago.single-maintainer.github.v1"
_SINGLE_MAINTAINER_POLICY_CONTRACT = "bago.single-maintainer-governance.v1"
_GITHUB_REVIEW_ATTESTATION = "bago.protected-remediation-attestation.v1"
_REQUIRED_PR_BASE_REF = "main"
_AUTHORIZED_REVIEW_PERMISSIONS = frozenset({"push", "maintain", "admin"})


def _repo_root() -> Path:
    # The wrapper lives at <repo>/.bago/bin/bago.py
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "backend").is_dir() or (candidate / ".bago").is_dir():
        return candidate
    # Fallback to Git root if the script was moved.
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    raise RuntimeError("Cannot determine repository root")


def _bago_dir() -> Path:
    return _repo_root() / ".bago"


def _paths() -> dict[str, Path]:
    root = _bago_dir()
    return {
        "context": root / "context" / "PROJECT_CONTEXT.md",
        "state": root / "state" / "PROJECT_STATE.json",
        "handoff": root / "runtime" / "ACTIVE_HANDOFF.md",
        "decisions": root / "decisions" / "DECISIONS.md",
        "conflicts": root / "conflicts" / "CONFLICTS.md",
    }


def _ensure_dirs() -> None:
    for sub in ("bin", "context", "state/agents", "runtime", "decisions", "conflicts"):
        (_bago_dir() / sub).mkdir(parents=True, exist_ok=True)


def _git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_fingerprint() -> dict[str, Any]:
    commit = _git_text("rev-parse", "HEAD") or None
    branch = _git_text("rev-parse", "--abbrev-ref", "HEAD") or None
    remote = _git_text("remote", "get-url", "origin") or None
    upstream = _git_text("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or None
    status = _git_text("status", "--porcelain=v1", "--untracked-files=all")
    tracked = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=_repo_root(), capture_output=True, check=False
    ).stdout
    digest = hashlib.sha256(tracked + status.encode("utf-8")).hexdigest()
    return {
        "commit": commit,
        "branch": branch,
        "remote": remote,
        "upstream": upstream,
        "dirty": bool(status),
        "worktree_sha256": digest,
    }


def _load_state() -> dict[str, Any]:
    path = _paths()["state"]
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "version": "",
        "status": "idle",
        "note": "",
        "updated_at": "",
        "commit": None,
        "branch": None,
        "last_verification": None,
    }


def _save_state(state: dict[str, Any]) -> None:
    _ensure_dirs()
    _paths()["state"].write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {label}")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _repo_root() / path
    return path.resolve()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: JSON object required")
    return value


def _remediation_candidate(package: Path) -> str:
    try:
        with zipfile.ZipFile(package) as archive:
            provenance = json.loads(archive.read("audit/bago-provenance.json"))
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"invalid remediation package: {exc}") from exc
    candidate = provenance.get("candidate_sha") if isinstance(provenance, dict) else None
    if not isinstance(candidate, str) or len(candidate) != 40:
        raise ValueError("invalid remediation package: BAGO candidate SHA is missing")
    if provenance.get("dirty") is not False:
        raise ValueError("invalid remediation package: BAGO candidate was dirty")
    return candidate


def _verify_remediation_package(package: Path) -> dict[str, Any]:
    verifier = _repo_root() / "scripts" / "verify_remediation_audit.py"
    if not verifier.is_file():
        raise ValueError("remediation verifier is unavailable")
    with tempfile.TemporaryDirectory(prefix="bago-receipt-") as directory:
        report = Path(directory) / "verification.json"
        result = subprocess.run(
            [sys.executable, str(verifier), str(package), "--report", str(report)],
            cwd=_repo_root(), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
            raise ValueError(f"remediation package verification failed: {detail[-500:]}")
        return _load_json_object(report, "recalculated verification receipt")


def _github_repository_from_origin(origin: Any) -> str:
    """Return the GitHub owner/repository identity configured for this checkout."""
    if not isinstance(origin, str):
        raise ValueError("current repository has no GitHub origin")
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?/?",
        origin.strip(),
    )
    if not match:
        raise ValueError("current repository origin is not a GitHub repository")
    return f"{match.group(1)}/{match.group(2)}"


def _github_pull_review(repository: str, pull_request: int, review_id: int) -> dict[str, Any]:
    """Load an authenticated GitHub pull-request review, failing closed on error."""
    try:
        result = subprocess.run(
            [
                "gh", "api", "--method", "GET",
                f"repos/{repository}/pulls/{pull_request}/reviews/{review_id}",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"GitHub review provenance is unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
        raise ValueError(f"GitHub review provenance is unavailable: {detail[-300:]}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub review provenance is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("GitHub review provenance is not a JSON object")
    return value


def _github_pull_request(repository: str, pull_request: int) -> dict[str, Any]:
    """Load the authenticated GitHub pull request, failing closed on error."""
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", f"repos/{repository}/pulls/{pull_request}"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"GitHub pull request provenance is unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
        raise ValueError(f"GitHub pull request provenance is unavailable: {detail[-300:]}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub pull request provenance is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("GitHub pull request provenance is not a JSON object")
    return value


def _github_paginated_list(repository: str, resource: str, label: str) -> list[dict[str, Any]]:
    """Load every page of a GitHub REST list endpoint or reject the authority check."""
    try:
        result = subprocess.run(
            [
                "gh", "api", "--method", "GET", "--paginate", "--slurp",
                f"repos/{repository}/{resource}?per_page=100",
            ],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"GitHub {label} is unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
        raise ValueError(f"GitHub {label} is unavailable: {detail[-300:]}")
    try:
        pages = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub {label} is invalid JSON: {exc}") from exc
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError(f"GitHub {label} is not a paginated JSON array")
    entries = [entry for page in pages for entry in page]
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError(f"GitHub {label} contains an invalid entry")
    return entries


def _github_pull_reviews(repository: str, pull_request: int) -> list[dict[str, Any]]:
    """Load every GitHub review so a superseding request for changes is visible."""
    return _github_paginated_list(repository, f"pulls/{pull_request}/reviews", "pull request reviews")


def _github_head_commit_actors(repository: str, pull_request: int, candidate: str) -> set[str]:
    """Return GitHub identities recorded as author/committer of the PR head commit."""
    commits = _github_paginated_list(repository, f"pulls/{pull_request}/commits", "pull request commits")
    matches = [commit for commit in commits if commit.get("sha") == candidate]
    if len(matches) != 1:
        raise ValueError("GitHub pull request head commit provenance is missing or ambiguous")
    actors: set[str] = set()
    for field in ("author", "committer"):
        identity = matches[0].get(field)
        login = identity.get("login") if isinstance(identity, dict) else None
        if isinstance(login, str) and login:
            actors.add(login)
    return actors


def _github_collaborator_permission(repository: str, login: str) -> str:
    """Load the authenticated GitHub collaborator permission, failing closed on error."""
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", f"repos/{repository}/collaborators/{login}/permission"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"GitHub reviewer permission is unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
        raise ValueError(f"GitHub reviewer permission is unavailable: {detail[-300:]}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub reviewer permission is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("GitHub reviewer permission is not a JSON object")
    permission = value.get("permission")
    if not isinstance(permission, str) or not permission:
        raise ValueError("GitHub reviewer permission is missing")
    return permission


def _github_current_login() -> str:
    """Load the authenticated GitHub login, failing closed when unavailable."""
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", "user"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"GitHub authenticated identity is unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
        raise ValueError(f"GitHub authenticated identity is unavailable: {detail[-300:]}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub authenticated identity is invalid JSON: {exc}") from exc
    login = value.get("login") if isinstance(value, dict) else None
    if not isinstance(login, str) or not login:
        raise ValueError("GitHub authenticated identity is missing")
    return login


def _github_branch_protection(repository: str, branch: str) -> dict[str, Any]:
    """Load authenticated GitHub branch protection, failing closed on error."""
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", f"repos/{repository}/branches/{branch}/protection"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"GitHub branch protection is unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
        raise ValueError(f"GitHub branch protection is unavailable: {detail[-300:]}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub branch protection is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("GitHub branch protection is not a JSON object")
    return value


def _github_requires_fresh_approval(repository: str) -> bool:
    """Return whether main's live policy requires a fresh independent approval."""
    protection = _github_branch_protection(repository, _REQUIRED_PR_BASE_REF)
    reviews = protection.get("required_pull_request_reviews")
    if not isinstance(reviews, dict):
        return False
    approving_count = reviews.get("required_approving_review_count")
    return (
        isinstance(approving_count, int)
        and not isinstance(approving_count, bool)
        and approving_count >= 1
        and reviews.get("dismiss_stale_reviews") is True
        and reviews.get("require_last_push_approval") is True
    )


def _single_maintainer_policy() -> dict[str, Any]:
    """Load the tracked, explicit exception instead of inferring it from a missing review."""
    path = _bago_dir() / "governance" / "single-maintainer.json"
    policy = _load_json_object(path, "single-maintainer governance policy")
    if (
        policy.get("contract") != _SINGLE_MAINTAINER_POLICY_CONTRACT
        or policy.get("mode") != "single-maintainer"
        or not isinstance(policy.get("owner"), str)
        or not policy["owner"].strip()
        or policy.get("required_status_check") != "validate"
        or policy.get("requires_pull_request") is not True
        or policy.get("review_requirement") != "not-applicable"
    ):
        raise ValueError("single-maintainer governance policy is invalid")
    return policy


def _github_requires_single_maintainer_policy(repository: str) -> bool:
    """Verify the remote policy retains PR/check/admin safeguards while omitting reviews."""
    policy = _single_maintainer_policy()
    protection = _github_branch_protection(repository, _REQUIRED_PR_BASE_REF)
    reviews = protection.get("required_pull_request_reviews")
    checks = protection.get("required_status_checks")
    enforce_admins = protection.get("enforce_admins")
    required_checks = checks.get("checks") if isinstance(checks, dict) else None
    return (
        isinstance(reviews, dict)
        and reviews.get("required_approving_review_count") == 0
        and reviews.get("dismiss_stale_reviews") is False
        and reviews.get("require_last_push_approval") is False
        and isinstance(required_checks, list)
        and any(
            isinstance(check, dict)
            and check.get("context") == policy["required_status_check"]
            and check.get("app_id") == 15368
            for check in required_checks
        )
        and isinstance(enforce_admins, dict)
        and enforce_admins.get("enabled") is True
    )


def _github_review_attestation_matches(remote_review: dict[str, Any], candidate: str, package_sha: str) -> bool:
    """Require the GitHub-hosted approval body to bind the remediation package."""
    body = remote_review.get("body")
    if not isinstance(body, str):
        return False
    required = {
        "attestation": _GITHUB_REVIEW_ATTESTATION,
        "contract": _INDEPENDENT_REVIEW_CONTRACT,
        "result": "PASS",
        "candidate_sha": candidate,
        "package_sha256": package_sha,
    }
    fields: dict[str, list[str]] = {key: [] for key in required}
    for line in body.splitlines():
        match = re.fullmatch(r"\s*([a-z0-9_]+)\s*:\s*([^\s]+)\s*", line)
        if match and match.group(1) in fields:
            fields[match.group(1)].append(match.group(2))
    # A review body is authenticated GitHub data, but it is still free-form
    # Markdown. Require one unambiguous declaration of every bound property.
    return all(fields[key] == [value] for key, value in required.items())


def _github_has_authorized_blocking_review(repository: str, pull_request: int) -> bool:
    """Reject a receipt if an authorized reviewer's latest decision requests changes."""
    latest: dict[str, dict[str, Any]] = {}
    for review in _github_pull_reviews(repository, pull_request):
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        submitted = review.get("submitted_at")
        review_id = review.get("id")
        if not isinstance(login, str) or not login or not isinstance(submitted, str) or not submitted:
            raise ValueError("GitHub review history has incomplete reviewer provenance")
        if not isinstance(review_id, int) or isinstance(review_id, bool) or review_id <= 0:
            raise ValueError("GitHub review history has an invalid review identifier")
        previous = latest.get(login)
        if previous is None or (submitted, review_id) > (previous["submitted_at"], previous["id"]):
            latest[login] = {"state": review.get("state"), "submitted_at": submitted, "id": review_id}
    for login, review in latest.items():
        if review["state"] == "CHANGES_REQUESTED":
            if _github_collaborator_permission(repository, login) in _AUTHORIZED_REVIEW_PERMISSIONS:
                return True
    return False


def _verify_independent_review(
    review: dict[str, Any], fp: dict[str, Any], candidate: str, package_sha: str, target_status: str = "VERIFIED",
) -> bool:
    """Verify review content and GitHub-authenticated provenance for a candidate.

    Beyond the review itself, this binds authority: the reviewer must hold
    real GitHub repository permission, must not be the pull request's own
    author, and the reviewed pull request must match this repository, base
    branch and head SHA exactly. VALIDATED additionally requires the pull
    request to be merged; a still-open PR can only support VERIFIED.
    """
    if review.get("contract") != _INDEPENDENT_REVIEW_CONTRACT or review.get("result") != "PASS":
        return False
    reviewer = review.get("reviewer")
    provenance = review.get("github")
    if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(provenance, dict):
        return False
    repository = provenance.get("repository")
    pull_request = provenance.get("pull_request")
    review_id = provenance.get("review_id")
    if (
        not isinstance(repository, str)
        or repository != _github_repository_from_origin(fp.get("remote"))
        or isinstance(pull_request, bool)
        or not isinstance(pull_request, int)
        or pull_request <= 0
        or isinstance(review_id, bool)
        or not isinstance(review_id, int)
        or review_id <= 0
        or review.get("candidate_sha") != candidate
        or review.get("package_sha256") != package_sha
    ):
        return False
    remote_review = _github_pull_review(repository, pull_request, review_id)
    remote_user = remote_review.get("user")
    if not (
        remote_review.get("state") == "APPROVED"
        and remote_review.get("commit_id") == candidate
        and isinstance(remote_user, dict)
        and remote_user.get("login") == reviewer
        and _github_review_attestation_matches(remote_review, candidate, package_sha)
    ):
        return False
    pull = _github_pull_request(repository, pull_request)
    pull_author = pull.get("user")
    pull_head = pull.get("head")
    pull_base = pull.get("base")
    if (
        pull.get("number") != pull_request
        or not isinstance(pull_head, dict)
        or pull_head.get("sha") != candidate
        or not isinstance(pull_base, dict)
        or pull_base.get("ref") != _REQUIRED_PR_BASE_REF
        or not isinstance(pull_author, dict)
        or not isinstance(pull_author.get("login"), str)
        or pull_author.get("login") == reviewer
    ):
        return False
    if not _github_requires_fresh_approval(repository):
        return False
    if _github_collaborator_permission(repository, reviewer) not in _AUTHORIZED_REVIEW_PERMISSIONS:
        return False
    if reviewer in _github_head_commit_actors(repository, pull_request, candidate):
        return False
    if _github_has_authorized_blocking_review(repository, pull_request):
        return False
    if target_status.upper() == "VALIDATED" and not (pull.get("state") == "closed" and pull.get("merged") is True):
        return False
    return True


def _verify_single_maintainer_receipt(
    receipt: dict[str, Any], fp: dict[str, Any], candidate: str, package_sha: str, target_status: str = "VERIFIED",
) -> bool:
    """Verify a documented owner-only exception without presenting it as independent review."""
    if receipt.get("contract") != _SINGLE_MAINTAINER_RECEIPT_CONTRACT or receipt.get("result") != "PASS":
        return False
    maintainer = receipt.get("maintainer")
    provenance = receipt.get("github")
    if not isinstance(maintainer, str) or not maintainer.strip() or not isinstance(provenance, dict):
        return False
    repository = provenance.get("repository")
    pull_request = provenance.get("pull_request")
    if (
        not isinstance(repository, str)
        or repository != _github_repository_from_origin(fp.get("remote"))
        or isinstance(pull_request, bool)
        or not isinstance(pull_request, int)
        or pull_request <= 0
        or receipt.get("candidate_sha") != candidate
        or receipt.get("package_sha256") != package_sha
    ):
        return False
    policy = _single_maintainer_policy()
    if maintainer != policy["owner"] or _github_current_login() != maintainer:
        return False
    if _github_collaborator_permission(repository, maintainer) != "admin":
        return False
    if not _github_requires_single_maintainer_policy(repository):
        return False
    pull = _github_pull_request(repository, pull_request)
    pull_author = pull.get("user")
    pull_base = pull.get("base")
    if (
        pull.get("number") != pull_request
        or not isinstance(pull_author, dict)
        or pull_author.get("login") != maintainer
        or not isinstance(pull_base, dict)
        or pull_base.get("ref") != _REQUIRED_PR_BASE_REF
    ):
        return False
    if target_status.upper() == "VALIDATED":
        return (
            pull.get("state") == "closed"
            and pull.get("merged") is True
            and pull.get("merge_commit_sha") == candidate
        )
    pull_head = pull.get("head")
    return (
        pull.get("state") == "open"
        and isinstance(pull_head, dict)
        and pull_head.get("sha") == candidate
    )


def _verify_protected_authority(
    receipt: dict[str, Any], fp: dict[str, Any], candidate: str, package_sha: str, target_status: str,
) -> bool:
    if receipt.get("contract") == _INDEPENDENT_REVIEW_CONTRACT:
        return _verify_independent_review(receipt, fp, candidate, package_sha, target_status)
    if receipt.get("contract") == _SINGLE_MAINTAINER_RECEIPT_CONTRACT:
        return _verify_single_maintainer_receipt(receipt, fp, candidate, package_sha, target_status)
    return False


def _has_current_protected_receipt(state: dict[str, Any], fp: dict[str, Any], claimed_status: str = "VERIFIED") -> bool:
    receipt = state.get("protected_receipt")
    if not isinstance(receipt, dict) or fp.get("dirty"):
        return False
    if receipt.get("candidate_sha") != fp.get("commit") or receipt.get("package_sha256") is None:
        return False
    try:
        package = _resolve_repo_path(receipt.get("package"), "package path")
        receipt_path = _resolve_repo_path(receipt.get("receipt"), "verification receipt path")
        verification = _load_json_object(receipt_path, "verification receipt")
        if _sha_file(package) != receipt["package_sha256"]:
            return False
        if _remediation_candidate(package) != fp.get("commit"):
            return False
        recalculated = _verify_remediation_package(package)
        if receipt.get("receipt_sha256") != _sha_file(receipt_path):
            return False
        verified = (
            verification.get("contract") == _REMEDIATION_RECEIPT_CONTRACT
            and verification.get("result") == "PASS"
            and verification.get("package") == package.name
            and verification.get("package_sha256") == receipt["package_sha256"]
            and all(verification.get(key) == recalculated.get(key) for key in ("contract", "result", "package", "package_sha256"))
        )
        review_path = _resolve_repo_path(receipt.get("review"), "independent review path")
        review = _load_json_object(review_path, "independent review receipt")
        return verified and receipt.get("review_sha256") == _sha_file(review_path) and _verify_protected_authority(
            review, fp, str(fp.get("commit")), str(receipt["package_sha256"]), claimed_status
        )
    except (KeyError, OSError, ValueError):
        return False


def _print_file(path: Path, label: str) -> None:
    print(f"\n=== {label}: {path} ===")
    if path.is_file():
        print(path.read_text(encoding="utf-8"))
    else:
        print("(not created)")


def cmd_status(_args: argparse.Namespace) -> int:
    state = _load_state()
    fp = _git_fingerprint()
    dirty = bool(fp.get("dirty"))
    recorded = state.get("fingerprint") or {}
    claimed_status = str(state.get("status", "idle"))
    protected_claim = claimed_status.upper() in {"VERIFIED", "VALIDATED"}
    missing_identity = protected_claim and not recorded
    stale = protected_claim and (missing_identity or recorded != fp)
    # PROJECT_STATE.json is project-authored context, not an independent
    # attestation. Even an exact fingerprint cannot self-certify a protected
    # lifecycle state; the immutable external receipt remains authoritative.
    has_receipt = _has_current_protected_receipt(state, fp, claimed_status.upper())
    effective_status = "STALE" if protected_claim and (dirty or stale) else "UNVERIFIED" if protected_claim and not has_receipt else claimed_status

    print(f"Repository: {_repo_root()}")
    print(f"Branch:     {fp.get('branch') or '?'}")
    print(f"Commit:     {fp.get('commit') or '?'}")
    print(f"Dirty:      {'yes' if dirty else 'no'}")
    print(f"Status:     {effective_status}")
    if effective_status in {"STALE", "UNVERIFIED"}:
        reason = "missing candidate fingerprint" if missing_identity else "candidate drift"
        if effective_status == "UNVERIFIED":
            reason = "protected state requires independent receipt verification"
        print(f"Recorded:   {claimed_status} (invalidated: {reason})")
    note_label = "Recorded note" if effective_status in {"STALE", "UNVERIFIED"} else "Note"
    print(f"{note_label}: {state.get('note', '')}")
    print(f"Updated:    {state.get('updated_at', '')}")
    if state.get("last_verification"):
        v = state["last_verification"]
        verify_label = "Recorded verify" if effective_status in {"STALE", "UNVERIFIED"} else "Last verify"
        print(f"{verify_label}: {v.get('command')} -> rc={v.get('returncode')} at {v.get('timestamp')}")

    _print_file(_paths()["context"], "Context")
    _print_file(_paths()["handoff"], "Handoff")
    _print_file(_paths()["decisions"], "Decisions")
    _print_file(_paths()["conflicts"], "Conflicts")
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    requested = str(args.status).strip().upper()
    if requested in {"VERIFIED", "VALIDATED"}:
        print(
            f"error: {requested} is a protected evidence state and cannot be set manually",
            file=sys.stderr,
        )
        return 2
    state = _load_state()
    if requested not in _MANUAL_STATES:
        print(
            f"error: unknown or non-manual lifecycle state: {requested or '<empty>'}",
            file=sys.stderr,
        )
        return 2
    current = str(state.get("status") or "").strip().upper()
    if current not in _LIFECYCLE:
        if requested != "PROPOSED":
            print(
                f"error: lifecycle must start at PROPOSED, not {requested}",
                file=sys.stderr,
            )
            return 2
    elif _LIFECYCLE.index(requested) > _LIFECYCLE.index(current) + 1:
        print(
            f"error: lifecycle jump is not permitted: {current} -> {requested}",
            file=sys.stderr,
        )
        return 2
    fp = _git_fingerprint()
    previous_fingerprint = state.get("fingerprint")
    if (
        isinstance(previous_fingerprint, dict)
        and previous_fingerprint.get("commit")
        and previous_fingerprint.get("commit") != fp.get("commit")
    ):
        previous_verification = state.pop("last_verification", None)
        if isinstance(previous_verification, dict):
            history = state.setdefault("history", {})
            continuity = history.setdefault("continuity", {})
            continuity["last_verification"] = previous_verification
            continuity["superseded_by"] = fp.get("commit")
    state["status"] = requested
    state["note"] = args.note
    state["updated_at"] = _iso_now()
    state["candidate_sha"] = fp.get("commit")
    state["commit"] = fp.get("commit")
    state["branch"] = fp.get("branch")
    state["fingerprint"] = fp
    _save_state(state)
    print(f"State updated: {state['status']}")
    if args.note:
        print(f"Note: {args.note}")
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    path = _paths()["handoff"]
    _ensure_dirs()
    if args.message is not None:
        header = f"# Active handoff\n\nUpdated: {_iso_now()}\n\n"
        path.write_text(header + args.message + "\n", encoding="utf-8")
        print("Handoff updated")
        return 0
    _print_file(path, "Handoff")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("error: verify requires a command after '--'", file=sys.stderr)
        return 2

    print(f"verify: {' '.join(command)}")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    state = _load_state()
    fp = _git_fingerprint()
    state["last_verification"] = {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout": result.stdout[:2000] if result.stdout else "",
        "stderr": result.stderr[:2000] if result.stderr else "",
        "commit": fp.get("commit"),
        "fingerprint": fp,
        "timestamp": _iso_now(),
    }
    state["fingerprint"] = fp
    state["candidate_sha"] = fp.get("commit")
    state["commit"] = fp.get("commit")
    state["branch"] = fp.get("branch")
    # `verify` records evidence; it is not a certification authority. Even a
    # clean successful command cannot preserve/promote a protected historical
    # claim. VERIFIED/VALIDATED require the closure policy and review gates.
    state["status"] = "EXECUTED"
    if result.returncode != 0:
        state["note"] = f"Verification failed (rc={result.returncode}); previous verification invalidated."
    elif fp.get("dirty"):
        state["note"] = "Verification command passed on a dirty candidate; global VERIFIED is not permitted."
    else:
        state["note"] = "Verification evidence recorded; protected state requires the closure policy and independent review."
    state["updated_at"] = _iso_now()
    _save_state(state)
    return result.returncode


def cmd_consume_remediation_receipt(args: argparse.Namespace) -> int:
    """Promote a protected state only from a candidate-bound external receipt."""
    target = str(args.status).upper()
    package = Path(args.package).resolve()
    receipt_path = Path(args.receipt).resolve()
    try:
        if not package.is_file():
            raise ValueError(f"remediation package not found: {package}")
        receipt = _load_json_object(receipt_path, "verification receipt")
        package_sha = _sha_file(package)
        candidate = _remediation_candidate(package)
        recalculated = _verify_remediation_package(package)
        if receipt.get("contract") != _REMEDIATION_RECEIPT_CONTRACT:
            raise ValueError("verification receipt has an unsupported contract")
        if receipt.get("result") != "PASS":
            raise ValueError("verification receipt does not report PASS")
        if receipt.get("package") != package.name or receipt.get("package_sha256") != package_sha:
            raise ValueError("verification receipt is not bound to this package")
        if any(receipt.get(key) != recalculated.get(key) for key in ("contract", "result", "package", "package_sha256")):
            raise ValueError("verification receipt does not match the recalculated package verification")
        fp = _git_fingerprint()
        if fp.get("dirty"):
            raise ValueError("current candidate is dirty")
        if fp.get("commit") != candidate:
            raise ValueError("remediation package candidate does not match current HEAD")
        if not args.review:
            raise ValueError(f"{target} requires --review with a GitHub-authenticated authority receipt")
        review = _load_json_object(Path(args.review).resolve(), "GitHub authority receipt")
        if not _verify_protected_authority(review, fp, candidate, package_sha, target):
            raise ValueError(
                "authority receipt is not bound to this candidate and the live GitHub governance policy"
            )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    state = _load_state()
    state["status"] = target
    state["note"] = f"{target} accepted from external remediation receipt bound to {candidate}."
    state["updated_at"] = _iso_now()
    state["commit"] = fp.get("commit")
    state["branch"] = fp.get("branch")
    state["fingerprint"] = fp
    state["protected_receipt"] = {
        "receipt": str(receipt_path),
        "receipt_contract": receipt["contract"],
        "package": str(package),
        "package_sha256": package_sha,
        "candidate_sha": candidate,
        "receipt_sha256": _sha_file(receipt_path),
        "review": str(Path(args.review).resolve()),
        "review_sha256": _sha_file(Path(args.review).resolve()),
    }
    _save_state(state)
    print(f"Protected state accepted: {target}")
    return 0


def cmd_init(_args: argparse.Namespace) -> int:
    _ensure_dirs()
    for label, path in _paths().items():
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            if label in ("decisions", "conflicts"):
                path.write_text(f"# {label.capitalize()}\n\n", encoding="utf-8")
            elif label == "handoff":
                path.write_text("# Active handoff\n\n", encoding="utf-8")
    print("BAGO runtime directories initialized")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bago.py",
        description="BAGO working-tree runtime wrapper.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show repository and BAGO state")

    state_parser = sub.add_parser("state", help="Update lifecycle state")
    state_parser.add_argument("status", help="Status label (e.g. PREPARED, EXECUTED)")
    state_parser.add_argument("--note", default="", help="Free-form note")

    handoff_parser = sub.add_parser("handoff", help="Read or update durable handoff")
    handoff_parser.add_argument("--set", dest="message", default=None, help="Set handoff text")

    verify_parser = sub.add_parser("verify", help="Run a verification command and record it")
    verify_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run (use -- before the command)",
    )

    receipt_parser = sub.add_parser(
        "consume-remediation-receipt",
        help="Consume a candidate-bound external remediation receipt for a protected state",
    )
    receipt_parser.add_argument("--package", required=True, help="Immutable remediation ZIP")
    receipt_parser.add_argument("--receipt", required=True, help="External verification JSON receipt")
    receipt_parser.add_argument("--status", choices=("VERIFIED", "VALIDATED"), required=True)
    receipt_parser.add_argument("--review", required=True, help="GitHub review or single-maintainer authority receipt")

    sub.add_parser("init", help="Create missing .bago directories and empty files")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 2

    dispatch = {
        "status": cmd_status,
        "state": cmd_state,
        "handoff": cmd_handoff,
        "verify": cmd_verify,
        "consume-remediation-receipt": cmd_consume_remediation_receipt,
        "init": cmd_init,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

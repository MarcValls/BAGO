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
_INDEPENDENT_REVIEW_CONTRACT = "bago.independent-review.v1"


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


def _has_current_protected_receipt(state: dict[str, Any], fp: dict[str, Any]) -> bool:
    receipt = state.get("protected_receipt")
    if not isinstance(receipt, dict) or fp.get("dirty"):
        return False
    if receipt.get("candidate_sha") != fp.get("commit") or receipt.get("package_sha256") is None:
        return False
    try:
        package = Path(str(receipt["package"]))
        verification = _load_json_object(Path(str(receipt["receipt"])), "verification receipt")
        if _sha_file(package) != receipt["package_sha256"]:
            return False
        if _remediation_candidate(package) != fp.get("commit"):
            return False
        recalculated = _verify_remediation_package(package)
        if receipt.get("receipt_sha256") != _sha_file(Path(str(receipt["receipt"]))):
            return False
        verified = (
            verification.get("contract") == _REMEDIATION_RECEIPT_CONTRACT
            and verification.get("result") == "PASS"
            and verification.get("package") == package.name
            and verification.get("package_sha256") == receipt["package_sha256"]
            and all(verification.get(key) == recalculated.get(key) for key in ("contract", "result", "package", "package_sha256"))
        )
        review_path = Path(str(receipt["review"]))
        review = _load_json_object(review_path, "independent review receipt")
        return verified and (
            review.get("contract") == _INDEPENDENT_REVIEW_CONTRACT
            and review.get("result") == "PASS"
            and isinstance(review.get("reviewer"), str)
            and bool(review["reviewer"].strip())
            and review.get("candidate_sha") == fp.get("commit")
            and review.get("package_sha256") == receipt["package_sha256"]
            and receipt.get("review_sha256") == _sha_file(review_path)
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
    has_receipt = _has_current_protected_receipt(state, fp)
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
            raise ValueError(f"{target} requires --review with an independent review receipt")
        review = _load_json_object(Path(args.review).resolve(), "independent review receipt")
        if review.get("contract") != _INDEPENDENT_REVIEW_CONTRACT or review.get("result") != "PASS":
            raise ValueError("independent review receipt does not report PASS under the required contract")
        if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
            raise ValueError("independent review receipt has no reviewer identity")
        if review.get("candidate_sha") != candidate or review.get("package_sha256") != package_sha:
            raise ValueError("independent review receipt is not bound to this candidate and package")
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
    receipt_parser.add_argument("--review", required=True, help="Independent review JSON receipt")

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

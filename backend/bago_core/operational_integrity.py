"""Cross-domain operational integrity contracts for BAGO.

These objects govern claims and closure; they do not execute product actions.
"""

from __future__ import annotations

import json
import hashlib
import re
import shlex
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Mapping


LIFECYCLE = ("PROPOSED", "PREPARED", "EXECUTED", "VERIFIED", "VALIDATED")
GATE_STATES = {"PASS", "FAIL", "NOT_RUN", "BLOCKED"}


@dataclass(frozen=True)
class CandidateIdentity:
    sha: str
    branch: str
    remote: str
    upstream: str = ""
    dirty: bool = False
    worktree_sha256: str = ""

    @property
    def immutable(self) -> bool:
        sha_ok = bool(re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", self.sha))
        worktree_ok = not self.worktree_sha256 or bool(re.fullmatch(r"[0-9a-fA-F]{64}", self.worktree_sha256))
        remote_ok = bool(
            re.match(r"^(?:https?://|ssh://|git@)[^\s]+$", self.remote)
            or re.match(r"^local-only:[^\r\n]+$", self.remote)
        )
        return bool(sha_ok and self.branch.strip() and remote_ok and worktree_ok and not self.dirty)


@dataclass(frozen=True)
class EvidenceRecord:
    claim: str
    action: str
    artifacts: tuple[str, ...]
    command: tuple[str, ...] = ()
    exit_code: int | None = None
    timestamp: str = ""
    candidate: CandidateIdentity | None = None
    artifact_sha256: tuple[str, ...] = ()
    receipt_id: str = ""
    gate_receipt: str = ""


class EvidencePolicy:
    @staticmethod
    def material(record: EvidenceRecord) -> bool:
        try:
            timestamp = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
            timestamp_ok = timestamp.tzinfo is not None
        except (TypeError, ValueError):
            timestamp_ok = False
        if (
            not record.action.strip()
            or not record.command
            or record.exit_code != 0
            or not record.receipt_id.strip()
            or not record.gate_receipt.strip()
            or not timestamp_ok
            or not record.artifacts
            or len(record.artifact_sha256) != len(record.artifacts)
            or record.candidate is None
            or not record.candidate.immutable
        ):
            return False
        for artifact, expected in zip(record.artifacts, record.artifact_sha256):
            path = Path(artifact)
            if not path.is_file() or not expected:
                return False
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest.casefold() != expected.casefold():
                return False
        # La política transversal no puede ser más débil que el ledger.
        # Revalida el recibo contra el Git actual y todos los repositorios que
        # participaron en el gate; un EvidenceRecord sintético no basta.
        try:
            receipt = Path(record.gate_receipt).resolve()
            repo = receipt.parents[3]
            from bago_core.claim_evidence import evidence_from_gate

            claim = SimpleNamespace(
                claim=record.claim,
                command=shlex.join(record.command),
                artifacts=list(record.artifacts),
            )
            derived = evidence_from_gate(repo, claim, receipt)
        except (ImportError, IndexError, OSError, ValueError):
            return False
        return bool(
            derived.claim == record.claim
            and derived.action == record.action
            and derived.artifacts == record.artifacts
            and derived.command == record.command
            and derived.exit_code == record.exit_code
            and derived.timestamp == record.timestamp
            and derived.candidate == record.candidate
            and derived.artifact_sha256 == record.artifact_sha256
            and derived.receipt_id == record.receipt_id
            and Path(derived.gate_receipt).resolve() == receipt
        )


class TruthPolicy:
    @staticmethod
    def can_claim_verified(record: EvidenceRecord) -> bool:
        return EvidencePolicy.material(record)

    @staticmethod
    def can_claim_validated(record: EvidenceRecord, *, closure_complete: bool, independent_review: bool) -> bool:
        return (
            TruthPolicy.can_claim_verified(record)
            and closure_complete
            and independent_review
            and record.candidate is not None
            and record.candidate.immutable
        )


class StateTransitionPolicy:
    @staticmethod
    def permits(current: str, target: str, *, evidence: EvidenceRecord | None = None, closure_complete: bool = False, independent_review: bool = False) -> bool:
        current = current.upper()
        target = target.upper()
        if current not in LIFECYCLE or target not in LIFECYCLE:
            return False
        if LIFECYCLE.index(target) > LIFECYCLE.index(current) + 1:
            return False
        if target == "VERIFIED":
            return evidence is not None and TruthPolicy.can_claim_verified(evidence)
        if target == "VALIDATED":
            return evidence is not None and TruthPolicy.can_claim_validated(
                evidence,
                closure_complete=closure_complete,
                independent_review=independent_review,
            )
        return True


@dataclass
class GateRegistry:
    required: dict[str, str] = field(default_factory=dict)

    def set(self, name: str, status: str) -> None:
        normalized = status.upper()
        if normalized not in GATE_STATES:
            raise ValueError(f"invalid gate state: {status}")
        self.required[name] = normalized

    def complete(self) -> bool:
        return bool(self.required) and all(status == "PASS" for status in self.required.values())


@dataclass
class ClosureContract:
    findings: dict[str, str]

    def close(self, finding: str) -> None:
        if finding not in self.findings:
            raise KeyError(finding)
        self.findings[finding] = "CLOSED"

    def complete(self) -> bool:
        return bool(self.findings) and all(value == "CLOSED" for value in self.findings.values())


class ConflictDetector:
    @staticmethod
    def detect(sources: Mapping[str, Mapping[str, object]], fields: Iterable[str]) -> list[dict]:
        conflicts = []
        for field_name in fields:
            values = {source: data.get(field_name) for source, data in sources.items() if field_name in data}
            distinct = {json.dumps(value, sort_keys=True, default=str) for value in values.values()}
            if len(distinct) > 1:
                conflicts.append({"field": field_name, "values": values})
        return conflicts


class IndependentReviewPolicy:
    @staticmethod
    def required(*, target_state: str, high_severity: bool = False) -> bool:
        return high_severity or target_state.upper() == "VALIDATED"


class AuditTrail:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **dict(event),
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def record_to_dict(record: EvidenceRecord) -> dict:
    return asdict(record)

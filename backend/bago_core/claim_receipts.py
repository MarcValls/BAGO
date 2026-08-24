"""Append-only persistence and strict parsing for claim evidence receipts."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from bago_core.operational_integrity import CandidateIdentity, EvidenceRecord


class ClaimReceiptStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, claim_id: str, evidence: EvidenceRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"claim_id": claim_id, "evidence": asdict(evidence)}, ensure_ascii=False) + "\n")

    def latest(self, claim_id: str) -> EvidenceRecord | None:
        if not self.path.exists():
            return None
        found: EvidenceRecord | None = None
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row.get("claim_id") != claim_id:
                    continue
                raw = row["evidence"]
                candidate = CandidateIdentity(**raw["candidate"]) if raw.get("candidate") else None
                found = EvidenceRecord(
                    claim=raw["claim"], action=raw["action"], artifacts=tuple(raw.get("artifacts", ())),
                    command=tuple(raw.get("command", ())), exit_code=raw.get("exit_code"),
                    timestamp=raw.get("timestamp", ""), candidate=candidate,
                    artifact_sha256=tuple(raw.get("artifact_sha256", ())), receipt_id=raw.get("receipt_id", ""),
                    gate_receipt=raw.get("gate_receipt", ""),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"claim_receipts.jsonl corrupt at line {line_number}: {exc}") from exc
        return found

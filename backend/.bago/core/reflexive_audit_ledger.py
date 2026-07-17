#!/usr/bin/env python3
"""Append-only evidence ledger for Reflexive Interpreter analyses."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class ReflexiveAuditLedger:
    """Persist Reflexive Interpreter analyses as evidence records."""

    def __init__(self, state_root: str | Path) -> None:
        self.state_root = Path(state_root)
        self.evidence_dir = self.state_root / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.evidence_dir / "reflexive_interpretations.jsonl"

    def append(
        self,
        *,
        session_id: str,
        provider: str,
        model: str,
        receipt_id: str,
        analysis: Mapping[str, Any],
        response_content: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        response_text = response_content or ""
        record = {
            "audit_id": "RA-" + uuid.uuid4().hex[:12],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "provider": provider,
            "model": model,
            "receipt_id": receipt_id,
            "question_id": analysis.get("question_id", ""),
            "intent": analysis.get("intent", ""),
            "confidence": analysis.get("confidence", 0.0),
            "analysis": dict(analysis),
            "response_sha256": hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
            "response_excerpt": response_text[:1000],
            "metadata": dict(metadata or {}),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return {
            "audit_id": record["audit_id"],
            "path": str(self.path),
            "receipt_id": receipt_id,
            "question_id": record["question_id"],
        }

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-max(1, int(limit or 1)) :]

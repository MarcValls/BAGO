#!/usr/bin/env python3
"""FASE 12.8 -- evidence gate tests.

Exercises call_with_evidence() against every real translator piece and
verifies the JSONL ledger is written with the contract fields.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure shared/base is on sys.path for direct ir_types imports in tests.
sys.path.insert(0, str(Path(os.environ.get("ProgramData", r"C:\ProgramData"))
                       / "BAGO" / "pieces" / "translators" / "shared" / "base"))

from bago_core.translators.evidence_gate import (  # noqa: E402
    call_with_evidence, evidence_path, last_evidence,
)
from bago_core.translators import list_translators  # noqa: E402
from ir_types import IRConversation, IRMessage  # type: ignore  # noqa: E402


def _make_conv(text: str = "hola") -> IRConversation:
    return IRConversation(
        messages=[IRMessage(id="m1", role="user",
                            parts=[{"type": "text", "text": text}])],
        model_hint="gpt-4o",
    )


class EvidenceGateTests(unittest.TestCase):
    def test_all_real_pieces_roundtrip(self):
        pieces = [p["piece_id"] for p in list_translators()
                  if p["piece_id"] != "translator.shared.base"]
        self.assertGreaterEqual(len(pieces), 4, "expected >=4 real translator pieces")
        with tempfile.TemporaryDirectory() as tmp:
            for pid in pieces:
                with self.subTest(piece=pid):
                    result = call_with_evidence(pid, _make_conv(), base_path=tmp)
                    self.assertTrue(result["ok"], msg=result)
                    ev = result["evidence"]
                    self.assertEqual(ev["piece_id"], pid)
                    self.assertTrue(ev["request_hash"].startswith("sha256:"))
                    self.assertTrue(ev["response_hash"].startswith("sha256:"))
                    self.assertIsInstance(ev["latency_ms"], int)
                    self.assertGreaterEqual(ev["latency_ms"], 0)
                    # ledger was written
                    self.assertTrue(evidence_path(base_path=tmp).exists())

    def test_ledger_tail_returns_most_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(3):
                r = call_with_evidence("translator.openai.gpt-4o",
                                       _make_conv(), base_path=tmp)
                self.assertTrue(r["ok"])
            tail = last_evidence("translator.openai.gpt-4o", base_path=tmp, limit=3)
            self.assertEqual(len(tail), 3)
            self.assertEqual(tail[-1]["piece_id"], "translator.openai.gpt-4o")

    def test_unknown_piece(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = call_with_evidence("translator.unknown", _make_conv(), base_path=tmp)
            self.assertFalse(r["ok"])
            self.assertIn("piece not found", r.get("error", ""))


if __name__ == "__main__":
    unittest.main()

"""Tests for the BAGO Code Forge 3B evidence bundle builder (step 16)."""
from __future__ import annotations

import json
import unittest
from typing import Iterable

from bago_core.codegen.code_verdict import (
    CodeVerdict,
    REASON_ACCEPTED,
    REASON_CONTRACT_REFUSED,
    REASON_GENERATOR_CRASHED,
    REASON_MAX_ATTEMPTS_EXCEEDED,
    REASON_PATCH_PARSE_FAILED,
    REASON_UNSAFE_MODE,
    VERDICT_ACCEPTED,
    VERDICT_NEEDS_REPAIR,
    VERDICT_NEEDS_REVIEW,
    VERDICT_REJECTED,
    derive_code_verdict,
)
from bago_core.codegen.evidence_builder import (
    BUNDLE_VERSION,
    EvidenceBundle,
    LIMIT_GENERATOR_CRASHED,
    LIMIT_PARSE_FAILED,
    LIMIT_PIPELINE_PARTIAL,
    LIMIT_REVIEW_ONLY,
    LIMIT_SAFE_MODE,
    build_evidence_bundle,
    bundle_from_repair_verdict,
    bundle_to_audit_record,
)
from bago_core.codegen.repair_loop import (
    RepairAttempt,
    RepairFeedback,
    RepairVerdict,
    STATUS_ACCEPTED,
    STATUS_REJECTED_MAX_ATTEMPTS,
    STATUS_REJECTED_PARSE_FAILED,
    STATUS_REJECTED_REFUSED,
    STATUS_REJECTED_UNRECOVERABLE,
)
from bago_core.codegen.task_classifier import CodeTaskClassification
from bago_core.codegen.task_compiler import compile_code_task
from bago_core.validation.validation_pipeline import (
    MODE_APPLY,
    MODE_AUTONOMOUS,
    MODE_SAFE,
    MODE_STAGED,
    PipelineVerdict,
)
from bago_core.validation.validation_result import (
    GATE_IMPORTS,
    GATE_LINT,
    GATE_SYNTAX,
    GateResult,
    ValidationResult,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classification() -> CodeTaskClassification:
    return CodeTaskClassification(
        kind="modify",
        confidence=0.9,
        reasons=("modify_hint",),
        target_files=("src/a.py",),
        is_code_request=True,
    )


def _contract() -> object:
    contract = compile_code_task(
        _classification(),
        objective="tighten a.py",
        allowed_files=["src/a.py"],
    )
    return contract


def _passed_verdict() -> PipelineVerdict:
    return PipelineVerdict(
        mode=MODE_APPLY,
        results={
            "python": ValidationResult(
                language="python",
                gate_results=(
                    GateResult(GATE_SYNTAX, ValidationStatus.PASSED, message="ok"),
                ),
                overall_status=ValidationStatus.PASSED,
            ),
        },
        overall_status=ValidationStatus.PASSED,
    )


def _failed_verdict() -> PipelineVerdict:
    return PipelineVerdict(
        mode=MODE_APPLY,
        results={
            "python": ValidationResult(
                language="python",
                gate_results=(
                    GateResult(
                        GATE_LINT, ValidationStatus.FAILED,
                        code="LINT_REJECTED", message="unused import",
                    ),
                    GateResult(
                        GATE_SYNTAX, ValidationStatus.PASSED, message="ok",
                    ),
                ),
                overall_status=ValidationStatus.FAILED,
                overall_code="LINT_REJECTED",
            ),
        },
        overall_status=ValidationStatus.FAILED,
        overall_code="LINT_REJECTED",
    )


def _accepted_repair() -> RepairVerdict:
    return RepairVerdict(
        status=STATUS_ACCEPTED,
        attempts=(
            RepairAttempt(
                index=1,
                prompt_kind="initial",
                raw_output="",
                verdict=_passed_verdict(),
            ),
        ),
        final_verdict=_passed_verdict(),
    )


def _rejected_repair() -> RepairVerdict:
    return RepairVerdict(
        status=STATUS_REJECTED_MAX_ATTEMPTS,
        attempts=(
            RepairAttempt(
                index=1,
                prompt_kind="initial",
                raw_output="",
                verdict=_failed_verdict(),
                feedback=RepairFeedback(
                    attempt=1,
                    maximum_attempts=3,
                    failing_gate=GATE_LINT,
                    failing_code="LINT_REJECTED",
                    failing_message="unused import",
                    offending_path="src/a.py",
                    offending_line=1,
                    offending_excerpt="import unused",
                ),
            ),
        ),
        final_verdict=_failed_verdict(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class BuildEvidenceBundleTests(unittest.TestCase):
    def test_accepted_bundle_is_json_safe(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_APPLY)
        bundle = build_evidence_bundle(
            verdict=verdict,
            contract=_contract(),
            repair=_accepted_repair(),
            duration_ms=42,
            created_at=1700000000.0,
        )
        self.assertIsInstance(bundle, EvidenceBundle)
        self.assertEqual(bundle.bundle_version, BUNDLE_VERSION)
        self.assertEqual(bundle.verdict.verdict, VERDICT_ACCEPTED)
        # The bundle must round-trip through json without error.
        payload = bundle.to_dict()
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["task_id"], bundle.task_id)
        self.assertEqual(decoded["verdict"]["verdict"], VERDICT_ACCEPTED)
        self.assertEqual(decoded["duration_ms"], 42)

    def test_failed_bundle_records_failure_codes_and_gates(self) -> None:
        verdict = derive_code_verdict(_rejected_repair(), mode=MODE_APPLY)
        bundle = build_evidence_bundle(
            verdict=verdict,
            contract=_contract(),
            repair=_rejected_repair(),
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.verdict.verdict, VERDICT_NEEDS_REPAIR)
        self.assertIn("LINT_REJECTED", bundle.verdict.failure_codes)
        self.assertIn(GATE_LINT, bundle.verdict.failure_gates)
        # The validation block exposes every gate in canonical order.
        gate_ids = [g["gate_id"] for g in bundle.to_dict()["validation"]["gates"]]
        self.assertEqual(gate_ids[0], GATE_LINT)
        self.assertIn(GATE_SYNTAX, gate_ids)

    def test_safe_mode_emits_safe_mode_limitation(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_SAFE)
        bundle = build_evidence_bundle(
            verdict=verdict,
            contract=_contract(),
            repair=_accepted_repair(),
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.verdict.can_apply, False)
        self.assertIn(LIMIT_SAFE_MODE, bundle.limitations)

    def test_apply_mode_does_not_emit_safe_mode_limitation(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_APPLY)
        bundle = build_evidence_bundle(
            verdict=verdict,
            contract=_contract(),
            repair=_accepted_repair(),
            created_at=1700000000.0,
        )
        self.assertTrue(bundle.verdict.can_apply)
        self.assertNotIn(LIMIT_SAFE_MODE, bundle.limitations)

    def test_rejected_with_attached_patches_flags_partial(self) -> None:
        repair = RepairVerdict(
            status=STATUS_REJECTED_PARSE_FAILED,
            attempts=(
                RepairAttempt(
                    index=1,
                    prompt_kind="initial",
                    raw_output="--- a/src/a.py\n+++ b/src/a.py\n",
                    parse_error="malformed_hunk_header",
                ),
            ),
        )
        verdict = derive_code_verdict(repair, mode=MODE_APPLY)
        bundle = build_evidence_bundle(
            verdict=verdict,
            repair=repair,
            created_at=1700000000.0,
        )
        self.assertIn(LIMIT_PARSE_FAILED, bundle.limitations)

    def test_generator_crashed_flags_review_only(self) -> None:
        verdict = CodeVerdict(
            verdict=VERDICT_NEEDS_REVIEW,
            reason=REASON_GENERATOR_CRASHED,
            mode=MODE_AUTONOMOUS,
            repair_status=STATUS_REJECTED_UNRECOVERABLE,
        )
        bundle = build_evidence_bundle(
            verdict=verdict,
            attempts=(),
            created_at=1700000000.0,
        )
        self.assertIn(LIMIT_GENERATOR_CRASHED, bundle.limitations)
        self.assertIn(LIMIT_REVIEW_ONLY, bundle.limitations)

    def test_unknown_mode_carries_unsafe_reason(self) -> None:
        # ``derive_code_verdict`` is the normal entry point; calling
        # ``build_evidence_bundle`` directly with a verdict that has an
        # unknown mode still produces a usable bundle.
        verdict = CodeVerdict(
            verdict=VERDICT_REJECTED,
            reason=REASON_UNSAFE_MODE,
            mode="BOGUS",
            repair_status="",
        )
        bundle = build_evidence_bundle(
            verdict=verdict,
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.verdict.reason, REASON_UNSAFE_MODE)

    def test_refused_contract_surfaces_limitation(self) -> None:
        repair = RepairVerdict(
            status=STATUS_REJECTED_REFUSED,
            attempts=(),
            refusal_reason="classifier_blocked",
        )
        verdict = derive_code_verdict(repair, mode=MODE_AUTONOMOUS)
        bundle = build_evidence_bundle(
            verdict=verdict,
            repair=repair,
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.verdict.verdict, VERDICT_NEEDS_REVIEW)
        self.assertIn(LIMIT_REVIEW_ONLY, bundle.limitations)

    def test_task_id_uses_contract_when_available(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_APPLY)
        contract = _contract()
        bundle = build_evidence_bundle(
            verdict=verdict,
            contract=contract,
            repair=_accepted_repair(),
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.task_id, contract.task_id)

    def test_task_id_falls_back_to_verdict_extra(self) -> None:
        verdict = CodeVerdict(
            verdict=VERDICT_REJECTED,
            reason="pipeline_failed",
            mode=MODE_APPLY,
            extra={"task_id": "PIPE-123"},
        )
        bundle = build_evidence_bundle(
            verdict=verdict,
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.task_id, "PIPE-123")

    def test_duration_ms_sums_attempt_durations(self) -> None:
        attempts = (
            RepairAttempt(
                index=1, prompt_kind="initial", raw_output="",
                verdict=PipelineVerdict(
                    mode=MODE_APPLY,
                    results={},
                    overall_status=ValidationStatus.PASSED,
                        summary={"duration_ms": 10},
                ),
            ),
            RepairAttempt(
                index=2, prompt_kind="repair", raw_output="",
                verdict=PipelineVerdict(
                    mode=MODE_APPLY,
                    results={},
                    overall_status=ValidationStatus.PASSED,
                        summary={"duration_ms": 15},
                ),
            ),
        )
        verdict = derive_code_verdict(
            RepairVerdict(status=STATUS_ACCEPTED, attempts=attempts,
                          final_verdict=attempts[-1].verdict),
            mode=MODE_APPLY,
        )
        bundle = build_evidence_bundle(
            verdict=verdict,
            attempts=attempts,
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.duration_ms, 25)

    def test_default_duration_is_zero_when_attempts_lack_verdict(self) -> None:
        attempts = (RepairAttempt(index=1, prompt_kind="initial", raw_output=""),)
        verdict = derive_code_verdict(
            RepairVerdict(status=STATUS_REJECTED_REFUSED, attempts=attempts),
            mode=MODE_AUTONOMOUS,
        )
        bundle = build_evidence_bundle(
            verdict=verdict,
            attempts=attempts,
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.duration_ms, 0)

    def test_attempts_preserve_order(self) -> None:
        attempts = (
            RepairAttempt(index=1, prompt_kind="initial", raw_output="A"),
            RepairAttempt(index=2, prompt_kind="repair", raw_output="B"),
            RepairAttempt(index=3, prompt_kind="repair", raw_output="C"),
        )
        verdict = derive_code_verdict(
            RepairVerdict(status=STATUS_REJECTED_MAX_ATTEMPTS, attempts=attempts),
            mode=MODE_AUTONOMOUS,
        )
        bundle = build_evidence_bundle(
            verdict=verdict,
            attempts=attempts,
            created_at=1700000000.0,
        )
        rendered = bundle.to_dict()["attempts"]
        self.assertEqual([a["index"] for a in rendered], [1, 2, 3])
        self.assertEqual([a["prompt_kind"] for a in rendered], ["initial", "repair", "repair"])

    def test_audit_record_adds_attempt_count(self) -> None:
        verdict = derive_code_verdict(_rejected_repair(), mode=MODE_APPLY)
        bundle = build_evidence_bundle(
            verdict=verdict,
            contract=_contract(),
            repair=_rejected_repair(),
            created_at=1700000000.0,
        )
        record = bundle_to_audit_record(bundle)
        self.assertEqual(record["attempt_count"], 1)
        self.assertEqual(record["task_id"], bundle.task_id)

    def test_bundle_from_repair_verdict_runs_end_to_end(self) -> None:
        bundle = bundle_from_repair_verdict(
            _accepted_repair(),
            mode=MODE_APPLY,
            contract=_contract(),
            objective="tighten a.py",
            duration_ms=5,
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.verdict.verdict, VERDICT_ACCEPTED)
        self.assertEqual(bundle.verdict.can_apply, True)

    def test_bundle_from_repair_verdict_unknown_mode(self) -> None:
        bundle = bundle_from_repair_verdict(
            _accepted_repair(),
            mode="BOGUS",
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.verdict.reason, REASON_UNSAFE_MODE)

    def test_bundle_from_repair_verdict_missing_contract(self) -> None:
        bundle = bundle_from_repair_verdict(
            _accepted_repair(),
            mode=MODE_APPLY,
            objective="tighten a.py",
            created_at=1700000000.0,
        )
        self.assertTrue(bundle.extra.get("missing_contract"))
        self.assertEqual(bundle.extra.get("objective"), "tighten a.py")

    def test_extra_is_optional(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_APPLY)
        bundle = build_evidence_bundle(
            verdict=verdict,
            created_at=1700000000.0,
        )
        self.assertEqual(bundle.extra, {})

    def test_to_dict_has_required_top_level_keys(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_APPLY)
        bundle = build_evidence_bundle(
            verdict=verdict,
            contract=_contract(),
            repair=_accepted_repair(),
            created_at=1700000000.0,
        )
        keys = set(bundle.to_dict().keys())
        for required in (
            "bundle_version", "task_id", "created_at", "duration_ms",
            "contract", "verdict", "attempts", "validation", "limitations",
        ):
            self.assertIn(required, keys)


if __name__ == "__main__":
    unittest.main()

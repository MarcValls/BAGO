"""Tests for the BAGO Code Forge 3B high-level code verdict (step 13)."""
from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from bago_core.codegen.code_verdict import (
    ALL_VERDICTS,
    CodeVerdict,
    REASON_ACCEPTED,
    REASON_CONTRACT_REFUSED,
    REASON_GENERATOR_CRASHED,
    REASON_MAX_ATTEMPTS_EXCEEDED,
    REASON_PATCH_PARSE_FAILED,
    REASON_PIPELINE_REJECTED,
    REASON_UNKNOWN_REPAIR_STATUS,
    REASON_UNSAFE_MODE,
    VERDICT_ACCEPTED,
    VERDICT_NEEDS_REPAIR,
    VERDICT_NEEDS_REVIEW,
    VERDICT_REJECTED,
    derive_code_verdict,
    verdict_collect_failure_codes,
    verdict_from_pipeline_only,
    verdict_is_review_only,
    verdict_is_safe_to_apply,
)
from bago_core.codegen.repair_loop import (
    RepairAttempt,
    RepairVerdict,
    STATUS_ACCEPTED,
    STATUS_REJECTED_MAX_ATTEMPTS,
    STATUS_REJECTED_PARSE_FAILED,
    STATUS_REJECTED_REFUSED,
    STATUS_REJECTED_UNRECOVERABLE,
)
from bago_core.validation.validation_pipeline import (
    MODE_APPLY,
    MODE_AUTONOMOUS,
    MODE_SAFE,
    MODE_STAGED,
    PipelineVerdict,
)
from bago_core.validation.validation_result import (
    GATE_SYNTAX,
    GateResult,
    ValidationResult,
    ValidationStatus,
)


def _empty_repair(status: str) -> RepairVerdict:
    return RepairVerdict(status=status, attempts=())


def _accepted_repair() -> RepairVerdict:
    return RepairVerdict(
        status=STATUS_ACCEPTED,
        attempts=(
            RepairAttempt(
                index=1, prompt_kind="initial", raw_output="",
            ),
        ),
        final_verdict=PipelineVerdict(
            mode=MODE_STAGED,
            results={
                "python": ValidationResult(
                    language="python",
                    gate_results=(
                        GateResult(
                            GATE_SYNTAX,
                            ValidationStatus.PASSED,
                            message="ok",
                        ),
                    ),
                    overall_status=ValidationStatus.PASSED,
                    overall_code="",
                ),
            },
            overall_status=ValidationStatus.PASSED,
            overall_code="",
        ),
    )


def _failed_repair(
    status: str = STATUS_REJECTED_MAX_ATTEMPTS,
) -> RepairVerdict:
    return RepairVerdict(
        status=status,
        attempts=(
            RepairAttempt(
                index=1, prompt_kind="initial", raw_output="",
                verdict=PipelineVerdict(
                    mode=MODE_STAGED,
                    results={
                        "python": ValidationResult(
                            language="python",
                            gate_results=(
                                GateResult(
                                    GATE_SYNTAX,
                                    ValidationStatus.FAILED,
                                    code="FORMATTER_REJECTED",
                                    message="would reformat line 12",
                                ),
                            ),
                            overall_status=ValidationStatus.FAILED,
                            overall_code="FORMATTER_REJECTED",
                        ),
                    },
                    overall_status=ValidationStatus.FAILED,
                    overall_code="FORMATTER_REJECTED",
                ),
            ),
            RepairAttempt(
                index=2, prompt_kind="repair", raw_output="",
                verdict=PipelineVerdict(
                    mode=MODE_STAGED,
                    results={
                        "python": ValidationResult(
                            language="python",
                            gate_results=(
                                GateResult(
                                    GATE_SYNTAX,
                                    ValidationStatus.FAILED,
                                    code="LINT_REJECTED",
                                    message="unused import",
                                ),
                            ),
                            overall_status=ValidationStatus.FAILED,
                            overall_code="LINT_REJECTED",
                        ),
                    },
                    overall_status=ValidationStatus.FAILED,
                    overall_code="LINT_REJECTED",
                ),
            ),
        ),
        final_verdict=PipelineVerdict(
            mode=MODE_STAGED,
            results={
                "python": ValidationResult(
                    language="python",
                    gate_results=(
                        GateResult(
                            GATE_SYNTAX,
                            ValidationStatus.FAILED,
                            code="LINT_REJECTED",
                            message="unused import",
                        ),
                    ),
                    overall_status=ValidationStatus.FAILED,
                    overall_code="LINT_REJECTED",
                ),
            },
            overall_status=ValidationStatus.FAILED,
            overall_code="LINT_REJECTED",
        ),
    )


class DeriveCodeVerdictTests(unittest.TestCase):
    def test_accepted_in_safe_mode_is_not_applyable(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_SAFE)
        self.assertEqual(verdict.verdict, VERDICT_ACCEPTED)
        self.assertEqual(verdict.reason, REASON_ACCEPTED)
        self.assertEqual(verdict.attempt_count, 1)
        self.assertFalse(verdict.can_apply)
        self.assertFalse(verdict_is_safe_to_apply(verdict))

    def test_accepted_in_apply_mode_is_applyable(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_APPLY)
        self.assertTrue(verdict.can_apply)
        self.assertTrue(verdict_is_safe_to_apply(verdict))

    def test_accepted_in_autonomous_mode_is_applyable(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_AUTONOMOUS)
        self.assertTrue(verdict.can_apply)

    def test_accepted_in_staged_mode_is_not_applyable(self) -> None:
        verdict = derive_code_verdict(_accepted_repair(), mode=MODE_STAGED)
        self.assertTrue(verdict.accepted)
        self.assertFalse(verdict.can_apply)

    def test_max_attempts_yields_needs_repair(self) -> None:
        verdict = derive_code_verdict(
            _failed_repair(STATUS_REJECTED_MAX_ATTEMPTS),
            mode=MODE_STAGED,
        )
        self.assertEqual(verdict.verdict, VERDICT_NEEDS_REPAIR)
        self.assertEqual(verdict.reason, REASON_MAX_ATTEMPTS_EXCEEDED)
        self.assertEqual(verdict.attempt_count, 2)
        # Only the *final* attempt's failure code is reported — the
        # loop's job is to drive the patch to a green state, not to
        # keep a per-attempt scoreboard.
        self.assertIn("LINT_REJECTED", verdict.failure_codes)
        self.assertIn("syntax", verdict.failure_gates)
        self.assertFalse(verdict_is_review_only(verdict))

    def test_parse_failed_yields_needs_repair(self) -> None:
        verdict = derive_code_verdict(
            _failed_repair(STATUS_REJECTED_PARSE_FAILED),
            mode=MODE_STAGED,
        )
        self.assertEqual(verdict.verdict, VERDICT_NEEDS_REPAIR)
        self.assertEqual(verdict.reason, REASON_PATCH_PARSE_FAILED)

    def test_refused_contract_yields_needs_review(self) -> None:
        verdict = derive_code_verdict(
            _empty_repair(STATUS_REJECTED_REFUSED),
            mode=MODE_STAGED,
        )
        self.assertEqual(verdict.verdict, VERDICT_NEEDS_REVIEW)
        self.assertEqual(verdict.reason, REASON_CONTRACT_REFUSED)
        self.assertTrue(verdict_is_review_only(verdict))
        self.assertFalse(verdict.can_apply)

    def test_generator_crash_yields_needs_review(self) -> None:
        verdict = derive_code_verdict(
            _empty_repair(STATUS_REJECTED_UNRECOVERABLE),
            mode=MODE_STAGED,
        )
        self.assertEqual(verdict.verdict, VERDICT_NEEDS_REVIEW)
        self.assertEqual(verdict.reason, REASON_GENERATOR_CRASHED)
        self.assertTrue(verdict_is_review_only(verdict))

    def test_unknown_repair_status_yields_rejected(self) -> None:
        verdict = derive_code_verdict(
            _empty_repair("ZOMBIE_STATUS"),
            mode=MODE_STAGED,
        )
        self.assertEqual(verdict.verdict, VERDICT_REJECTED)
        self.assertEqual(verdict.reason, REASON_UNKNOWN_REPAIR_STATUS)
        self.assertTrue(verdict.rejected)

    def test_unknown_mode_yields_rejected(self) -> None:
        verdict = derive_code_verdict(
            _accepted_repair(),
            mode="WONKY",
        )
        self.assertEqual(verdict.verdict, VERDICT_REJECTED)
        self.assertEqual(verdict.reason, REASON_UNSAFE_MODE)
        self.assertFalse(verdict.can_apply)


class VerdictFromPipelineOnlyTests(unittest.TestCase):
    def test_accepted_pipeline_yields_accepted(self) -> None:
        pipeline = PipelineVerdict(
            mode=MODE_STAGED,
            results={},
            overall_status=ValidationStatus.PASSED,
            overall_code="",
        )
        verdict = verdict_from_pipeline_only(pipeline, mode=MODE_SAFE)
        self.assertEqual(verdict.verdict, VERDICT_ACCEPTED)
        self.assertEqual(verdict.attempt_count, 1)
        self.assertFalse(verdict.can_apply)

    def test_failed_pipeline_yields_rejected(self) -> None:
        pipeline = PipelineVerdict(
            mode=MODE_STAGED,
            results={
                "python": ValidationResult(
                    language="python",
                    gate_results=(
                        GateResult(
                            GATE_SYNTAX,
                            ValidationStatus.FAILED,
                            code="AST_PARSE",
                            message="expected ':'",
                        ),
                    ),
                    overall_status=ValidationStatus.FAILED,
                    overall_code="AST_PARSE",
                ),
            },
            overall_status=ValidationStatus.FAILED,
            overall_code="AST_PARSE",
        )
        verdict = verdict_from_pipeline_only(pipeline, mode=MODE_SAFE)
        self.assertEqual(verdict.verdict, VERDICT_REJECTED)
        self.assertEqual(verdict.reason, REASON_PIPELINE_REJECTED)
        self.assertIn("AST_PARSE", verdict.failure_codes)
        self.assertIn("syntax", verdict.failure_gates)


class CodeVerdictDataclassTests(unittest.TestCase):
    def test_verdict_is_frozen(self) -> None:
        v = CodeVerdict(verdict=VERDICT_ACCEPTED, reason=REASON_ACCEPTED)
        with self.assertRaises(FrozenInstanceError):
            v.verdict = VERDICT_REJECTED  # type: ignore[misc]

    def test_to_dict_is_json_safe(self) -> None:
        v = CodeVerdict(
            verdict=VERDICT_NEEDS_REPAIR,
            reason=REASON_MAX_ATTEMPTS_EXCEEDED,
            failure_codes=("X", "Y"),
            failure_gates=("syntax",),
        )
        d = v.to_dict()
        self.assertEqual(d["verdict"], VERDICT_NEEDS_REPAIR)
        self.assertEqual(d["failure_codes"], ["X", "Y"])
        self.assertEqual(d["failure_gates"], ["syntax"])
        # Tuples must round-trip as lists for json.dumps.
        import json
        json.dumps(d)

    def test_collect_failure_codes_returns_tuple(self) -> None:
        v = CodeVerdict(
            verdict=VERDICT_NEEDS_REPAIR,
            reason=REASON_PIPELINE_REJECTED,
            failure_codes=("A", "B", "A"),
        )
        # _collect_failure_codes returns the same tuple; downstream
        # code can dedupe but the verdict layer preserves order.
        codes = verdict_collect_failure_codes(v)
        self.assertEqual(codes, ("A", "B", "A"))

    def test_all_verdicts_constant_is_complete(self) -> None:
        self.assertEqual(
            ALL_VERDICTS,
            frozenset(
                {
                    VERDICT_ACCEPTED,
                    VERDICT_NEEDS_REPAIR,
                    VERDICT_NEEDS_REVIEW,
                    VERDICT_REJECTED,
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()

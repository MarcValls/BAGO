"""Tests for the BAGO Code Forge 3B repair loop (step 12)."""
from __future__ import annotations

import textwrap
import unittest
from typing import Mapping

from bago_core.codegen.context_builder import (
    CodeContext,
    CodeFileSummary,
    build_code_context,
)
from bago_core.codegen.patch_parser import (
    Hunk,
    HunkLine,
    Patch,
    parse_patch,
)
from bago_core.codegen.repair_loop import (
    DEFAULT_MAX_ATTEMPTS,
    RepairAttempt,
    RepairFeedback,
    RepairVerdict,
    STATUS_ACCEPTED,
    STATUS_REJECTED_MAX_ATTEMPTS,
    STATUS_REJECTED_PARSE_FAILED,
    STATUS_REJECTED_REFUSED,
    STATUS_REJECTED_UNRECOVERABLE,
    run_repair_loop,
)
from bago_core.codegen.task_classifier import classify_code_request
from bago_core.codegen.task_compiler import compile_code_task
from bago_core.validation.language_adapter import FileToValidate
from bago_core.validation.validation_pipeline import (
    AdapterRegistry,
    PipelineVerdict,
    validate_patch,
)
from bago_core.validation.validation_result import (
    GATE_SYNTAX,
    ValidationStatus,
)


VALID_BODY = textwrap.dedent(
    """\
    def greet(name: str) -> str:
        return f"hi {name}"
    """
)


def _build_context(target_body: str = VALID_BODY, target_path: str = "src/a.py") -> CodeContext:
    classification = classify_code_request(
        f"modify file {target_path}",
    )
    contract = compile_code_task(
        classification,
        objective="Refine greet() to add a greeting prefix.",
        allowed_files=[target_path],
    )
    summary = CodeFileSummary(
        path=target_path, language="python", exists=True, body=target_body,
    )
    return CodeContext(
        contract=contract,
        target_summaries=(summary,),
        related_tests=(),
        similar_files=(),
    )


def _make_unified_diff(old_body: str, new_body: str, path: str = "src/a.py") -> str:
    """Tiny helper to build a single-hunk unified diff for tests."""
    old_lines = old_body.splitlines() or [""]
    new_lines = new_body.splitlines() or [""]
    diff = [
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1,{len(old_lines)} +1,{len(new_lines)} @@",
    ]
    for line in old_lines:
        diff.append(f"-{line}")
    for line in new_lines:
        diff.append(f"+{line}")
    return "\n".join(diff) + "\n"


class _RecordingValidator:
    """Stub validator that lets tests script verdicts attempt-by-attempt."""

    def __init__(self, verdicts: list[PipelineVerdict]) -> None:
        self._verdicts = list(verdicts)
        self.calls: list[tuple[Mapping[str, FileToValidate], str]] = []

    def __call__(
        self, files: Mapping[str, FileToValidate], language: str
    ) -> PipelineVerdict:
        self.calls.append((dict(files), language))
        if not self._verdicts:
            return PipelineVerdict(
                mode="STAGED",
                results={},
                overall_status=ValidationStatus.FAILED,
                overall_code="verdict_exhausted",
            )
        return self._verdicts.pop(0)


def _accepted_verdict() -> PipelineVerdict:
    return PipelineVerdict(
        mode="STAGED",
        results={
            "python": _passing_python_result(),
        },
        overall_status=ValidationStatus.PASSED,
        overall_code="",
    )


def _failing_verdict(code: str = "FORMATTER_REJECTED") -> PipelineVerdict:
    from bago_core.validation.validation_result import (
        GateResult,
        ValidationResult,
    )
    return PipelineVerdict(
        mode="STAGED",
        results={
            "python": ValidationResult(
                language="python",
                gate_results=(
                    GateResult(
                        GATE_SYNTAX,
                        ValidationStatus.FAILED,
                        code=code,
                        message="bad syntax",
                    ),
                ),
                overall_status=ValidationStatus.FAILED,
                overall_code=code,
            ),
        },
        overall_status=ValidationStatus.FAILED,
        overall_code=code,
    )


def _passing_python_result():
    from bago_core.validation.validation_result import (
        GateResult,
        ValidationResult,
    )
    return ValidationResult(
        language="python",
        gate_results=(
            GateResult(GATE_SYNTAX, ValidationStatus.PASSED, message="ok"),
        ),
        overall_status=ValidationStatus.PASSED,
        overall_code="",
    )


class RepairLoopSmokeTests(unittest.TestCase):
    def test_initial_attempt_is_accepted(self) -> None:
        context = _build_context()
        diff = _make_unified_diff(VALID_BODY, "def greet(name: str) -> str:\n    return f'hi {name}!'\n")
        generator = lambda prompt: diff  # noqa: E731
        validator = _RecordingValidator([_accepted_verdict()])
        verdict = run_repair_loop(
            contract=context.contract,
            context=context,
            generator=generator,
            validator=validator,
        )
        self.assertEqual(verdict.status, STATUS_ACCEPTED)
        self.assertEqual(len(verdict.attempts), 1)
        self.assertTrue(verdict.attempts[0].accepted)
        self.assertEqual(verdict.attempts[0].prompt_kind, "initial")
        self.assertEqual(len(verdict.final_patches), 1)
        self.assertEqual(len(validator.calls), 1)

    def test_repair_passes_after_two_attempts(self) -> None:
        context = _build_context()
        diff = _make_unified_diff(
            VALID_BODY,
            "def greet(name: str) -> str:\n    return f'hello {name}'\n",
        )
        generator = lambda prompt: diff  # noqa: E731
        validator = _RecordingValidator([
            _failing_verdict("FORMATTER_REJECTED"),
            _accepted_verdict(),
        ])
        verdict = run_repair_loop(
            contract=context.contract,
            context=context,
            generator=generator,
            validator=validator,
        )
        self.assertEqual(verdict.status, STATUS_ACCEPTED)
        self.assertEqual(len(verdict.attempts), 2)
        self.assertEqual(verdict.attempts[1].prompt_kind, "repair")
        self.assertIsNotNone(verdict.attempts[1].feedback)
        self.assertEqual(verdict.attempts[1].feedback.failing_code, "FORMATTER_REJECTED")

    def test_max_attempts_yields_rejected(self) -> None:
        context = _build_context()
        diff = _make_unified_diff(
            VALID_BODY,
            "def greet(name: str) -> str:\n    return f'hi {name}'\n",
        )
        generator = lambda prompt: diff  # noqa: E731
        validator = _RecordingValidator([
            _failing_verdict("X"),
            _failing_verdict("X"),
            _failing_verdict("X"),
        ])
        verdict = run_repair_loop(
            contract=context.contract,
            context=context,
            generator=generator,
            validator=validator,
        )
        self.assertEqual(verdict.status, STATUS_REJECTED_MAX_ATTEMPTS)
        self.assertEqual(len(verdict.attempts), DEFAULT_MAX_ATTEMPTS)
        self.assertFalse(verdict.accepted)

    def test_refused_contract_short_circuits(self) -> None:
        context = _build_context()
        refused_contract = context.contract.__class__(
            task_id="CODE-X",
            operation="explain",
            language="unknown",
            objective="x",
            target_files=(),
            allowed_files=(),
            forbidden_paths=(),
            constraints=(),
            acceptance=(),
            refused=True,
            refusal_reason="policy:blocked",
        )
        generator_called = {"n": 0}

        def _gen(prompt):
            generator_called["n"] += 1
            return ""

        verdict = run_repair_loop(
            contract=refused_contract,
            context=context,
            generator=_gen,
            validator=_RecordingVerifier(),
        )
        self.assertEqual(verdict.status, STATUS_REJECTED_REFUSED)
        self.assertEqual(verdict.refusal_reason, "policy:blocked")
        self.assertEqual(generator_called["n"], 0)

    def test_parse_error_is_recorded_and_repaired(self) -> None:
        context = _build_context()
        diff = _make_unified_diff(
            VALID_BODY,
            "def greet(name: str) -> str:\n    return f'hi {name}'\n",
        )
        outputs = iter(["not a diff at all", diff])
        generator = lambda prompt: next(outputs)  # noqa: E731
        validator = _RecordingValidator([_accepted_verdict()])
        verdict = run_repair_loop(
            contract=context.contract,
            context=context,
            generator=generator,
            validator=validator,
        )
        self.assertEqual(verdict.status, STATUS_ACCEPTED)
        self.assertEqual(len(verdict.attempts), 2)
        self.assertNotEqual(verdict.attempts[0].parse_error, "")
        self.assertEqual(verdict.attempts[0].verdict, None)
        self.assertEqual(verdict.attempts[1].prompt_kind, "repair")

    def test_generator_crash_is_unrecoverable(self) -> None:
        context = _build_context()

        def _gen(prompt):
            raise RuntimeError("model offline")

        verdict = run_repair_loop(
            contract=context.contract,
            context=context,
            generator=_gen,
            validator=_RecordingVerifier(),
        )
        self.assertEqual(verdict.status, STATUS_REJECTED_UNRECOVERABLE)
        self.assertIn("generator_crashed", verdict.refusal_reason)

    def test_empty_generator_output_keeps_repairing(self) -> None:
        context = _build_context()
        diff = _make_unified_diff(
            VALID_BODY,
            "def greet(name: str) -> str:\n    return f'hi {name}'\n",
        )
        outputs = iter(["", diff])
        generator = lambda prompt: next(outputs)  # noqa: E731
        validator = _RecordingValidator([_accepted_verdict()])
        verdict = run_repair_loop(
            contract=context.contract,
            context=context,
            generator=generator,
            validator=validator,
        )
        self.assertEqual(verdict.status, STATUS_ACCEPTED)
        self.assertEqual(verdict.attempts[0].parse_error, "empty_patch")


class RepairLoopPromptShapeTests(unittest.TestCase):
    def test_prompts_contain_contract_and_feedback(self) -> None:
        context = _build_context()
        diff = _make_unified_diff(
            VALID_BODY,
            "def greet(name: str) -> str:\n    return f'hello {name}'\n",
        )
        captured: list[dict[str, object]] = []

        def _gen(prompt):
            captured.append(prompt)
            return diff

        validator = _RecordingValidator([
            _failing_verdict("FORMATTER_REJECTED"),
            _accepted_verdict(),
        ])
        run_repair_loop(
            contract=context.contract,
            context=context,
            generator=_gen,
            validator=validator,
        )
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0]["phase"], "initial")
        self.assertEqual(captured[1]["phase"], "repair")
        self.assertIn("feedback", captured[1])
        feedback = captured[1]["feedback"]
        self.assertEqual(feedback["failing_code"], "FORMATTER_REJECTED")
        self.assertEqual(feedback["attempt"], 1)
        self.assertEqual(feedback["maximum_attempts"], DEFAULT_MAX_ATTEMPTS)


class _RecordingVerifier:
    """Minimal validator that always reports the test as failed."""

    def __call__(self, files, language) -> PipelineVerdict:
        return _failing_verdict("VERIFIER_REJECTED")


class RepairLoopIntegrationTests(unittest.TestCase):
    """Smoke test that wires the loop with the real validation pipeline."""

    def test_loop_with_real_validator_accepts_clean_patch(self) -> None:
        context = _build_context()
        diff = _make_unified_diff(
            VALID_BODY,
            "def greet(name: str) -> str:\n    return f'hi {name}'\n",
        )
        registry = AdapterRegistry().with_adapter("python", _StubAdapter())
        generator = lambda prompt: diff  # noqa: E731

        def _validator(files, language):
            return validate_patch(
                registry=registry,
                files=tuple(files.values()),
                mode="STAGED",
            )

        verdict = run_repair_loop(
            contract=context.contract,
            context=context,
            generator=generator,
            validator=_validator,
        )
        self.assertEqual(verdict.status, STATUS_ACCEPTED)


class _StubAdapter:
    """A minimal adapter object that the real ``validate_patch`` accepts."""

    language = "python"
    supported_gates = (GATE_SYNTAX,)

    def __init__(self) -> None:
        from bago_core.validation.validation_result import (
            GateResult,
            ValidationResult,
        )
        self._passed = ValidationResult(
            language="python",
            gate_results=(
                GateResult(GATE_SYNTAX, ValidationStatus.PASSED, message="ok"),
            ),
            overall_status=ValidationStatus.PASSED,
            overall_code="",
        )

    def run(self, context) -> ValidationResult:  # type: ignore[override]
        return self._passed


if __name__ == "__main__":
    unittest.main()

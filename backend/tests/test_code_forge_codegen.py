"""End-to-end tests for the BAGO Code Forge 3B codegen pipeline.

Step 17 of the Code Forge plan. These tests wire the deterministic
pieces together (classifier -> compiler -> context builder -> repair
loop -> verdict -> evidence bundle) with a stubbed model and a stubbed
adapter. The model is the only non-deterministic part of the real
pipeline; replacing it with a deterministic ``Generator`` lets us
exercise every branch deterministically.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bago_core.codegen.code_verdict import (
    REASON_MAX_ATTEMPTS_EXCEEDED,
    VERDICT_ACCEPTED,
    VERDICT_NEEDS_REPAIR,
    derive_code_verdict,
)
from bago_core.codegen.context_builder import build_code_context
from bago_core.codegen.evidence_builder import (
    BUNDLE_VERSION,
    EvidenceBundle,
    LIMIT_SAFE_MODE,
    build_evidence_bundle,
    bundle_from_repair_verdict,
)
from bago_core.codegen.patch_parser import parse_patch
from bago_core.codegen.repair_loop import (
    STATUS_ACCEPTED,
    STATUS_REJECTED_MAX_ATTEMPTS,
    run_repair_loop,
)
from bago_core.codegen.task_classifier import classify_code_request
from bago_core.codegen.task_compiler import compile_code_task
from bago_core.validation.language_adapter import (
    FileToValidate,
    LanguageAdapter,
)
from bago_core.validation.validation_pipeline import (
    AdapterRegistry,
    MODE_APPLY,
    MODE_AUTONOMOUS,
    MODE_SAFE,
    MODE_STAGED,
    validate_patch,
)
from bago_core.validation.validation_result import (
    GATE_SYNTAX,
    GateResult,
    ValidationResult,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _ScriptedGenerator:
    """Returns the next script entry, then echoes "done" if exhausted."""

    def __init__(self, scripts: list[str | Exception]) -> None:
        self.scripts = list(scripts)
        self.calls: list[dict[str, object]] = []

    def __call__(self, prompt: dict[str, object]) -> str:
        self.calls.append({"prompt": prompt})
        if not self.scripts:
            return "--- a/src/a.py\n+++ b/src/a.py\n@@\n+done\n"
        head = self.scripts.pop(0)
        if isinstance(head, Exception):
            raise head
        return head


class _StaticAdapter(LanguageAdapter):
    """Adapter that returns a pre-canned ``ValidationResult``.

    The first invocation returns ``first``; later invocations return
    ``later``. This lets the test simulate "rejected, then rejected
    again" or "rejected, then accepted".
    """

    language = "python"

    def __init__(self, first: ValidationResult, later: ValidationResult | None = None) -> None:
        super().__init__()
        self._first = first
        self._later = later or first
        self.calls = 0

    def run(self, context: ValidationContext) -> ValidationResult:
        self.calls += 1
        return self._first if self.calls == 1 else self._later


def _passed_result() -> ValidationResult:
    return ValidationResult(
        language="python",
        gate_results=(
            GateResult(GATE_SYNTAX, ValidationStatus.PASSED, message="ok"),
        ),
        overall_status=ValidationStatus.PASSED,
    )


def _failed_result(*, code: str = "LINT_REJECTED") -> ValidationResult:
    return ValidationResult(
        language="python",
        gate_results=(
            GateResult(
                GATE_SYNTAX, ValidationStatus.FAILED,
                code=code, message="boom",
            ),
        ),
        overall_status=ValidationStatus.FAILED,
        overall_code=code,
    )


def _good_diff(
    path: str = "src/a.py",
    old: str = "a = 1\n",
    new: str = "a = 2\n",
    *,
    absolute_prefix: str | None = None,
) -> str:
    """Build a parseable unified diff.

    The default ``old`` matches the body written by :func:`_workspace`
    so the in-memory apply pass lands cleanly. ``absolute_prefix`` lets
    tests construct a diff that targets the absolute path the context
    builder records in ``target_summaries[].path`` (Windows temp dirs
    are not stable, so the test provides the resolved prefix it gets
    from the context).
    """
    old_lines = old.splitlines() if old else [""]
    new_lines = new.splitlines() if new else [""]
    if absolute_prefix:
        old_path = f"{absolute_prefix}/{path}"
        new_path = f"{absolute_prefix}/{path}"
    else:
        old_path = f"a/{path}"
        new_path = f"b/{path}"
    return (
        f"--- {old_path}\n"
        f"+++ {new_path}\n"
        f"@@ -1,{len(old_lines)} +1,{len(new_lines)} @@\n"
        + "".join(f"-{line}\n" for line in old_lines)
        + "".join(f"+{line}\n" for line in new_lines)
    )


def _workspace(tmp: Path) -> tuple[Path, str]:
    """Build a tiny Python project in ``tmp`` and return ``(root, prefix)``.

    ``prefix`` is the resolved, forward-slash absolute path of ``root``
    so the test can build unified diffs whose paths match what the
    context builder records.
    """
    root = tmp / "ws"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("a = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text(
        "def test_a():\n    assert True\n", encoding="utf-8",
    )
    prefix = str(root.resolve()).replace("\\", "/")
    return root, prefix


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class PipelineAcceptsFirstAttemptTests(unittest.TestCase):
    def test_full_pipeline_emits_accepted_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _prefix = _workspace(tmp)
            request = "Modify src/a.py to set a = 2"

            classification = classify_code_request(request, workspace_root=root)
            self.assertFalse(classification.blocked)
            contract = compile_code_task(
                classification,
                objective=request,
                allowed_files=["src/a.py"],
            )
            context = build_code_context(contract, workspace_root=root)
            # Use the actual target path the context builder recorded
            # so the in-memory apply lines up with the staged map.
            target_path = context.target_summaries[0].path

            adapter = _StaticAdapter(first=_passed_result())
            registry = AdapterRegistry().with_adapter(adapter.language, adapter)

            generator = _ScriptedGenerator([_good_diff(path=target_path)])
            repair = run_repair_loop(
                contract=contract,
                context=context,
                generator=generator,
                validator=lambda files, mode: validate_patch(
                    registry=registry,
                    files=tuple(files.values()),
                    mode=MODE_APPLY,
                    workspace="<test>",
                ),
            )

            self.assertEqual(repair.status, STATUS_ACCEPTED)
            self.assertEqual(len(generator.calls), 1)
            self.assertEqual(adapter.calls, 1)

            verdict = derive_code_verdict(repair, mode=MODE_APPLY)
            bundle = bundle_from_repair_verdict(
                repair,
                mode=MODE_APPLY,
                contract=contract,
                created_at=1700000000.0,
            )

            self.assertEqual(verdict.verdict, VERDICT_ACCEPTED)
            self.assertTrue(verdict.can_apply)
            self.assertIsInstance(bundle, EvidenceBundle)
            self.assertEqual(bundle.bundle_version, BUNDLE_VERSION)
            self.assertEqual(bundle.task_id, contract.task_id)
            self.assertEqual(bundle.verdict.verdict, VERDICT_ACCEPTED)
            self.assertEqual(bundle.attempts[0].index, 1)
            # Safe-mode limitation only shows up in non-apply verdicts.
            self.assertNotIn(LIMIT_SAFE_MODE, bundle.limitations)


class PipelineRepairTests(unittest.TestCase):
    def test_repair_after_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _prefix = _workspace(tmp)
            request = "Refactor src/a.py to set a = 2"

            classification = classify_code_request(request, workspace_root=root)
            contract = compile_code_task(
                classification,
                objective=request,
                allowed_files=["src/a.py"],
            )
            self.assertFalse(contract.refused)
            context = build_code_context(contract, workspace_root=root)
            target_path = context.target_summaries[0].path

            adapter = _StaticAdapter(first=_failed_result(), later=_passed_result())
            registry = AdapterRegistry().with_adapter(adapter.language, adapter)

            generator = _ScriptedGenerator([
                _good_diff(path=target_path),  # attempt 1: rejected
                _good_diff(path=target_path),  # attempt 2: accepted
            ])
            repair = run_repair_loop(
                contract=contract,
                context=context,
                generator=generator,
                validator=lambda files, mode: validate_patch(
                    registry=registry,
                    files=tuple(files.values()),
                    mode=MODE_APPLY,
                ),
            )

            self.assertEqual(repair.status, STATUS_ACCEPTED)
            self.assertEqual(len(repair.attempts), 2)
            self.assertEqual(adapter.calls, 2)

            verdict = derive_code_verdict(repair, mode=MODE_APPLY)
            self.assertEqual(verdict.verdict, VERDICT_ACCEPTED)
            self.assertEqual(verdict.attempt_count, 2)


class PipelineMaxAttemptsTests(unittest.TestCase):
    def test_max_attempts_emits_needs_repair(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _prefix = _workspace(tmp)
            request = "Refactor src/a.py to set a = 2"

            classification = classify_code_request(request, workspace_root=root)
            contract = compile_code_task(
                classification, objective=request,
                allowed_files=["src/a.py"],
            )
            self.assertFalse(contract.refused)
            context = build_code_context(contract, workspace_root=root)
            target_path = context.target_summaries[0].path

            adapter = _StaticAdapter(first=_failed_result(), later=_failed_result())
            registry = AdapterRegistry().with_adapter(adapter.language, adapter)

            generator = _ScriptedGenerator([
                _good_diff(path=target_path),
                _good_diff(path=target_path),
                _good_diff(path=target_path),
            ])
            repair = run_repair_loop(
                contract=contract, context=context,
                generator=generator,
                validator=lambda files, mode: validate_patch(
                    registry=registry, files=tuple(files.values()), mode=MODE_APPLY,
                ),
                max_attempts=3,
            )

            self.assertEqual(repair.status, STATUS_REJECTED_MAX_ATTEMPTS)
            verdict = derive_code_verdict(repair, mode=MODE_APPLY)
            self.assertEqual(verdict.verdict, VERDICT_NEEDS_REPAIR)
            self.assertEqual(verdict.reason, REASON_MAX_ATTEMPTS_EXCEEDED)
            self.assertIn("LINT_REJECTED", verdict.failure_codes)


class PipelineParseFailureTests(unittest.TestCase):
    def test_parse_failure_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _prefix = _workspace(tmp)
            request = "Refactor src/a.py to set a = 2"

            classification = classify_code_request(request, workspace_root=root)
            contract = compile_code_task(
                classification, objective=request,
                allowed_files=["src/a.py"],
            )
            self.assertFalse(contract.refused)
            context = build_code_context(contract, workspace_root=root)
            target_path = context.target_summaries[0].path

            adapter = _StaticAdapter(first=_passed_result())
            registry = AdapterRegistry().with_adapter(adapter.language, adapter)

            # Attempt 1 returns a non-diff blob; attempt 2 returns the
            # real diff.
            generator = _ScriptedGenerator([
                "this is not a unified diff at all",
                _good_diff(path=target_path),
            ])
            repair = run_repair_loop(
                contract=contract, context=context,
                generator=generator,
                validator=lambda files, mode: validate_patch(
                    registry=registry, files=tuple(files.values()), mode=MODE_APPLY,
                ),
            )
            self.assertEqual(repair.status, STATUS_ACCEPTED)
            self.assertEqual(len(repair.attempts), 2)
            self.assertTrue(repair.attempts[0].parse_error)


class PipelineRefusedContractTests(unittest.TestCase):
    def test_refused_contract_short_circuits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _prefix = _workspace(tmp)
            # Craft a request that the classifier refuses (forbidden path
            # mention) so the contract is born with ``refused=True``.
            classification = classify_code_request(
                "delete .env file", workspace_root=root,
            )
            contract = compile_code_task(
                classification, objective="purge state", allowed_files=[],
            )
            self.assertTrue(contract.refused)

            adapter = _StaticAdapter(first=_passed_result())
            registry = AdapterRegistry().with_adapter(adapter.language, adapter)

            generator = _ScriptedGenerator([])
            repair = run_repair_loop(
                contract=contract,
                context=build_code_context(contract, workspace_root=root),
                generator=generator,
                validator=lambda files, mode: validate_patch(
                    registry=registry, files=tuple(files.values()), mode=MODE_APPLY,
                ),
            )

            self.assertEqual(repair.status, "rejected_refused")
            self.assertEqual(repair.attempts, ())
            self.assertEqual(generator.calls, [])  # never invoked
            self.assertEqual(adapter.calls, 0)

            verdict = derive_code_verdict(repair, mode=MODE_AUTONOMOUS)
            bundle = build_evidence_bundle(
                verdict=verdict, repair=repair, contract=contract,
                created_at=1700000000.0,
            )
            self.assertEqual(bundle.attempts, ())


class PipelineGeneratorCrashTests(unittest.TestCase):
    def test_generator_crash_returns_unrecoverable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _prefix = _workspace(tmp)
            classification = classify_code_request(
                "modify src/a.py", workspace_root=root,
            )
            contract = compile_code_task(
                classification, objective="modify", allowed_files=["src/a.py"],
            )
            context = build_code_context(contract, workspace_root=root)

            generator = _ScriptedGenerator([RuntimeError("model exploded")])
            registry = AdapterRegistry().with_adapter(
                _StaticAdapter(first=_passed_result()).language,
                _StaticAdapter(first=_passed_result()),
            )

            repair = run_repair_loop(
                contract=contract, context=context,
                generator=generator,
                validator=lambda files, mode: validate_patch(
                    registry=registry, files=tuple(files.values()), mode=MODE_APPLY,
                ),
            )
            self.assertEqual(repair.status, "rejected_unrecoverable")
            self.assertTrue(repair.refusal_reason.startswith("generator_crashed"))


class PipelineSafeModeTests(unittest.TestCase):
    def test_safe_mode_forbids_apply(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root, _prefix = _workspace(tmp)
            classification = classify_code_request(
                "modify src/a.py", workspace_root=root,
            )
            contract = compile_code_task(
                classification, objective="modify",
                allowed_files=["src/a.py"],
            )
            context = build_code_context(contract, workspace_root=root)
            target_path = context.target_summaries[0].path

            adapter = _StaticAdapter(first=_passed_result())
            registry = AdapterRegistry().with_adapter(adapter.language, adapter)
            generator = _ScriptedGenerator([_good_diff(path=target_path)])

            repair = run_repair_loop(
                contract=contract, context=context,
                generator=generator,
                validator=lambda files, mode: validate_patch(
                    registry=registry, files=tuple(files.values()), mode=MODE_APPLY,
                ),
            )

            for mode in (MODE_SAFE, MODE_STAGED, MODE_APPLY, MODE_AUTONOMOUS):
                verdict = derive_code_verdict(repair, mode=mode)
                if mode in (MODE_APPLY, MODE_AUTONOMOUS):
                    self.assertTrue(verdict.can_apply, mode)
                else:
                    self.assertFalse(verdict.can_apply, mode)


class PipelineValidatePatchFallbackTests(unittest.TestCase):
    """Tests that don't need a real repair loop but exercise the pipeline."""

    def test_validate_patch_with_no_adapter(self) -> None:
        verdict = validate_patch(
            registry=AdapterRegistry(),
            files=(FileToValidate(path="x.py", language="python", body=""),),
            mode=MODE_SAFE,
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.FAILED)
        self.assertEqual(verdict.overall_code, "adapter_missing")

    def test_validate_patch_unknown_mode(self) -> None:
        verdict = validate_patch(
            registry=AdapterRegistry(),
            files=(),
            mode="BOGUS",
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.FAILED)
        self.assertEqual(verdict.overall_code, "unknown_mode")

    def test_validate_patch_succeeds(self) -> None:
        adapter = _StaticAdapter(first=_passed_result())
        registry = AdapterRegistry().with_adapter(adapter.language, adapter)
        verdict = validate_patch(
            registry=registry,
            files=(FileToValidate(path="x.py", language="python", body="a = 1\n"),),
            mode=MODE_APPLY,
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.PASSED)
        self.assertTrue(verdict.accepted)


class PipelineParsePatchOutputTests(unittest.TestCase):
    def test_diff_round_trip_through_parser(self) -> None:
        diff = _good_diff()
        patch = parse_patch(diff)
        self.assertEqual(patch.new_path, "src/a.py")
        self.assertEqual(patch.hunks[0].additions(), 1)
        self.assertEqual(patch.hunks[0].deletions(), 1)


if __name__ == "__main__":
    unittest.main()
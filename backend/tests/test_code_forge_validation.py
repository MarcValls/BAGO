"""Tests for the BAGO Code Forge 3B validation pipeline and Python adapter."""
from __future__ import annotations

import textwrap
import unittest

from bago_core.validation import (
    AdapterRegistry,
    GATE_FORMATTING,
    GATE_IMPORTS,
    GATE_LINT,
    GATE_SECURITY,
    GATE_SYNTAX,
    GATE_TESTS,
    GATE_TYPECHECK,
    GateResult,
    LanguageAdapter,
    MODE_APPLY,
    MODE_AUTONOMOUS,
    MODE_SAFE,
    MODE_STAGED,
    PipelineVerdict,
    VALIDATION_MODES,
    ValidationContext,
    ValidationResult,
    ValidationStatus,
    FileToValidate,
    gate_is_allowed,
    validate_patch,
)
from bago_core.validation.adapters.python_adapter import (
    CODE_AST_PARSE,
    CODE_FORMATTER_REJECTED,
    CODE_IMPORT_UNRESOLVED,
    CODE_TESTS_FAILED,
    CODE_TYPECHECK_REJECTED,
    PythonAdapter,
    PythonToolConfig,
    _parse_python,
    _resolve_imports,
)


VALID_BODY = textwrap.dedent(
    """\
    def greet(name: str) -> str:
        return f"hi {name}"
    """
).lstrip()


SYNTAX_BROKEN_BODY = "def greet(name: str) -> str\n    return 'hi'\n"  # missing ':'


class FakeRunner:
    """In-memory replacement for the real process runner.

    Each command id maps to a deterministic ``(returncode, stderr)``.
    Tests can register any id they need; unrecognised commands raise
    ``RuntimeError`` so unexpected tool invocations fail loudly.
    """

    def __init__(self, *, default_returncode: int = 0) -> None:
        self._responses: dict[str, tuple[int, str]] = {}
        self._default_returncode = default_returncode
        self.calls: list[tuple[str, str]] = []  # (command, cwd)

    def register(self, command: str, *, returncode: int, stderr: str = "") -> None:
        self._responses[command] = (returncode, stderr)

    def run(self, command, *, stdin, cwd, timeout_seconds):
        self.calls.append((command, cwd))
        returncode, stderr = self._responses.get(
            command, (self._default_returncode, ""),
        )
        return _FakeOutcome(returncode=returncode, stderr=stderr, duration_ms=2)


class _FakeOutcome:
    def __init__(self, *, returncode: int, stderr: str, duration_ms: int) -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.duration_ms = duration_ms


def _files(*bodies_and_paths: tuple[str, str]) -> tuple[FileToValidate, ...]:
    return tuple(
        FileToValidate(path=path, language="python", body=body)
        for body, path in bodies_and_paths
    )


class _RecordingAdapter(LanguageAdapter):
    """Adapter used to inspect pipeline behaviour without subprocess."""

    language = "fake"
    supported_gates = (GATE_SYNTAX, GATE_IMPORTS)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[ValidationContext] = []

    def run(self, context: ValidationContext) -> ValidationResult:
        self.calls.append(context)
        return ValidationResult(
            language=self.language,
            gate_results=(
                self._gate_passed(GATE_SYNTAX, message="ok"),
                self._gate_passed(GATE_IMPORTS, message="ok"),
            ),
            overall_status=ValidationStatus.PASSED,
            overall_code="",
        )


class ValidationPipelineTests(unittest.TestCase):
    def test_validate_patch_rejects_unknown_mode(self) -> None:
        verdict = validate_patch(
            registry=AdapterRegistry(),
            files=(),
            mode="NOPE",
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.FAILED)
        self.assertEqual(verdict.overall_code, "unknown_mode")

    def test_validate_patch_reports_missing_adapter(self) -> None:
        files = _files((VALID_BODY, "src/a.py"))
        verdict = validate_patch(
            registry=AdapterRegistry(),  # no python adapter
            files=files,
            mode=MODE_STAGED,
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.FAILED)
        self.assertEqual(verdict.overall_code, "adapter_missing")
        result = verdict.results["python"]
        self.assertEqual(result.overall_code, "adapter_missing")

    def test_validate_patch_routes_files_by_language(self) -> None:
        rec = _RecordingAdapter()
        registry = AdapterRegistry().with_adapter("fake", rec)
        files = (
            FileToValidate(path="a.py", language="fake", body="x = 1"),
            FileToValidate(path="b.py", language="fake", body="y = 2"),
        )
        verdict = validate_patch(
            registry=registry, files=files, mode=MODE_STAGED,
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.PASSED)
        self.assertEqual(len(rec.calls), 1)
        self.assertEqual(len(rec.calls[0].files), 2)

    def test_safe_mode_filters_adapter_gates(self) -> None:
        # The fake adapter only declares two safe gates; the pipeline
        # must not invent additional ones, but it must also not fail
        # just because ``lint`` etc. are not declared.
        rec = _RecordingAdapter()
        registry = AdapterRegistry().with_adapter("fake", rec)
        verdict = validate_patch(
            registry=registry,
            files=(FileToValidate(path="a.py", language="fake", body="x = 1"),),
            mode=MODE_SAFE,
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.PASSED)

    def test_validate_patch_propagates_first_failure(self) -> None:
        # When the adapter fails, the verdict carries the first failing
        # code so the repair loop can dispatch on it without parsing.
        class _FailingAdapter(LanguageAdapter):
            language = "broken"
            supported_gates = (GATE_SYNTAX,)

            def run(self, context):
                return ValidationResult(
                    language=self.language,
                    gate_results=(
                        self._gate_failed(
                            GATE_SYNTAX, "X_FAIL", message="boom",
                        ),
                    ),
                    overall_status=ValidationStatus.FAILED,
                    overall_code="X_FAIL",
                )

        registry = AdapterRegistry().with_adapter(
            "broken", _FailingAdapter(),
        )
        verdict = validate_patch(
            registry=registry,
            files=(FileToValidate(path="x.py", language="broken", body=""),),
            mode=MODE_STAGED,
        )
        self.assertEqual(verdict.overall_status, ValidationStatus.FAILED)
        self.assertEqual(verdict.overall_code, "X_FAIL")

    def test_gate_is_allowed_table(self) -> None:
        self.assertTrue(gate_is_allowed("syntax", mode=MODE_SAFE))
        self.assertTrue(gate_is_allowed("imports", mode=MODE_SAFE))
        self.assertFalse(gate_is_allowed("lint", mode=MODE_SAFE))
        self.assertTrue(gate_is_allowed("lint", mode=MODE_STAGED))
        self.assertTrue(gate_is_allowed("tests", mode=MODE_APPLY))
        self.assertTrue(gate_is_allowed("tests", mode=MODE_AUTONOMOUS))
        self.assertFalse(gate_is_allowed("syntax", mode="BOGUS"))

    def test_validation_modes_constant_includes_all_four(self) -> None:
        self.assertEqual(
            VALIDATION_MODES,
            frozenset({MODE_SAFE, MODE_STAGED, MODE_APPLY, MODE_AUTONOMOUS}),
        )


class PythonAdapterTests(unittest.TestCase):
    def test_parse_python_reports_syntax_errors(self) -> None:
        self.assertIsNone(_parse_python(VALID_BODY))
        msg = _parse_python(SYNTAX_BROKEN_BODY)
        self.assertIsNotNone(msg)
        self.assertIn("expected", msg)

    def test_parse_python_accepts_empty(self) -> None:
        self.assertIsNone(_parse_python(""))

    def test_resolve_imports_flags_unknown_modules(self) -> None:
        unresolved = _resolve_imports(
            "import os, sys\nimport does_not_exist_xyz\n",
            "x.py",
        )
        self.assertIn("does_not_exist_xyz", unresolved)
        self.assertNotIn("os", unresolved)
        self.assertNotIn("sys", unresolved)

    def test_resolve_imports_accepts_future(self) -> None:
        unresolved = _resolve_imports(
            "from __future__ import annotations\n",
            "x.py",
        )
        self.assertEqual(unresolved, ())

    def test_resolve_imports_returns_empty_on_syntax_error(self) -> None:
        self.assertEqual(_resolve_imports(SYNTAX_BROKEN_BODY, "x.py"), ())

    def test_python_adapter_passes_clean_file_with_runner(self) -> None:
        runner = FakeRunner()  # default_returncode=0
        adapter = PythonAdapter(process_runner=runner)
        files = _files((VALID_BODY, "src/a.py"))
        result = adapter.run(ValidationContext(
            workspace="/tmp/ws",
            files=files,
            mode=MODE_STAGED,
        ))
        self.assertEqual(result.overall_status, ValidationStatus.PASSED)
        gates = {g.gate: g for g in result.gate_results}
        self.assertEqual(gates[GATE_SYNTAX].status, ValidationStatus.PASSED)
        self.assertEqual(gates[GATE_IMPORTS].status, ValidationStatus.PASSED)
        # External tools were invoked.
        self.assertGreaterEqual(len(runner.calls), 5)

    def test_python_adapter_fails_syntax_first(self) -> None:
        runner = FakeRunner()
        adapter = PythonAdapter(process_runner=runner)
        files = _files((SYNTAX_BROKEN_BODY, "src/a.py"))
        result = adapter.run(ValidationContext(
            workspace="/tmp/ws",
            files=files,
            mode=MODE_STAGED,
        ))
        self.assertEqual(result.overall_status, ValidationStatus.FAILED)
        self.assertEqual(result.overall_code, CODE_AST_PARSE)
        # Downstream gates are not reported when syntax fails - we bail
        # out to keep the result short.
        gates = {g.gate: g for g in result.gate_results}
        self.assertEqual(gates[GATE_SYNTAX].status, ValidationStatus.FAILED)
        self.assertNotIn(GATE_LINT, gates)
        self.assertEqual(len(runner.calls), 0)

    def test_python_adapter_skips_external_tools_without_runner(self) -> None:
        adapter = PythonAdapter(process_runner=None)
        files = _files((VALID_BODY, "src/a.py"))
        result = adapter.run(ValidationContext(
            workspace="/tmp/ws",
            files=files,
            mode=MODE_STAGED,
        ))
        self.assertEqual(result.overall_status, ValidationStatus.PASSED)
        gates = {g.gate: g for g in result.gate_results}
        for gate in (GATE_FORMATTING, GATE_LINT, GATE_TYPECHECK,
                     GATE_SECURITY, GATE_TESTS):
            self.assertEqual(gates[gate].status, ValidationStatus.SKIPPED)

    def test_python_adapter_propagates_formatter_failure(self) -> None:
        runner = FakeRunner()
        runner.register("black --check", returncode=1, stderr="would reformat")
        adapter = PythonAdapter(process_runner=runner)
        result = adapter.run(ValidationContext(
            workspace="/tmp/ws",
            files=_files((VALID_BODY, "src/a.py")),
            mode=MODE_STAGED,
        ))
        self.assertEqual(result.overall_status, ValidationStatus.FAILED)
        # formatter runs before typecheck and tests; its failure wins.
        self.assertEqual(result.overall_code, CODE_FORMATTER_REJECTED)

    def test_python_adapter_propagates_test_failure(self) -> None:
        runner = FakeRunner()  # default returncode 0
        runner.register("pytest", returncode=1, stderr="1 failed")
        adapter = PythonAdapter(process_runner=runner)
        result = adapter.run(ValidationContext(
            workspace="/tmp/ws",
            files=_files((VALID_BODY, "src/a.py")),
            mode=MODE_STAGED,
        ))
        self.assertEqual(result.overall_status, ValidationStatus.FAILED)
        self.assertEqual(result.overall_code, CODE_TESTS_FAILED)

    def test_python_adapter_disabling_tools_yields_passed(self) -> None:
        # With every external tool disabled, only syntax + imports run.
        tools = PythonToolConfig(
            formatter=None, linter=None, typechecker=None,
            security=None, tests=None,
        )
        adapter = PythonAdapter(tools=tools)
        result = adapter.run(ValidationContext(
            workspace="/tmp/ws",
            files=_files((VALID_BODY, "src/a.py")),
            mode=MODE_STAGED,
        ))
        self.assertEqual(result.overall_status, ValidationStatus.PASSED)
        # Disabled gates are not reported at all (caller asked to skip
        # them by setting ``None``).
        present = {g.gate for g in result.gate_results}
        self.assertNotIn(GATE_FORMATTING, present)
        self.assertNotIn(GATE_LINT, present)
        self.assertNotIn(GATE_TYPECHECK, present)
        self.assertNotIn(GATE_SECURITY, present)
        self.assertNotIn(GATE_TESTS, present)
        # The cheap in-process gates still ran.
        self.assertIn(GATE_SYNTAX, present)
        self.assertIn(GATE_IMPORTS, present)


class ValidationResultTests(unittest.TestCase):
    def test_overall_passed_when_every_gate_passes(self) -> None:
        gates = (
            GateResult(GATE_SYNTAX, ValidationStatus.PASSED, message="ok"),
            GateResult(GATE_IMPORTS, ValidationStatus.PASSED, message="ok"),
        )
        result = ValidationResult(
            language="python", gate_results=gates,
        )
        status, code = LanguageAdapter._overall(gates)
        self.assertEqual(status, ValidationStatus.PASSED)
        self.assertEqual(code, "")

    def test_overall_failed_when_one_gate_fails(self) -> None:
        gates = (
            GateResult(GATE_SYNTAX, ValidationStatus.PASSED, message="ok"),
            GateResult(GATE_LINT, ValidationStatus.FAILED, code="X", message=""),
        )
        status, code = LanguageAdapter._overall(gates)
        self.assertEqual(status, ValidationStatus.FAILED)
        self.assertEqual(code, "X")


if __name__ == "__main__":
    unittest.main()

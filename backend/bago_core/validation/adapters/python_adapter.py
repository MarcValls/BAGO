"""BAGO Code Forge 3B - Python validation adapter.

Implements the full Python gate sequence proposed in the BAGO Code
Forge 3B design doc:

1. ``syntax``     - in-process ``ast.parse``
2. ``imports``    - every ``import`` resolves to a module on ``sys.path``
                    or to a relative module inside ``workspace``
3. ``formatting`` - delegates to a configurable formatter (defaults to
                    ``black --check`` when a process runner is available;
                    skipped when no runner is present)
4. ``lint``       - delegates to a configurable linter (defaults to
                    ``ruff check``; skipped without a runner)
5. ``typecheck``  - delegates to ``mypy``; skipped without a runner
6. ``security``   - delegates to ``bandit``; skipped without a runner
7. ``tests``      - delegates to ``pytest``; skipped without a runner

The adapter never mutates the workspace and never imports any module
from the patch - those checks belong to the staging workspace. It
treats the supplied ``body`` as opaque source text.

Design rules (R0-R10):

- R1: returns a single :class:`ValidationResult`.
- R3: never raises. Every failure becomes a :class:`GateResult`.
- R8: subprocess only via the injected runner.
"""
from __future__ import annotations

import ast
import importlib
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping

from ..language_adapter import (
    FileToValidate,
    LanguageAdapter,
    ValidationContext,
)
from ..validation_result import (
    GATE_FORMATTING,
    GATE_IMPORTS,
    GATE_LINT,
    GATE_SECURITY,
    GATE_SYNTAX,
    GATE_TESTS,
    GATE_TYPECHECK,
    ValidationResult,
    ValidationStatus,
)


# Stable codes the repair loop dispatches on.
CODE_AST_PARSE = "AST_PARSE"
CODE_IMPORT_UNRESOLVED = "IMPORT_UNRESOLVED"
CODE_FORMATTER_REJECTED = "FORMATTER_REJECTED"
CODE_LINT_REJECTED = "LINT_REJECTED"
CODE_TYPECHECK_REJECTED = "TYPECHECK_REJECTED"
CODE_SECURITY_REJECTED = "SECURITY_REJECTED"
CODE_TESTS_FAILED = "TESTS_FAILED"
CODE_TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"


@dataclass(frozen=True)
class PythonToolConfig:
    """Which external tools the adapter should attempt.

    Each value is either a string command id (resolved against the
    process runner) or ``None`` to skip that gate entirely.
    """

    formatter: str | None = "black --check"
    linter: str | None = "ruff check"
    typechecker: str | None = "mypy"
    security: str | None = "bandit"
    tests: str | None = "pytest"


_DEFAULT_TOOLS = PythonToolConfig()


class PythonAdapter(LanguageAdapter):
    """Adapter that runs the seven Python gates in order."""

    language = "python"
    supported_gates: tuple[str, ...] = (
        GATE_SYNTAX,
        GATE_IMPORTS,
        GATE_FORMATTING,
        GATE_LINT,
        GATE_TYPECHECK,
        GATE_SECURITY,
        GATE_TESTS,
    )

    def __init__(
        self,
        *,
        process_runner=None,
        tools: PythonToolConfig | None = None,
    ) -> None:
        super().__init__(process_runner=process_runner)
        self._tools = tools or _DEFAULT_TOOLS

    def run(self, context: ValidationContext) -> ValidationResult:
        gates: list = []
        for file in context.files:
            gates.extend(self._gate_file(file, context))
        gate_results = tuple(gates)
        overall_status, overall_code = self._overall(gate_results)
        return ValidationResult(
            language=self.language,
            gate_results=gate_results,
            overall_status=overall_status,
            overall_code=overall_code,
        )

    # ------------------------------------------------------------------
    # per-file gating
    # ------------------------------------------------------------------

    def _gate_file(self, file: FileToValidate, context: ValidationContext):
        if file.language != self.language:
            yield self._gate_failed(
                GATE_SYNTAX,
                "wrong_language",
                message=f"python adapter received {file.language!r}",
            )
            return

        # 1. syntax - cheapest, in-process
        syntax_error = _parse_python(file.body)
        if syntax_error is None:
            yield self._gate_passed(GATE_SYNTAX, message="ast.parse ok")
        else:
            yield self._gate_failed(
                GATE_SYNTAX,
                CODE_AST_PARSE,
                message=syntax_error,
            )
            # Syntax errors invalidate every downstream gate; bail out.
            return

        # 2. imports
        unresolved = _resolve_imports(file.body, file.path)
        if not unresolved:
            yield self._gate_passed(GATE_IMPORTS, message="all imports resolved")
        else:
            yield self._gate_failed(
                GATE_IMPORTS,
                CODE_IMPORT_UNRESOLVED,
                message=f"{len(unresolved)} unresolved import(s): {', '.join(unresolved[:5])}",
            )

        # 3. formatting - requires a process runner
        yield from self._run_external_tool(
            file, context, GATE_FORMATTING, self._tools.formatter,
            code_fail=CODE_FORMATTER_REJECTED,
        )
        # 4. lint
        yield from self._run_external_tool(
            file, context, GATE_LINT, self._tools.linter,
            code_fail=CODE_LINT_REJECTED,
        )
        # 5. typecheck
        yield from self._run_external_tool(
            file, context, GATE_TYPECHECK, self._tools.typechecker,
            code_fail=CODE_TYPECHECK_REJECTED,
        )
        # 6. security
        yield from self._run_external_tool(
            file, context, GATE_SECURITY, self._tools.security,
            code_fail=CODE_SECURITY_REJECTED,
        )
        # 7. tests
        yield from self._run_external_tool(
            file, context, GATE_TESTS, self._tools.tests,
            code_fail=CODE_TESTS_FAILED,
        )

    # ------------------------------------------------------------------
    # external-tool runner
    # ------------------------------------------------------------------

    def _run_external_tool(self, file, context, gate, command, *, code_fail):
        if not command:
            # Caller disabled this gate by passing ``None``. Don't
            # report it at all so downstream consumers don't have to
            # distinguish "skipped because disabled" from "skipped because
            # tool unavailable" - both just mean the gate was not run.
            return
        if self._process_runner is None:
            yield self._gate_skipped(
                gate,
                reason="no process runner injected",
                command_id=command,
            )
            return
        try:
            outcome = self._process_runner.run(
                command,
                stdin=file.body,
                cwd=context.workspace,
                timeout_seconds=context.timeout_seconds,
            )
        except Exception as exc:
            yield self._gate_failed(
                gate,
                CODE_TOOL_UNAVAILABLE,
                message=f"{command} crashed: {exc}",
                command_id=command,
            )
            return
        if outcome.returncode == 0:
            yield self._gate_passed(
                gate, message=f"{command} ok", command_id=command,
                duration_ms=outcome.duration_ms,
            )
        else:
            yield self._gate_failed(
                gate,
                code_fail,
                message=outcome.stderr.strip()[:2000] or f"{command} failed",
                command_id=command,
                duration_ms=outcome.duration_ms,
            )


# ----------------------------------------------------------------------
# pure helpers (no I/O, easy to unit-test)
# ----------------------------------------------------------------------


def _parse_python(source: str) -> str | None:
    """Return ``None`` on success or a short error string."""
    if not source.strip():
        return None  # empty file is fine
    try:
        ast.parse(source)
    except SyntaxError as exc:
        line = getattr(exc, "lineno", 0) or 0
        column = getattr(exc, "offset", 0) or 0
        return f"{exc.msg} at line {line}, column {column}"
    return None


def _resolve_imports(source: str, file_path: str) -> tuple[str, ...]:
    """Return the list of import targets that cannot be resolved.

    Resolution rules:

    - ``from __future__ import ...`` is always considered resolved.
    - A relative ``from .x import y`` resolves if any sibling file with
      stem ``x.py`` or ``x/__init__.py`` exists in the staged workspace
      (the adapter does not have that info, so it cannot validate
      relative imports and always accepts them).
    - An absolute import resolves if ``importlib.util.find_spec`` returns
      a non-``None`` spec.
    """
    if not source.strip():
        return ()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # The syntax gate will already have reported this; skip import
        # resolution rather than duplicate the failure.
        return ()
    unresolved: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import - cannot verify without workspace.
                continue
            if node.module == "__future__":
                continue
            targets = [a.name for a in node.names]
            if not _module_resolves(node.module):
                unresolved.extend(f"{node.module}.{t}" for t in targets)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if not _module_resolves(alias.name):
                    unresolved.append(alias.name)
    # Dedup, preserve order
    seen: dict[str, None] = {}
    for name in unresolved:
        seen.setdefault(name, None)
    return tuple(seen)


def _module_resolves(name: str) -> bool:
    parts = name.split(".")
    for cutoff in range(len(parts), 0, -1):
        candidate = ".".join(parts[:cutoff])
        try:
            if importlib.util.find_spec(candidate) is not None:
                return True
        except (ImportError, ValueError):
            continue
    return False


__all__ = [
    "CODE_AST_PARSE",
    "CODE_FORMATTER_REJECTED",
    "CODE_IMPORT_UNRESOLVED",
    "CODE_LINT_REJECTED",
    "CODE_SECURITY_REJECTED",
    "CODE_TESTS_FAILED",
    "CODE_TOOL_UNAVAILABLE",
    "CODE_TYPECHECK_REJECTED",
    "PythonAdapter",
    "PythonToolConfig",
]

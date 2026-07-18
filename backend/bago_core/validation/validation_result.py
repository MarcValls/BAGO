"""BAGO Code Forge 3B - validation result types.

The validation pipeline is the single authority on whether a candidate
patch is allowed to land in the workspace. Every adapter returns a
:class:`ValidationResult` composed of :class:`GateResult` items so the
pipeline can:

1. Show the user the full gate-by-gate breakdown.
2. Feed the failing gates to the repair loop without re-parsing.
3. Produce a stable evidence bundle.

Design rules (R0-R10):

- R1: dataclasses are ``frozen=True`` and JSON-serialisable via
  :meth:`to_dict`.
- R2: every status is one of three literal values. ``PASSED`` means the
  gate succeeded; ``FAILED`` means the gate rejected the patch with a
  stable ``code``; ``SKIPPED`` means the gate was intentionally not run
  (missing tool, disabled by mode, etc.).
- R3: stable ``GATE_*`` and ``code`` constants. Downstream code dispatches
  on these strings, so renaming a code is a breaking change.
- R8: no subprocess, no I/O. The result is just data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


# Gate identifiers. The order matters: adapters must run gates in this
# order so cheap, deterministic checks fail first and expensive
# checks (tests, full build) only run on candidates that already passed
# the cheap ones.
GATE_SYNTAX = "syntax"
GATE_FORMATTING = "formatting"
GATE_LINT = "lint"
GATE_TYPECHECK = "typecheck"
GATE_IMPORTS = "imports"
GATE_SECURITY = "security"
GATE_TESTS = "tests"

GATE_ORDER: tuple[str, ...] = (
    GATE_SYNTAX,
    GATE_FORMATTING,
    GATE_LINT,
    GATE_TYPECHECK,
    GATE_IMPORTS,
    GATE_SECURITY,
    GATE_TESTS,
)


class ValidationStatus:
    """The three outcomes a gate can return."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict on a single file.

    Attributes
    ----------
    gate:
        Gate id (one of :data:`GATE_ORDER`).
    status:
        ``passed``, ``failed``, or ``skipped``.
    code:
        Stable machine-readable sub-code (e.g. ``AST_PARSE``,
        ``LINT_UNDEFINED_NAME``). Empty string when the gate passed.
    message:
        Human-readable explanation. Always present, even on success, so
        the evidence bundle stays informative.
    command_id:
        Id of the ``script_registry`` command the gate ran, if any.
        Empty when the gate was an in-process check.
    """

    gate: str
    status: str
    code: str = ""
    message: str = ""
    command_id: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": self.gate,
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "command_id": self.command_id,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate verdict for one patch across all gates.

    Attributes
    ----------
    language:
        Adapter language id (``python``, ``javascript``, ...).
    gate_results:
        Tuple of :class:`GateResult`. Order follows :data:`GATE_ORDER`
        but the tuple is the source of truth; the pipeline does not
        reorder it.
    overall_status:
        ``passed`` iff every gate passed. ``failed`` if any gate failed
        (the failing gate's ``code`` is ``overall_code``).
        ``skipped`` if every gate was skipped (nothing was actually
        validated - the pipeline must escalate).
    overall_code:
        The ``code`` of the first failing gate, or empty string if all
        passed.
    duration_ms:
        Wall-clock time spent in the adapter (best effort).
    """

    language: str
    gate_results: tuple[GateResult, ...] = field(default_factory=tuple)
    overall_status: str = ValidationStatus.SKIPPED
    overall_code: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "gate_results": [g.to_dict() for g in self.gate_results],
            "overall_status": self.overall_status,
            "overall_code": self.overall_code,
            "duration_ms": self.duration_ms,
        }

    @property
    def failed_gates(self) -> tuple[GateResult, ...]:
        return tuple(g for g in self.gate_results if g.status == ValidationStatus.FAILED)

    @property
    def passed_gates(self) -> tuple[GateResult, ...]:
        return tuple(g for g in self.gate_results if g.status == ValidationStatus.PASSED)

    @property
    def skipped_gates(self) -> tuple[GateResult, ...]:
        return tuple(g for g in self.gate_results if g.status == ValidationStatus.SKIPPED)

    def first_failure(self) -> GateResult | None:
        for gate in GATE_ORDER:
            for result in self.gate_results:
                if result.gate == gate and result.status == ValidationStatus.FAILED:
                    return result
        return None


def empty_validation_result(language: str) -> ValidationResult:
    """Return a result with no gates executed yet."""
    return ValidationResult(language=language)


def summarise(results: Mapping[str, ValidationResult]) -> dict[str, object]:
    """Build a flat summary the evidence bundle can attach verbatim."""
    summary: dict[str, object] = {}
    for language, result in results.items():
        summary[language] = {
            "overall_status": result.overall_status,
            "overall_code": result.overall_code,
            "passed": len(result.passed_gates),
            "failed": len(result.failed_gates),
            "skipped": len(result.skipped_gates),
        }
    return summary

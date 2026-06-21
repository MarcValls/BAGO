"""BAGO Code Forge 3B - language adapter base class.

An adapter is responsible for taking the **post-patch** file contents
(via the staging workspace) and running every applicable gate in order,
returning a single :class:`ValidationResult`. Adapters never mutate the
workspace and never call the model - they are the deterministic
backbone of the pipeline.

Design rules (R0-R10):

- R1: subclasses must declare their ``language`` id and the gate ids
  they implement via :attr:`supported_gates`.
- R3: a missing or unreadable file must yield a
  ``ValidationStatus.FAILED`` with code ``FILE_MISSING``, never raise.
- R6: adapters are stateless; any state lives in the ``context``
  dict passed in by the pipeline.
- R8: subprocess is allowed *only* via :class:`ProcessRunner` declared
  in :mod:`bago_core.execution.process_runner`. The adapter receives
  the runner by injection so tests can swap a fake.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .validation_result import (
    GATE_ORDER,
    GateResult,
    ValidationResult,
    ValidationStatus,
)


@dataclass(frozen=True)
class FileToValidate:
    """One file the adapter has to gate.

    Attributes
    ----------
    path:
        Workspace-relative path (matches :attr:`CodeTaskContract.target_files`).
    language:
        Adapter language id; must equal the adapter's
        :attr:`LanguageAdapter.language`.
    body:
        The *post-patch* source. Adapters see the new content, not the
        old one - the staging workspace has already applied the patch.
    is_new:
        ``True`` for files that did not exist before the patch (so
        ``FILE_MISSING`` checks should be skipped).
    """

    path: str
    language: str
    body: str
    is_new: bool = False


@dataclass(frozen=True)
class ValidationContext:
    """Read-only inputs the pipeline hands every adapter.

    The adapter must not assume the workspace directory contains the
    files - the staging area may be a temporary copy. All file contents
    arrive through :attr:`files`.
    """

    workspace: str
    files: tuple[FileToValidate, ...]
    mode: str  # one of validation_pipeline.VALIDATION_MODES
    timeout_seconds: int = 120
    extra: dict[str, object] | None = None


class LanguageAdapter(ABC):
    """Base class for all language-specific adapters."""

    #: Identifier used by the registry (``"python"``, ``"javascript"``...).
    language: str = ""

    #: Gate ids this adapter is able to run, in execution order.
    supported_gates: tuple[str, ...] = ()

    def __init__(self, *, process_runner=None) -> None:
        # Optional process runner injection. Adapters that need
        # subprocess (lint, tests) accept it; pure-AST adapters ignore
        # it. The default ``None`` means "no subprocess available" - the
        # adapter must report ``SKIPPED`` for any gate it cannot run
        # without subprocess.
        self._process_runner = process_runner

    @abstractmethod
    def run(self, context: ValidationContext) -> ValidationResult:
        """Run all supported gates against the staged files."""

    # ---- helpers shared by every adapter -----------------------------

    def _empty_result(self) -> ValidationResult:
        return ValidationResult(language=self.language)

    @staticmethod
    def _gate(gate: str, status: str, *, code: str = "", message: str = "",
              command_id: str = "", duration_ms: int = 0) -> GateResult:
        return GateResult(
            gate=gate,
            status=status,
            code=code,
            message=message,
            command_id=command_id,
            duration_ms=duration_ms,
        )

    @classmethod
    def _gate_passed(cls, gate: str, *, message: str = "ok",
                     command_id: str = "", duration_ms: int = 0) -> GateResult:
        return cls._gate(gate, ValidationStatus.PASSED, message=message,
                         command_id=command_id, duration_ms=duration_ms)

    @classmethod
    def _gate_failed(cls, gate: str, code: str, *, message: str,
                     command_id: str = "", duration_ms: int = 0) -> GateResult:
        return cls._gate(gate, ValidationStatus.FAILED, code=code, message=message,
                         command_id=command_id, duration_ms=duration_ms)

    @classmethod
    def _gate_skipped(cls, gate: str, *, reason: str,
                      command_id: str = "") -> GateResult:
        return cls._gate(gate, ValidationStatus.SKIPPED, message=reason,
                         command_id=command_id)

    @staticmethod
    def _overall(gates: tuple[GateResult, ...]) -> tuple[str, str]:
        """Compute ``(overall_status, overall_code)`` from a gate list.

        The first failing gate (in :data:`GATE_ORDER` order) wins the
        ``overall_code``. If nothing failed but everything is skipped,
        the result is ``skipped``.
        """
        if any(g.status == ValidationStatus.FAILED for g in gates):
            for gate_id in GATE_ORDER:
                for g in gates:
                    if g.gate == gate_id and g.status == ValidationStatus.FAILED:
                        return ValidationStatus.FAILED, g.code
        if gates and all(g.status == ValidationStatus.SKIPPED for g in gates):
            return ValidationStatus.SKIPPED, ""
        if any(g.status == ValidationStatus.PASSED for g in gates):
            return ValidationStatus.PASSED, ""
        return ValidationStatus.SKIPPED, ""

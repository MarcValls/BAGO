"""BAGO Code Forge 3B - validation pipeline.

The pipeline is the single public entry point every higher pass
(repair loop, code verdict, evidence builder) calls. It is responsible
for:

1. Selecting the right :class:`LanguageAdapter` for each file in the
   patch.
2. Running the adapter with a :class:`ValidationContext`.
3. Aggregating per-adapter results into a single
   :class:`PipelineVerdict`.
4. Enforcing the four operating modes (``SAFE``, ``STAGED``, ``APPLY``,
   ``AUTONOMOUS``) so the caller never has to remember which gate is
   allowed where.

Design rules (R0-R10):

- R1: :class:`PipelineVerdict` is a frozen dataclass.
- R3: a missing or unknown adapter must yield a structured
  ``adapter_missing`` failure, never raise.
- R4: deterministic. Same context + adapters ⇒ same verdict.
- R8: no I/O. The pipeline trusts the caller to feed it staged files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .language_adapter import (
    FileToValidate,
    LanguageAdapter,
    ValidationContext,
)
from .validation_result import (
    GATE_ORDER,
    ValidationResult,
    ValidationStatus,
    summarise,
)


# Operating modes the BAGO policy allows.
MODE_SAFE = "SAFE"
MODE_STAGED = "STAGED"
MODE_APPLY = "APPLY"
MODE_AUTONOMOUS = "AUTONOMOUS"
VALIDATION_MODES: frozenset[str] = frozenset(
    {MODE_SAFE, MODE_STAGED, MODE_APPLY, MODE_AUTONOMOUS}
)


# Gates that are allowed to run in SAFE mode. Safe mode never mutates
# and never shells out, so only the cheapest, in-process gates are on
# the list. Lint, typecheck and tests all require ``MODE_STAGED`` or
# higher.
SAFE_GATES: frozenset[str] = frozenset(
    {
        "syntax",
        "imports",
        "formatting",
    }
)

# Gates that require a sandboxed run (STAGED or above).
MUTATING_GATES: frozenset[str] = frozenset(
    {
        "lint",
        "typecheck",
        "security",
        "tests",
    }
)

# Code used when the adapter registry cannot find a handler for a
# file's language. Stable string so the repair loop can dispatch on it.
CODE_ADAPTER_MISSING = "adapter_missing"
CODE_FORBIDDEN_LANGUAGE = "forbidden_language"
CODE_UNKNOWN_MODE = "unknown_mode"


@dataclass(frozen=True)
class AdapterRegistry:
    """Maps language id to :class:`LanguageAdapter`.

    The registry is immutable; registering a new adapter means creating
    a new registry. This keeps the pipeline deterministic.
    """

    adapters: Mapping[str, LanguageAdapter] = field(default_factory=dict)

    def get(self, language: str) -> LanguageAdapter | None:
        return self.adapters.get(language)

    def languages(self) -> tuple[str, ...]:
        return tuple(sorted(self.adapters))

    def with_adapter(self, language: str, adapter: LanguageAdapter) -> "AdapterRegistry":
        new = dict(self.adapters)
        new[language] = adapter
        return AdapterRegistry(adapters=new)


def _select_gates(adapter: LanguageAdapter, *, mode: str) -> tuple[str, ...]:
    """Filter the adapter's gate list according to the operating mode."""
    if mode == MODE_SAFE:
        return tuple(g for g in adapter.supported_gates if g in SAFE_GATES)
    return adapter.supported_gates


@dataclass(frozen=True)
class PipelineVerdict:
    """Aggregate verdict returned by :func:`validate_patch`.

    Attributes
    ----------
    mode:
        The operating mode the verdict was produced in.
    results:
        Mapping from language id to :class:`ValidationResult`.
    overall_status:
        ``passed`` if every result passed; ``failed`` if any result
        failed; ``skipped`` if nothing was actually validated.
    overall_code:
        First failing ``code`` across all results, or empty string.
    summary:
        Compact summary built by :func:`summarise` for the evidence
        bundle.
    """

    mode: str
    results: Mapping[str, ValidationResult]
    overall_status: str = ValidationStatus.SKIPPED
    overall_code: str = ""
    summary: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "overall_status": self.overall_status,
            "overall_code": self.overall_code,
            "summary": self.summary,
            "results": {
                lang: r.to_dict() for lang, r in self.results.items()
            },
        }

    @property
    def accepted(self) -> bool:
        return self.overall_status == ValidationStatus.PASSED


def validate_patch(
    *,
    registry: AdapterRegistry,
    files: Iterable[FileToValidate],
    mode: str,
    workspace: str = "<staged>",
    timeout_seconds: int = 120,
) -> PipelineVerdict:
    """Run every applicable adapter and return a :class:`PipelineVerdict`.

    The caller is expected to have already produced the staged files;
    this function never touches the disk. ``workspace`` is only used for
    diagnostics (it ends up in the verdict and any error messages).
    """
    if mode not in VALIDATION_MODES:
        return PipelineVerdict(
            mode=mode,
            results={},
            overall_status=ValidationStatus.FAILED,
            overall_code=CODE_UNKNOWN_MODE,
            summary={},
        )

    files_by_lang: dict[str, list[FileToValidate]] = {}
    for file in files:
        files_by_lang.setdefault(file.language, []).append(file)

    results: dict[str, ValidationResult] = {}
    for language, lang_files in sorted(files_by_lang.items()):
        adapter = registry.get(language)
        if adapter is None:
            # No adapter for this language; report structured failure so
            # the repair loop can route around it.
            results[language] = ValidationResult(
                language=language,
                gate_results=(),
                overall_status=ValidationStatus.FAILED,
                overall_code=CODE_ADAPTER_MISSING,
            )
            continue
        context = ValidationContext(
            workspace=workspace,
            files=tuple(lang_files),
            mode=mode,
            timeout_seconds=timeout_seconds,
        )
        try:
            results[language] = adapter.run(context)
        except Exception as exc:  # pragma: no cover - safety net
            results[language] = ValidationResult(
                language=language,
                gate_results=(),
                overall_status=ValidationStatus.FAILED,
                overall_code="adapter_crashed",
            )

    # Compute aggregate verdict.
    overall_status = ValidationStatus.PASSED
    overall_code = ""
    for lang, result in sorted(results.items()):
        if result.overall_status == ValidationStatus.FAILED:
            overall_status = ValidationStatus.FAILED
            if not overall_code:
                overall_code = result.overall_code or CODE_ADAPTER_MISSING
        elif (
            result.overall_status == ValidationStatus.SKIPPED
            and overall_status == ValidationStatus.PASSED
        ):
            # If nothing was actually validated, surface that as
            # ``skipped`` so callers cannot accidentally treat an empty
            # result as a green light.
            overall_status = ValidationStatus.SKIPPED

    return PipelineVerdict(
        mode=mode,
        results=results,
        overall_status=overall_status,
        overall_code=overall_code,
        summary=summarise(results),
    )


def gate_is_allowed(gate: str, *, mode: str) -> bool:
    """Return ``True`` if ``gate`` may run in ``mode``."""
    if mode not in VALIDATION_MODES:
        return False
    if mode == MODE_SAFE:
        return gate in SAFE_GATES
    return True


__all__ = [
    "AdapterRegistry",
    "CODE_ADAPTER_MISSING",
    "CODE_FORBIDDEN_LANGUAGE",
    "CODE_UNKNOWN_MODE",
    "MUTATING_GATES",
    "MODE_APPLY",
    "MODE_AUTONOMOUS",
    "MODE_SAFE",
    "MODE_STAGED",
    "PipelineVerdict",
    "SAFE_GATES",
    "VALIDATION_MODES",
    "gate_is_allowed",
    "validate_patch",
]

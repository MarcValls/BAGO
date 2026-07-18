"""BAGO Code Forge 3B - validation subpackage.

The validation subpackage is the single authority on whether a
candidate patch can land in the workspace. It exposes:

- :class:`AdapterRegistry` and :func:`validate_patch` in
  :mod:`bago_core.validation.validation_pipeline` for routing files to
  the right language adapter and producing a :class:`PipelineVerdict`.
- :class:`LanguageAdapter`, :class:`FileToValidate` and
  :class:`ValidationContext` in
  :mod:`bago_core.validation.language_adapter` for adapter authors.
- :class:`GateResult`, :class:`ValidationResult`,
  :class:`ValidationStatus`, the ``GATE_*`` constants and the
  :func:`summarise` helper in
  :mod:`bago_core.validation.validation_result` for result handling.

Concrete language adapters live under :mod:`bago_core.validation.adapters`.
"""
from __future__ import annotations

from .language_adapter import (
    FileToValidate,
    LanguageAdapter,
    ValidationContext,
)
from .validation_pipeline import (
    AdapterRegistry,
    CODE_ADAPTER_MISSING,
    CODE_FORBIDDEN_LANGUAGE,
    CODE_UNKNOWN_MODE,
    MODE_APPLY,
    MODE_AUTONOMOUS,
    MODE_SAFE,
    MODE_STAGED,
    MUTATING_GATES,
    PipelineVerdict,
    SAFE_GATES,
    VALIDATION_MODES,
    gate_is_allowed,
    validate_patch,
)
from .validation_result import (
    GATE_FORMATTING,
    GATE_IMPORTS,
    GATE_LINT,
    GATE_ORDER,
    GATE_SECURITY,
    GATE_SYNTAX,
    GATE_TESTS,
    GATE_TYPECHECK,
    GateResult,
    ValidationResult,
    ValidationStatus,
    summarise,
)


__all__ = [
    # pipeline
    "AdapterRegistry",
    "PipelineVerdict",
    "validate_patch",
    "gate_is_allowed",
    "MODE_SAFE",
    "MODE_STAGED",
    "MODE_APPLY",
    "MODE_AUTONOMOUS",
    "VALIDATION_MODES",
    "SAFE_GATES",
    "MUTATING_GATES",
    "CODE_ADAPTER_MISSING",
    "CODE_FORBIDDEN_LANGUAGE",
    "CODE_UNKNOWN_MODE",
    # results
    "GateResult",
    "ValidationResult",
    "ValidationStatus",
    "GATE_SYNTAX",
    "GATE_FORMATTING",
    "GATE_LINT",
    "GATE_TYPECHECK",
    "GATE_IMPORTS",
    "GATE_SECURITY",
    "GATE_TESTS",
    "GATE_ORDER",
    "summarise",
    # adapter
    "LanguageAdapter",
    "FileToValidate",
    "ValidationContext",
]

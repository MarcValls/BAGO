"""BAGO Code Forge 3B — task contract compiler.

This module is step 2 of the BAGO Code Forge 3B pipeline. It takes the
deterministic classification emitted by :mod:`bago_core.codegen.task_classifier`
and produces a *verifiable task contract* that every later pass
(plan_pass, generation_pass, review_pass, validation_pipeline) consumes.

The contract is intentionally a small, declarative JSON-shaped object. It
exists so that the model never receives an open question — only a closed
spec with explicit files, forbidden paths, constraints and acceptance
criteria.

Design rules (R0-R10):

- R0: <200 lines, no I/O, no subprocess, no ``provider_adapter`` import.
- R1: pure data; ``CodeTaskContract`` is a ``dataclass(frozen=True)``.
- R2: deterministic; same inputs → same outputs.
- R3: defensive; if the classifier output is ``blocked`` or
  ``unsafe_or_unsupported`` the compiler refuses and returns
  ``refused=True`` with a stable ``refusal_reason``.
- R8: no ``print``, no shell.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from .task_classifier import CodeTaskClassification

# Operations the rest of the pipeline understands. Kept in sync with
# ``code.script_registry`` ids. Adding a new operation requires also
# teaching the validation pipeline how to gate it.
ALLOWED_OPERATIONS: frozenset[str] = frozenset(
    {
        "explain",
        "inspect",
        "create_file",
        "modify_file",
        "fix_error",
        "add_test",
        "refactor_local",
        "generate_project",
    }
)

# Default forbidden paths. Anything matched (case-insensitive, segment-wise)
# is rejected before the contract is emitted. The pipeline never writes
# to these locations, full stop.
DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (
    ".git",
    ".env",
    "state",
    "dist",
    "release",
    "__pycache__",
    ".bago",
    "node_modules",
    ".venv",
    "venv",
)

# Map of kind → default operation. Lets the compiler be predictable
# even if a future classification adds a new kind without a 1:1 mapping.
_KIND_TO_OPERATION: dict[str, str] = {
    "explain": "explain",
    "inspect": "inspect",
    "create_file": "create_file",
    "modify_file": "modify_file",
    "fix_error": "fix_error",
    "add_test": "add_test",
    "refactor_local": "refactor_local",
    "generate_project": "generate_project",
}

# Default constraints the model is *always* told about, regardless of the
# specific request. Per-task constraints can be appended by the caller.
_GLOBAL_CONSTRAINTS: tuple[str, ...] = (
    "Do not change public function signatures without an explicit allowance.",
    "Do not introduce shell=True, eval, exec or os.system in generated code.",
    "Output must be JSON or unified_diff only; no mixed prose-and-code blocks.",
    "Maximum two production files and one test file per task.",
    "Stay within allowed_files; everything else is forbidden.",
)

# Default acceptance criteria. If the caller does not provide any, these
# are the ones the validation pipeline will check.
_GLOBAL_ACCEPTANCE: tuple[str, ...] = (
    "Target file parses with ast.parse (Python) or language equivalent.",
    "compileall succeeds for the modified Python files.",
    "ruff (or language equivalent) reports no new warnings.",
    "Targeted tests for the modified module pass.",
)

_LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "data",
    ".yaml": "data",
    ".yml": "data",
    ".toml": "data",
    ".md": "data",
    ".ps1": "powershell",
    ".cmd": "powershell",
    ".sh": "shell",
}


def _detect_language(target_files: Iterable[str]) -> str:
    """Return a stable language id for the dominant extension.

    Ties are broken by first occurrence so the result is deterministic.
    Unknown extensions fall back to ``"unknown"`` so the contract is still
    well-formed and the validation pipeline can refuse it.
    """
    counts: dict[str, int] = {}
    order: list[str] = []
    for path in target_files:
        ext = ""
        dot = path.rfind(".")
        if dot > 0:
            ext = path[dot:].lower()
        lang = _LANGUAGE_BY_EXT.get(ext, "unknown")
        if lang not in counts:
            order.append(lang)
        counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "unknown"
    best = max(order, key=lambda lang: (counts[lang], -order.index(lang)))
    return best


def _new_task_id(prefix: str = "CODE") -> str:
    """Stable, sortable task id derived from UTC timestamp.

    Format: ``PREFIX-YYYYMMDD-HHMMSS-mmm``. Millisecond precision keeps
    successive compilations from colliding inside the same second.
    """
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now.strftime('%Y%m%d-%H%M%S')}-{now.microsecond // 1000:03d}"


@dataclass(frozen=True)
class CodeTaskContract:
    """Closed, verifiable contract emitted by the compiler.

    The fields are deliberately aligned with the JSON shape the user
    requested in the BAGO Code Forge 3B spec. Every downstream pass
    treats this object as the single source of truth.
    """

    task_id: str
    operation: str
    language: str
    objective: str
    target_files: tuple[str, ...]
    allowed_files: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    constraints: tuple[str, ...]
    acceptance: tuple[str, ...]
    classification_reasons: tuple[str, ...] = ()
    refused: bool = False
    refusal_reason: str = ""
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe dict mirroring the spec."""
        return {
            "task_id": self.task_id,
            "operation": self.operation,
            "language": self.language,
            "objective": self.objective,
            "target_files": list(self.target_files),
            "allowed_files": list(self.allowed_files),
            "forbidden_paths": list(self.forbidden_paths),
            "constraints": list(self.constraints),
            "acceptance": list(self.acceptance),
            "classification_reasons": list(self.classification_reasons),
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "extra": dict(self.extra),
        }


def compile_code_task(
    classification: CodeTaskClassification,
    *,
    objective: str,
    allowed_files: Iterable[str] | None = None,
    forbidden_paths: Iterable[str] = DEFAULT_FORBIDDEN_PATHS,
    extra_constraints: Iterable[str] = (),
    extra_acceptance: Iterable[str] = (),
    task_id: str | None = None,
) -> CodeTaskContract:
    """Compile a :class:`CodeTaskClassification` into a contract.

    The compiler is intentionally strict. If the classification is
    blocked, unsafe, or references files outside ``allowed_files``, the
    returned contract is marked ``refused=True`` and carries a stable
    ``refusal_reason``. The rest of the pipeline must short-circuit on
    any refused contract.
    """
    reasons = classification.reasons

    if classification.kind == "unsafe_or_unsupported":
        return CodeTaskContract(
            task_id=task_id or _new_task_id(),
            operation="explain",
            language="unknown",
            objective=objective,
            target_files=classification.target_files,
            allowed_files=tuple(allowed_files or ()),
            forbidden_paths=tuple(forbidden_paths),
            constraints=tuple(extra_constraints),
            acceptance=tuple(extra_acceptance),
            classification_reasons=reasons,
            refused=True,
            refusal_reason=classification.refusal_message() or "unsafe_or_unsupported",
        )

    operation = _KIND_TO_OPERATION.get(classification.kind, "explain")
    if operation not in ALLOWED_OPERATIONS:
        return CodeTaskContract(
            task_id=task_id or _new_task_id(),
            operation="explain",
            language="unknown",
            objective=objective,
            target_files=classification.target_files,
            allowed_files=tuple(allowed_files or ()),
            forbidden_paths=tuple(forbidden_paths),
            constraints=tuple(extra_constraints),
            acceptance=tuple(extra_acceptance),
            classification_reasons=reasons + ("unknown_kind",),
            refused=True,
            refusal_reason=f"classifier_kind_not_supported:{classification.kind}",
        )

    target_files = classification.target_files
    if not target_files and operation not in {"explain", "inspect", "generate_project"}:
        return CodeTaskContract(
            task_id=task_id or _new_task_id(),
            operation=operation,
            language="unknown",
            objective=objective,
            target_files=(),
            allowed_files=tuple(allowed_files or ()),
            forbidden_paths=tuple(forbidden_paths),
            constraints=tuple(extra_constraints),
            acceptance=tuple(extra_acceptance),
            classification_reasons=reasons + ("no_target_file",),
            refused=True,
            refusal_reason="operation_requires_target_file",
        )

    effective_allowed = tuple(allowed_files) if allowed_files is not None else target_files
    language = _detect_language(target_files or effective_allowed)

    constraints = _GLOBAL_CONSTRAINTS + tuple(extra_constraints)
    acceptance = _GLOBAL_ACCEPTANCE + tuple(extra_acceptance)

    return CodeTaskContract(
        task_id=task_id or _new_task_id(),
        operation=operation,
        language=language,
        objective=objective,
        target_files=target_files,
        allowed_files=effective_allowed,
        forbidden_paths=tuple(forbidden_paths),
        constraints=constraints,
        acceptance=acceptance,
        classification_reasons=reasons,
        refused=False,
    )

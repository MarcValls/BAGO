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
from pathlib import Path
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


@dataclass(frozen=True)
class CodeTaskPlan:
    """Deterministic execution plan for a code task.

    The plan gives downstream tooling an explicit answer to:
    - what should be read
    - what should be edited
    - what should be created
    - how to verify completion
    - what message to emit when the task finishes
    """

    read_files: tuple[str, ...] = ()
    edit_files: tuple[str, ...] = ()
    create_files: tuple[str, ...] = ()
    verify_steps: tuple[str, ...] = ()
    finish_message: str = ""
    requires_model_review: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "read_files": list(self.read_files),
            "edit_files": list(self.edit_files),
            "create_files": list(self.create_files),
            "verify_steps": list(self.verify_steps),
            "finish_message": self.finish_message,
            "requires_model_review": self.requires_model_review,
            "notes": list(self.notes),
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
    plan: CodeTaskPlan = field(default_factory=CodeTaskPlan)
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
            "plan": self.plan.to_dict(),
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "extra": dict(self.extra),
        }


def _unique_paths(paths: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for raw in paths:
        item = str(raw).strip()
        if item:
            seen.setdefault(item, None)
    return tuple(seen.keys())


def _infer_test_targets(target_files: Iterable[str]) -> tuple[str, ...]:
    inferred: list[str] = []
    for raw in target_files:
        path = Path(raw)
        stem = path.stem
        suffix = path.suffix.lower()
        if not stem:
            continue
        if suffix in {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs"}:
            inferred.append(str(path.with_name(f"test_{stem}.py")))
            inferred.append(str(path.with_name(f"{stem}_test.py")))
            inferred.append(str(Path("tests") / f"test_{stem}.py"))
        else:
            inferred.append(str(Path("tests") / f"test_{stem}.py"))
    return _unique_paths(inferred)


def _build_plan(
    classification: CodeTaskClassification,
    *,
    operation: str,
    target_files: tuple[str, ...],
    refused: bool,
) -> CodeTaskPlan:
    read_files = target_files
    edit_files: tuple[str, ...] = ()
    create_files: tuple[str, ...] = ()
    verify_steps: list[str] = []
    notes: list[str] = list(classification.reasons)

    if refused:
        return CodeTaskPlan(
            read_files=read_files,
            edit_files=edit_files,
            create_files=create_files,
            verify_steps=(),
            finish_message="Pedir aclaración o bloquear la ejecución.",
            requires_model_review=True,
            notes=tuple(notes or ("refused",)),
        )

    if operation in {"explain", "inspect"}:
        finish_message = "Devuelve el análisis sin modificar archivos."
        verify_steps.append("Confirmar que no se han escrito archivos.")
        if not read_files:
            notes.append("sin_ficheros_objetivo")
    elif operation == "create_file":
        create_files = target_files
        finish_message = "Crear los archivos indicados y validar su existencia."
        verify_steps.extend([
            "Confirmar que los archivos nuevos existen.",
            "Verificar sintaxis o parseo básico del contenido creado.",
        ])
    elif operation in {"modify_file", "fix_error", "refactor_local"}:
        edit_files = target_files
        finish_message = "Editar los archivos objetivo y cerrar la tarea con verificación."
        verify_steps.extend([
            "Revisar los archivos editados.",
            "Ejecutar la validación mínima correspondiente.",
        ])
        if operation == "fix_error":
            notes.append("priorizar_reproduccion_del_error")
        if operation == "refactor_local":
            notes.append("mantener_comportamiento")
    elif operation == "add_test":
        edit_files = ()
        create_files = _infer_test_targets(target_files)
        finish_message = "Añadir pruebas y ejecutar la batería relevante."
        verify_steps.extend([
            "Confirmar que las pruebas nuevas existen.",
            "Ejecutar el subconjunto de tests afectado.",
        ])
        if not create_files:
            notes.append("no_test_target_inferido")
            requires_model_review = True
        else:
            requires_model_review = False
    elif operation == "generate_project":
        create_files = target_files
        finish_message = "Generar el esqueleto del proyecto y validar la estructura."
        verify_steps.extend([
            "Confirmar que la estructura básica existe.",
            "Validar la salida inicial del scaffold.",
        ])
    else:
        finish_message = "Resolver la tarea según el contrato emitido."
        verify_steps.append("Cerrar la tarea con verificación manual.")

    if operation in {"modify_file", "fix_error", "refactor_local"} and target_files:
        read_files = _unique_paths((*target_files, *read_files))
        if operation == "refactor_local":
            create_files = ()
    if operation == "add_test" and target_files:
        read_files = _unique_paths(read_files)
        if not create_files:
            create_files = _infer_test_targets(target_files)

    requires_model_review = bool(
        refused
        or (operation in {"explain", "inspect"} and not read_files)
        or (operation == "add_test" and not create_files)
        or classification.confidence < 0.7
    )

    if not verify_steps:
        verify_steps.append("Validar que la salida final coincide con el objetivo.")

    return CodeTaskPlan(
        read_files=_unique_paths(read_files),
        edit_files=_unique_paths(edit_files),
        create_files=_unique_paths(create_files),
        verify_steps=tuple(verify_steps),
        finish_message=finish_message,
        requires_model_review=requires_model_review,
        notes=tuple(dict.fromkeys(notes)),
    )


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
        plan = _build_plan(
            classification,
            operation="explain",
            target_files=classification.target_files,
            refused=True,
        )
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
            plan=plan,
            refused=True,
            refusal_reason=classification.refusal_message() or "unsafe_or_unsupported",
        )

    operation = _KIND_TO_OPERATION.get(classification.kind, "explain")
    if operation not in ALLOWED_OPERATIONS:
        plan = _build_plan(
            classification,
            operation="explain",
            target_files=classification.target_files,
            refused=True,
        )
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
            plan=plan,
            refused=True,
            refusal_reason=f"classifier_kind_not_supported:{classification.kind}",
        )

    target_files = classification.target_files
    if not target_files and operation not in {"explain", "inspect", "generate_project"}:
        plan = _build_plan(
            classification,
            operation=operation,
            target_files=(),
            refused=True,
        )
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
            plan=plan,
            refused=True,
            refusal_reason="operation_requires_target_file",
        )

    effective_allowed = tuple(allowed_files) if allowed_files is not None else target_files
    language = _detect_language(target_files or effective_allowed)

    constraints = _GLOBAL_CONSTRAINTS + tuple(extra_constraints)
    acceptance = _GLOBAL_ACCEPTANCE + tuple(extra_acceptance)
    plan = _build_plan(
        classification,
        operation=operation,
        target_files=target_files,
        refused=False,
    )

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
        plan=plan,
        refused=False,
    )

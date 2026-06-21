"""BAGO Code Forge 3B - repair loop.

Step 12 of the BAGO Code Forge 3B pipeline. Drives the
generation -> validation -> repair cycle, capped at a small number of
attempts (default 3).

The loop is the seam between the **generative** layer (the model) and
the **deterministic** layer (the validation pipeline). Its only
responsibility is to:

1. Call the caller-supplied generator with a focused prompt
   (contract + minimal context + last error excerpt).
2. Parse whatever the model produced. A malformed patch is itself an
   error the loop must repair.
3. Apply the patch in memory against the staged files.
4. Hand the staged files to the validation pipeline.
5. If the verdict is ``accepted`` -> stop. If the verdict is ``failed``
   and we still have attempts left, build a focused repair prompt
   (only the failing gate, only the offending lines) and call the
   generator again. If the verdict is ``failed`` and we are out of
   attempts -> ``rejected``.

The loop is intentionally **not** smart about prompt engineering. The
``build_repair_prompt`` helper is just a deterministic function from
``RepairFeedback -> dict``; whoever wires the loop in production can
swap the prompt shape without touching the state machine.

Design rules (R0-R10):

- R1: dataclasses are ``frozen=True``; verdict is JSON-serialisable.
- R2: deterministic. Same inputs (contract, context, staged files,
  mock generator, mock validator) -> same verdict.
- R3: stable codes the evidence bundle dispatches on:
  ``accepted``, ``rejected_max_attempts``, ``rejected_unrecoverable``,
  ``rejected_refused``, ``rejected_parse_failed``.
- R4: max 3 attempts by default. The loop must never keep retrying
  forever - the model can hallucinate or thrash.
- R5: never raises. Generator/parse/validate exceptions become
  ``rejected_parse_failed`` / ``rejected_unrecoverable`` verdicts.
- R8: no subprocess, no I/O. The patch application is pure string
  surgery; real disk writes belong to ``atomic_patch`` (step 15).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from .context_builder import CodeContext
from .patch_parser import (
    Hunk,
    HunkLine,
    Patch,
    PatchParseError,
    parse_patch,
)
from .task_compiler import CodeTaskContract
from ..validation.validation_pipeline import (
    PipelineVerdict,
    validate_patch,
)
from ..validation.language_adapter import FileToValidate
from ..validation.validation_result import (
    GATE_ORDER,
    GateResult,
    ValidationStatus,
)


# Hard cap on repair attempts. The design spec is explicit: a 3B model
# thrashes after 3 passes; 4+ is almost always pure hallucination.
DEFAULT_MAX_ATTEMPTS = 3

# Stable codes the evidence bundle can switch on.
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED_MAX_ATTEMPTS = "rejected_max_attempts"
STATUS_REJECTED_UNRECOVERABLE = "rejected_unrecoverable"
STATUS_REJECTED_REFUSED = "rejected_refused"
STATUS_REJECTED_PARSE_FAILED = "rejected_parse_failed"

ALL_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_ACCEPTED,
        STATUS_REJECTED_MAX_ATTEMPTS,
        STATUS_REJECTED_UNRECOVERABLE,
        STATUS_REJECTED_REFUSED,
        STATUS_REJECTED_PARSE_FAILED,
    }
)


# ----------------------------------------------------------------------------
# Public data types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class RepairFeedback:
    """The minimal, focused feedback fed back to the model.

    The loop never hands the model the whole log of a failed test
    suite; it only hands it the failing gate's code, the offending
    lines (best effort) and the original contract.
    """

    attempt: int
    maximum_attempts: int
    failing_gate: str
    failing_code: str
    failing_message: str
    offending_path: str
    offending_line: int
    offending_excerpt: str
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "maximum_attempts": self.maximum_attempts,
            "failing_gate": self.failing_gate,
            "failing_code": self.failing_code,
            "failing_message": self.failing_message,
            "offending_path": self.offending_path,
            "offending_line": self.offending_line,
            "offending_excerpt": self.offending_excerpt,
            "extra": dict(self.extra),
        }


@dataclass(frozen=True)
class RepairAttempt:
    """One iteration of the generation -> validation cycle."""

    index: int
    prompt_kind: str  # "initial" | "repair"
    raw_output: str
    patches: tuple[Patch, ...] = ()
    feedback: RepairFeedback | None = None
    verdict: PipelineVerdict | None = None
    parse_error: str = ""

    @property
    def accepted(self) -> bool:
        return bool(self.verdict and self.verdict.accepted)

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "prompt_kind": self.prompt_kind,
            "raw_output": self.raw_output,
            "patches": [p.to_dict() for p in self.patches],
            "feedback": self.feedback.to_dict() if self.feedback else None,
            "verdict": self.verdict.to_dict() if self.verdict else None,
            "parse_error": self.parse_error,
        }


@dataclass(frozen=True)
class RepairVerdict:
    """The aggregate outcome of the loop."""

    status: str
    attempts: tuple[RepairAttempt, ...]
    final_patches: tuple[Patch, ...] = ()
    final_verdict: PipelineVerdict | None = None
    refusal_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "refusal_reason": self.refusal_reason,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_patches": [p.to_dict() for p in self.final_patches],
            "final_verdict": self.final_verdict.to_dict() if self.final_verdict else None,
        }

    @property
    def accepted(self) -> bool:
        return self.status == STATUS_ACCEPTED


# ----------------------------------------------------------------------------
# Type aliases for injected dependencies
# ----------------------------------------------------------------------------


#: Generator signature: receives a dict-shaped prompt and must return
#: either a unified diff (str) or a ``{"patches": [Patch, ...]}`` dict.
#: Strings are the only thing the loop cares about.
Generator = Callable[[dict[str, object]], str]


#: Validator signature: keeps the loop decoupled from the real
#: :func:`validate_patch`. Test code injects a stub.
Validator = Callable[[Mapping[str, FileToValidate], str], PipelineVerdict]


# ----------------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------------


def _safe_staged_files(context: CodeContext) -> dict[str, str]:
    """Return ``path -> body`` for every file the model is allowed to see.

    The validation pipeline expects the **post-patch** state. The loop
    starts with whatever the context builder recorded, then mutates it
    in memory as patches come in.
    """
    files: dict[str, str] = {}
    for summary in context.target_summaries:
        files[summary.path] = summary.body
    return files


def _apply_patch_to_memory(
    files: dict[str, str], patch: Patch
) -> tuple[dict[str, str], tuple[str, int, str] | None]:
    """Apply one ``Patch`` to an in-memory file map.

    Returns the new map and a ``(path, line, message)`` tuple if the
    patch referenced a line that doesn't exist; ``None`` on success.
    The validator is run after every patch so a bad patch is caught
    fast.
    """
    new_files = dict(files)
    body = new_files.get(patch.new_path, "")
    lines = body.splitlines(keepends=False) if body else []
    # Convert 1-based line numbers into 0-based indices.
    for hunk in patch.hunks:
        idx = max(0, hunk.new_start - 1)
        for line in hunk.lines:
            if line.marker == " ":
                if idx >= len(lines) or lines[idx] != line.text:
                    return new_files, (
                        patch.new_path,
                        hunk.new_start,
                        f"context mismatch at line {hunk.new_start}",
                    )
                idx += 1
            elif line.marker == "-":
                # Deletions in unified diff come from the *old* file;
                # when applying to a synthesized new file we skip them.
                continue
            elif line.marker == "+":
                lines.insert(idx, line.text)
                idx += 1
            elif line.marker == "\\":
                # Informational; ignored here.
                continue
            else:  # pragma: no cover - patch_parser rejects unknowns
                return new_files, (
                    patch.new_path,
                    hunk.new_start,
                    f"unknown marker {line.marker!r}",
                )
    new_files[patch.new_path] = "\n".join(lines) + (
        "\n" if lines and not lines[-1].endswith("\n") else ""
    )
    return new_files, None


def _build_files_to_validate(
    files: dict[str, str], context: CodeContext
) -> dict[str, FileToValidate]:
    """Wrap the in-memory file map into ``FileToValidate`` objects.

    The language is borrowed from the contract via the context, falling
    back to the file extension heuristic. The validator only needs the
    language id to pick an adapter.
    """
    language = context.contract.language or "python"
    out: dict[str, FileToValidate] = {}
    for path, body in files.items():
        out[path] = FileToValidate(
            path=path, language=language, body=body,
        )
    return out


def _build_initial_prompt(
    contract: CodeTaskContract, context: CodeContext
) -> dict[str, object]:
    """Shape the first-pass prompt. Deterministic and JSON-safe."""
    return {
        "phase": "initial",
        "contract": contract.to_dict(),
        "context": context.to_dict(),
    }


def _build_repair_prompt(
    contract: CodeTaskContract,
    context: CodeContext,
    feedback: RepairFeedback,
) -> dict[str, object]:
    """Shape a focused repair prompt.

    The model receives the contract, the context, and *only* the
    failing gate. It does not see the full validation log.
    """
    return {
        "phase": "repair",
        "contract": contract.to_dict(),
        "context": context.to_dict(),
        "feedback": feedback.to_dict(),
    }


def _coerce_to_patches(raw: str) -> tuple[Patch, ...]:
    """Parse a raw model output into a tuple of :class:`Patch`.

    Accepts:
    - a unified diff string (preferred);
    - a JSON object of the form ``{"patches": [...]}`` (fallback);
    - a JSON object of the form ``{"diff": "..."}`` (fallback);
    - any other string -> raised as ``PatchParseError`` by ``parse_patch``.
    """
    text = raw.strip()
    if not text:
        return ()
    if text.startswith("{") and text.endswith("}"):
        import json
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if isinstance(data, dict):
            diff = data.get("diff") or data.get("patch")
            if isinstance(diff, str) and diff.strip():
                return (parse_patch(diff),)
            raw_patches = data.get("patches")
            if isinstance(raw_patches, list) and raw_patches:
                # Reconstruct patches from structured form. The keys we
                # accept are ``diff``, ``patch``, ``content`` (unified
                # diff) or ``old_path``/``new_path``/``hunks``.
                collected: list[Patch] = []
                for entry in raw_patches:
                    if not isinstance(entry, dict):
                        continue
                    body = (
                        entry.get("diff")
                        or entry.get("patch")
                        or entry.get("content")
                    )
                    if isinstance(body, str) and body.strip():
                        collected.append(parse_patch(body))
                if collected:
                    return tuple(collected)
    return (parse_patch(text),)


def _extract_failing_lines(patch: Patch, code: str) -> tuple[str, int, str]:
    """Best-effort extraction of the offending line from a failing patch.

    Returns ``(path, line, excerpt)`` based on the first hunk that
    mentions a line whose marker is ``"+"`` (a candidate change) and
    whose content matches a hint in the failure ``code``. Falls back
    to the first hunk header.
    """
    for hunk in patch.hunks:
        first = next(
            (l for l in hunk.lines if l.marker == "+"),
            None,
        )
        if first is not None:
            return (
                patch.new_path,
                hunk.new_start,
                first.text[:400],
            )
    if patch.hunks:
        h = patch.hunks[0]
        return patch.new_path, h.new_start, h.lines[0].text[:400] if h.lines else code
    return patch.new_path, 0, code


def _build_feedback(
    *,
    attempt_index: int,
    maximum_attempts: int,
    verdict: PipelineVerdict | None,
    patches: tuple[Patch, ...],
    fallback_code: str,
    fallback_message: str,
) -> RepairFeedback:
    """Build a :class:`RepairFeedback` from a failed attempt."""
    if verdict is None:
        return RepairFeedback(
            attempt=attempt_index,
            maximum_attempts=maximum_attempts,
            failing_gate="parse",
            failing_code=fallback_code,
            failing_message=fallback_message,
            offending_path="",
            offending_line=0,
            offending_excerpt="",
        )
    gate: GateResult | None = None
    for lang, result in verdict.results.items():
        candidate = result.first_failure()
        if candidate is not None:
            gate = candidate
            break
    if gate is None:
        return RepairFeedback(
            attempt=attempt_index,
            maximum_attempts=maximum_attempts,
            failing_gate="verdict",
            failing_code=fallback_code,
            failing_message=fallback_message,
            offending_path="",
            offending_line=0,
            offending_excerpt="",
        )
    if patches:
        path, line, excerpt = _extract_failing_lines(patches[0], gate.code)
    else:
        path = next(iter(verdict.results), "")
        line = 0
        excerpt = gate.message
    return RepairFeedback(
        attempt=attempt_index,
        maximum_attempts=maximum_attempts,
        failing_gate=gate.gate,
        failing_code=gate.code or fallback_code,
        failing_message=gate.message or fallback_message,
        offending_path=path,
        offending_line=line,
        offending_excerpt=excerpt,
    )


# ----------------------------------------------------------------------------
# The loop
# ----------------------------------------------------------------------------


def run_repair_loop(
    *,
    contract: CodeTaskContract,
    context: CodeContext,
    generator: Generator,
    validator: Validator,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> RepairVerdict:
    """Drive the generate -> validate -> repair cycle.

    Parameters
    ----------
    contract:
        The compiled task contract. If ``contract.refused`` is true the
        loop short-circuits with ``STATUS_REJECTED_REFUSED`` and the
        generator is never called.
    context:
        The minimal context the model is allowed to see.
    generator:
        Callable that takes a dict-shaped prompt and returns either a
        unified diff string or a JSON envelope. Same callable is
        invoked for initial and repair passes.
    validator:
        Callable that takes the staged files and the operating mode
        and returns a :class:`PipelineVerdict`. Usually
        :func:`bago_core.validation.validate_patch`.
    max_attempts:
        Cap on the number of generate -> validate rounds. Defaults to
        :data:`DEFAULT_MAX_ATTEMPTS` (3).
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if contract.refused:
        return RepairVerdict(
            status=STATUS_REJECTED_REFUSED,
            attempts=(),
            refusal_reason=contract.refusal_reason,
        )

    staged = _safe_staged_files(context)
    attempts: list[RepairAttempt] = []
    feedback: RepairFeedback | None = None

    for index in range(1, max_attempts + 1):
        if feedback is None:
            prompt = _build_initial_prompt(contract, context)
            prompt_kind = "initial"
        else:
            prompt = _build_repair_prompt(contract, context, feedback)
            prompt_kind = "repair"

        try:
            raw = generator(prompt)
        except Exception as exc:  # pragma: no cover - safety net
            return RepairVerdict(
                status=STATUS_REJECTED_UNRECOVERABLE,
                attempts=tuple(attempts),
                refusal_reason=f"generator_crashed:{type(exc).__name__}",
            )

        try:
            patches = _coerce_to_patches(raw)
        except PatchParseError as exc:
            attempt = RepairAttempt(
                index=index,
                prompt_kind=prompt_kind,
                raw_output=raw,
                patches=(),
                feedback=feedback,
                verdict=None,
                parse_error=exc.code,
            )
            attempts.append(attempt)
            feedback = _build_feedback(
                attempt_index=index,
                maximum_attempts=max_attempts,
                verdict=None,
                patches=(),
                fallback_code=exc.code or "patch_parse_failed",
                fallback_message=str(exc),
            )
            continue

        if not patches:
            attempt = RepairAttempt(
                index=index,
                prompt_kind=prompt_kind,
                raw_output=raw,
                patches=(),
                feedback=feedback,
                verdict=None,
                parse_error="empty_patch",
            )
            attempts.append(attempt)
            feedback = _build_feedback(
                attempt_index=index,
                maximum_attempts=max_attempts,
                verdict=None,
                patches=(),
                fallback_code="empty_patch",
                fallback_message="generator returned no patch",
            )
            continue

        # Apply every patch in order. Stop at the first that fails.
        apply_error: tuple[str, int, str] | None = None
        for patch in patches:
            staged, apply_error = _apply_patch_to_memory(staged, patch)
            if apply_error is not None:
                break

        if apply_error is not None:
            attempt = RepairAttempt(
                index=index,
                prompt_kind=prompt_kind,
                raw_output=raw,
                patches=patches,
                feedback=feedback,
                verdict=None,
                parse_error="patch_apply_failed",
            )
            attempts.append(attempt)
            path, line, message = apply_error
            feedback = RepairFeedback(
                attempt=index,
                maximum_attempts=max_attempts,
                failing_gate="apply",
                failing_code="patch_apply_failed",
                failing_message=message,
                offending_path=path,
                offending_line=line,
                offending_excerpt=message,
            )
            continue

        # Validation pass.
        files_to_validate = _build_files_to_validate(staged, context)
        verdict = validator(files_to_validate, contract.language or "python")
        attempt = RepairAttempt(
            index=index,
            prompt_kind=prompt_kind,
            raw_output=raw,
            patches=patches,
            feedback=feedback,
            verdict=verdict,
        )
        attempts.append(attempt)

        if verdict.accepted:
            return RepairVerdict(
                status=STATUS_ACCEPTED,
                attempts=tuple(attempts),
                final_patches=patches,
                final_verdict=verdict,
            )

        feedback = _build_feedback(
            attempt_index=index,
            maximum_attempts=max_attempts,
            verdict=verdict,
            patches=patches,
            fallback_code=verdict.overall_code or "validation_failed",
            fallback_message="validation pipeline rejected the patch",
        )

    return RepairVerdict(
        status=STATUS_REJECTED_MAX_ATTEMPTS,
        attempts=tuple(attempts),
        final_patches=attempts[-1].patches if attempts else (),
        final_verdict=attempts[-1].verdict if attempts else None,
        refusal_reason="max_attempts_exceeded",
    )


__all__ = [
    "ALL_STATUSES",
    "DEFAULT_MAX_ATTEMPTS",
    "Generator",
    "RepairAttempt",
    "RepairFeedback",
    "RepairVerdict",
    "STATUS_ACCEPTED",
    "STATUS_REJECTED_MAX_ATTEMPTS",
    "STATUS_REJECTED_PARSE_FAILED",
    "STATUS_REJECTED_REFUSED",
    "STATUS_REJECTED_UNRECOVERABLE",
    "Validator",
    "run_repair_loop",
]

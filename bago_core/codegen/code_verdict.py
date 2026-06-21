"""BAGO Code Forge 3B - high-level code verdict.

Step 13 of the BAGO Code Forge 3B pipeline. The repair loop already
emits a :class:`bago_core.codegen.repair_loop.RepairVerdict` for the
generate -> validate -> repair cycle, but the rest of BAGO (the
``STAGED``/``APPLY``/``AUTONOMOUS`` mode switches, the evidence
builder, the human-facing notifications) needs a smaller, more
declarative verdict that only answers three questions:

1. Did the cycle end with a green validation? -> ``accepted``.
2. Did the cycle end without a green validation but the
   :class:`RepairVerdict` carries something the user can still act
   on? -> ``needs_repair`` (or ``needs_review`` when the failure
   needs human eyes).
3. Did the cycle end with nothing usable? -> ``rejected``.

``code_verdict`` is the *single* place that collapses the
:class:`RepairVerdict` taxonomy
(``accepted``/``rejected_max_attempts``/``rejected_unrecoverable``/
``rejected_refused``/``rejected_parse_failed``) into the three-way
verdict the rest of BAGO actually consumes.

Design rules (R0-R10):

- R0: <200 lines, no I/O, no subprocess.
- R1: pure data; :class:`CodeVerdict` is ``frozen=True`` and JSON-safe
  via :meth:`to_dict`.
- R2: deterministic. Same inputs -> same verdict.
- R3: stable verdict ids the policy layer dispatches on:
  ``accepted``, ``needs_repair``, ``needs_review``, ``rejected``.
- R4: never raises. Unknown repair statuses fall back to
  ``rejected`` with a stable ``reason="unknown_repair_status"`` so
  the caller can escalate instead of crashing.
- R8: no ``print``, no shell, no model calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .repair_loop import (
    RepairAttempt,
    RepairVerdict,
    STATUS_ACCEPTED,
    STATUS_REJECTED_MAX_ATTEMPTS,
    STATUS_REJECTED_PARSE_FAILED,
    STATUS_REJECTED_REFUSED,
    STATUS_REJECTED_UNRECOVERABLE,
)
from ..validation.validation_pipeline import (
    MODE_APPLY,
    MODE_AUTONOMOUS,
    MODE_SAFE,
    MODE_STAGED,
    PipelineVerdict,
    VALIDATION_MODES,
)
from ..validation.validation_result import ValidationStatus


# Stable verdict ids the policy layer dispatches on.
VERDICT_ACCEPTED = "accepted"
VERDICT_NEEDS_REPAIR = "needs_repair"
VERDICT_NEEDS_REVIEW = "needs_review"
VERDICT_REJECTED = "rejected"

ALL_VERDICTS: frozenset[str] = frozenset(
    {
        VERDICT_ACCEPTED,
        VERDICT_NEEDS_REPAIR,
        VERDICT_NEEDS_REVIEW,
        VERDICT_REJECTED,
    }
)


# Stable reason codes attached to non-accepted verdicts. They mirror
# the repair loop status ids 1:1 so the evidence bundle can join on
# them, plus a few extras for the verdict layer itself.
REASON_ACCEPTED = "accepted"
REASON_MAX_ATTEMPTS_EXCEEDED = "max_attempts_exceeded"
REASON_GENERATOR_CRASHED = "generator_crashed"
REASON_PATCH_PARSE_FAILED = "patch_parse_failed"
REASON_CONTRACT_REFUSED = "contract_refused"
REASON_PIPELINE_FAILED = "pipeline_failed"
REASON_PIPELINE_REJECTED = "pipeline_rejected"
REASON_UNKNOWN_REPAIR_STATUS = "unknown_repair_status"
REASON_UNSAFE_MODE = "unsafe_mode"


# Codes that the human (not the model) must look at before the patch
# can land. They map to ``needs_review`` so the UI can show a separate
# "review" bucket.
_REVIEW_ONLY_CODES: frozenset[str] = frozenset(
    {
        REASON_CONTRACT_REFUSED,
        REASON_GENERATOR_CRASHED,
        REASON_UNKNOWN_REPAIR_STATUS,
    }
)


@dataclass(frozen=True)
class CodeVerdict:
    """The high-level verdict the rest of BAGO consumes.

    Attributes
    ----------
    verdict:
        One of :data:`ALL_VERDICTS`.
    reason:
        Stable machine-readable explanation. Always present, even on
        success (``"accepted"``), so the evidence bundle never has to
        branch on ``verdict`` first.
    mode:
        The validation mode the verdict was produced in. Carried
        through so downstream mode policy can audit the choice.
    repair_status:
        The original :class:`RepairVerdict.status` the verdict was
        derived from. Lets callers correlate the verdict with the
        full attempt history.
    attempt_count:
        How many generate -> validate rounds were actually used.
    failure_codes:
        Stable codes the validation pipeline reported (e.g.
        ``FORMATTER_REJECTED``). Empty on success.
    failure_gates:
        Gate ids the validation pipeline flagged. Empty on success.
    can_apply:
        ``True`` iff :attr:`verdict` is ``accepted`` *and* the mode is
        safe enough for an unattended apply. ``APPLY`` and
        ``AUTONOMOUS`` both qualify; ``STAGED`` and ``SAFE`` do not.
    extra:
        Free-form context for the evidence bundle (always JSON-safe).
    """

    verdict: str
    reason: str
    mode: str = MODE_SAFE
    repair_status: str = ""
    attempt_count: int = 0
    failure_codes: tuple[str, ...] = ()
    failure_gates: tuple[str, ...] = ()
    can_apply: bool = False
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "mode": self.mode,
            "repair_status": self.repair_status,
            "attempt_count": self.attempt_count,
            "failure_codes": list(self.failure_codes),
            "failure_gates": list(self.failure_gates),
            "can_apply": self.can_apply,
            "extra": dict(self.extra),
        }

    @property
    def accepted(self) -> bool:
        return self.verdict == VERDICT_ACCEPTED

    @property
    def rejected(self) -> bool:
        return self.verdict == VERDICT_REJECTED


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _collect_failures(
    verdict: PipelineVerdict | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(codes, gates)`` for a :class:`PipelineVerdict`.

    Falls back to the verdict's own ``overall_code`` when no per-gate
    failure is recorded. Order is preserved so the evidence bundle
    stays deterministic.
    """
    if verdict is None:
        return (), ()
    codes: list[str] = []
    gates: list[str] = []
    seen_codes: dict[str, None] = {}
    seen_gates: dict[str, None] = {}
    for result in verdict.results.values():
        if result.overall_status == ValidationStatus.FAILED:
            if result.overall_code and result.overall_code not in seen_codes:
                codes.append(result.overall_code)
                seen_codes[result.overall_code] = None
        for gate in result.gate_results:
            if gate.status != ValidationStatus.FAILED:
                continue
            if gate.gate not in seen_gates:
                gates.append(gate.gate)
                seen_gates[gate.gate] = None
            if gate.code and gate.code not in seen_codes:
                codes.append(gate.code)
                seen_codes[gate.code] = None
    if not codes and verdict.overall_code:
        codes.append(verdict.overall_code)
    if not gates and codes:
        gates.append("verdict")
    return tuple(codes), tuple(gates)


def _attempt_count(attempts: Iterable[RepairAttempt]) -> int:
    """How many attempt slots the loop actually consumed."""
    n = 0
    for _ in attempts:
        n += 1
    return n


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def derive_code_verdict(
    repair: RepairVerdict,
    *,
    mode: str = MODE_SAFE,
) -> CodeVerdict:
    """Collapse a :class:`RepairVerdict` into a :class:`CodeVerdict`.

    The mode argument is required: the policy layer must declare which
    validation mode the verdict was produced in, because the same
    green validation in ``STAGED`` mode is not safe to apply
    unattended, while the same verdict in ``APPLY`` mode is.
    """
    if mode not in VALIDATION_MODES:
        return CodeVerdict(
            verdict=VERDICT_REJECTED,
            reason=REASON_UNSAFE_MODE,
            mode=mode,
            repair_status=repair.status,
            attempt_count=_attempt_count(repair.attempts),
        )

    if repair.status == STATUS_ACCEPTED:
        codes, gates = _collect_failures(repair.final_verdict)
        return CodeVerdict(
            verdict=VERDICT_ACCEPTED,
            reason=REASON_ACCEPTED,
            mode=mode,
            repair_status=repair.status,
            attempt_count=_attempt_count(repair.attempts),
            failure_codes=codes,
            failure_gates=gates,
            can_apply=mode in (MODE_APPLY, MODE_AUTONOMOUS),
        )

    if repair.status == STATUS_REJECTED_REFUSED:
        return CodeVerdict(
            verdict=VERDICT_NEEDS_REVIEW,
            reason=REASON_CONTRACT_REFUSED,
            mode=mode,
            repair_status=repair.status,
            attempt_count=_attempt_count(repair.attempts),
        )

    if repair.status == STATUS_REJECTED_UNRECOVERABLE:
        return CodeVerdict(
            verdict=VERDICT_NEEDS_REVIEW,
            reason=REASON_GENERATOR_CRASHED,
            mode=mode,
            repair_status=repair.status,
            attempt_count=_attempt_count(repair.attempts),
        )

    if repair.status == STATUS_REJECTED_PARSE_FAILED:
        codes, gates = _collect_failures(repair.final_verdict)
        return CodeVerdict(
            verdict=VERDICT_NEEDS_REPAIR,
            reason=REASON_PATCH_PARSE_FAILED,
            mode=mode,
            repair_status=repair.status,
            attempt_count=_attempt_count(repair.attempts),
            failure_codes=codes,
            failure_gates=gates,
        )

    if repair.status == STATUS_REJECTED_MAX_ATTEMPTS:
        codes, gates = _collect_failures(repair.final_verdict)
        return CodeVerdict(
            verdict=VERDICT_NEEDS_REPAIR,
            reason=REASON_MAX_ATTEMPTS_EXCEEDED,
            mode=mode,
            repair_status=repair.status,
            attempt_count=_attempt_count(repair.attempts),
            failure_codes=codes,
            failure_gates=gates,
        )

    # Unknown repair status -> safe default.
    return CodeVerdict(
        verdict=VERDICT_REJECTED,
        reason=REASON_UNKNOWN_REPAIR_STATUS,
        mode=mode,
        repair_status=repair.status,
        attempt_count=_attempt_count(repair.attempts),
    )


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


def verdict_is_safe_to_apply(verdict: CodeVerdict) -> bool:
    """Return ``True`` iff the verdict + mode pair allows an apply."""
    return verdict.can_apply


def verdict_collect_failure_codes(verdict: CodeVerdict) -> tuple[str, ...]:
    """Stable projection of every failure code in the verdict."""
    return verdict.failure_codes


def verdict_from_pipeline_only(
    pipeline: PipelineVerdict,
    *,
    mode: str = MODE_SAFE,
) -> CodeVerdict:
    """Build a :class:`CodeVerdict` from a :class:`PipelineVerdict` only.

    Useful for tools that bypass the repair loop (e.g. a quick lint
    check on an existing file). The verdict carries no ``repair_status``
    and the attempt count is always ``1``.
    """
    codes, gates = _collect_failures(pipeline)
    accepted = pipeline.accepted
    if accepted:
        return CodeVerdict(
            verdict=VERDICT_ACCEPTED,
            reason=REASON_ACCEPTED,
            mode=mode,
            repair_status="",
            attempt_count=1,
            failure_codes=codes,
            failure_gates=gates,
            can_apply=mode in (MODE_APPLY, MODE_AUTONOMOUS),
        )
    return CodeVerdict(
        verdict=VERDICT_REJECTED,
        reason=REASON_PIPELINE_REJECTED,
        mode=mode,
        repair_status="",
        attempt_count=1,
        failure_codes=codes,
        failure_gates=gates,
    )


def verdict_is_review_only(verdict: CodeVerdict) -> bool:
    """Return ``True`` iff the verdict requires a human look."""
    return verdict.reason in _REVIEW_ONLY_CODES


__all__ = [
    "ALL_VERDICTS",
    "CodeVerdict",
    "REASON_ACCEPTED",
    "REASON_CONTRACT_REFUSED",
    "REASON_GENERATOR_CRASHED",
    "REASON_MAX_ATTEMPTS_EXCEEDED",
    "REASON_PATCH_PARSE_FAILED",
    "REASON_PIPELINE_FAILED",
    "REASON_PIPELINE_REJECTED",
    "REASON_UNKNOWN_REPAIR_STATUS",
    "REASON_UNSAFE_MODE",
    "VERDICT_ACCEPTED",
    "VERDICT_NEEDS_REPAIR",
    "VERDICT_NEEDS_REVIEW",
    "VERDICT_REJECTED",
    "derive_code_verdict",
    "verdict_collect_failure_codes",
    "verdict_from_pipeline_only",
    "verdict_is_review_only",
    "verdict_is_safe_to_apply",
]

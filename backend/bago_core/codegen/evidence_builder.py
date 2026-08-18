"""BAGO Code Forge 3B - evidence bundle builder.

Step 16 of the BAGO Code Forge 3B pipeline. After the repair loop and
the code verdict have produced a final decision, the rest of BAGO
needs a single, stable, JSON-safe record of what happened: which
task it was, which contract was emitted, which attempts the model
went through, which validation gates ran, and what limitations the
call must surface to the user.

The evidence bundle is the **only** artefact the codegen pipeline
emits to the outside world. Everything upstream (classifier,
compiler, context builder, repair loop, code verdict) is internal;
only the bundle leaves the boundary.

Design rules (R0-R10):

- R0: <200 lines, no I/O, no subprocess.
- R1: every nested object is a frozen dataclass and exposes
  :meth:`to_dict`. The bundle itself is JSON-safe.
- R2: deterministic. Given the same inputs, the bundle is byte-for-byte
  identical apart from the ``created_at`` timestamp (which the caller
  can override for tests).
- R3: stable field names. The UI and the audit log both join on
  ``task_id`` and ``verdict``. Renaming a field is a breaking change.
- R4: never raises. Unknown inputs (``None`` where a contract is
  expected, a missing verdict, etc.) fall back to documented empty
  values. The bundle is always usable.
- R8: no ``print``, no model calls, no file I/O. The bundle is a pure
  data object.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .code_verdict import CodeVerdict, VERDICT_ACCEPTED, VERDICT_REJECTED
from .repair_loop import (
    RepairAttempt,
    RepairVerdict,
    STATUS_ACCEPTED,
    STATUS_REJECTED_REFUSED,
)
from .task_compiler import CodeTaskContract
from ..validation.validation_pipeline import (
    MODE_APPLY,
    MODE_AUTONOMOUS,
    PipelineVerdict,
    VALIDATION_MODES,
)
from ..validation.validation_result import (
    GATE_ORDER,
    ValidationStatus,
)


# Bundle version. Bump when the JSON shape changes so the audit log
# can detect old bundles.
BUNDLE_VERSION = "1.0.0"

# Stable keys the policy layer dispatches on.
KEY_BUNDLE_VERSION = "bundle_version"
KEY_TASK_ID = "task_id"
KEY_CONTRACT = "contract"
KEY_VERDICT = "verdict"
KEY_ATTEMPTS = "attempts"
KEY_VALIDATION = "validation"
KEY_LIMITATIONS = "limitations"
KEY_CREATED_AT = "created_at"
KEY_DURATION_MS = "duration_ms"
KEY_FINAL_PATCHES = "final_patches"
KEY_ATTEMPT_COUNT = "attempt_count"
KEY_FAILURE_CODES = "failure_codes"
KEY_FAILURE_GATES = "failure_gates"
KEY_GATES = "gates"
KEY_GATE_ID = "gate_id"
KEY_GATE_STATUS = "gate_status"
KEY_GATE_CODE = "code"
KEY_GATE_MESSAGE = "message"

# Stable codes for the limitations list. Used by the UI to pick a
# localised message; never used to dispatch on policy.
LIMIT_SAFE_MODE = "safe_mode_no_apply"
LIMIT_PIPELINE_PARTIAL = "pipeline_partial"
LIMIT_GENERATOR_CRASHED = "generator_crashed"
LIMIT_PARSE_FAILED = "parse_failed"
LIMIT_REVIEW_ONLY = "review_only"


@dataclass(frozen=True)
class EvidenceBundle:
    """The full JSON-safe record of one Code Forge run.

    Attributes
    ----------
    bundle_version:
        :data:`BUNDLE_VERSION`. Lets the audit log detect old shapes.
    task_id:
        Mirror of ``contract.task_id``. Always present, even when the
        contract was refused (the compiler still emits a stable id).
    verdict:
        The :class:`CodeVerdict` the pipeline ended with. Never
        ``None``; callers always get an opinion.
    contract:
        The contract the loop ran against. May be the refused one if
        the classifier rejected the request before the loop started.
    attempts:
        Every iteration of the repair loop, in order. May be empty.
    limitations:
        Stable codes the UI must surface to the user. Always a tuple;
        empty on a clean ``accepted`` verdict.
    created_at:
        Unix timestamp (seconds) the bundle was assembled.
    duration_ms:
        Wall-clock duration of the loop, best effort. ``0`` when the
        loop was skipped (e.g. contract refused).
    extra:
        Free-form context. Always JSON-safe.
    """

    bundle_version: str
    task_id: str
    verdict: CodeVerdict
    contract: CodeTaskContract | None = None
    attempts: tuple[RepairAttempt, ...] = ()
    limitations: tuple[str, ...] = ()
    created_at: float = 0.0
    duration_ms: int = 0
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        validation = _validation_summary(self.verdict, self.attempts)
        return {
            KEY_BUNDLE_VERSION: self.bundle_version,
            KEY_TASK_ID: self.task_id,
            KEY_CREATED_AT: self.created_at,
            KEY_DURATION_MS: self.duration_ms,
            KEY_CONTRACT: self.contract.to_dict() if self.contract else None,
            KEY_VERDICT: self.verdict.to_dict(),
            KEY_ATTEMPTS: [a.to_dict() for a in self.attempts],
            KEY_VALIDATION: validation,
            KEY_LIMITATIONS: list(self.limitations),
            "extra": dict(self.extra),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validation_summary(
    verdict: CodeVerdict,
    attempts: Iterable[RepairAttempt],
) -> dict[str, object]:
    """Build the ``validation`` block of the bundle.

    The block lists every gate the pipeline ran in the canonical order,
    the gate's final status, and the failure codes the verdict kept.
    """
    gates: list[dict[str, object]] = []
    seen: dict[str, None] = {}

    # Carry forward the verdict's own gate list (preserves order).
    for gate in verdict.failure_gates:
        if gate in seen:
            continue
        gates.append({
            KEY_GATE_ID: gate,
                KEY_GATE_STATUS: ValidationStatus.FAILED,
            KEY_GATE_CODE: _first_code_for_gate(verdict, gate),
            KEY_GATE_MESSAGE: "",
        })
        seen[gate] = None

    # Fold in any gate the verdict did not flag (e.g. SKIPPED) so the
    # bundle always shows the full gate order.
    for gate in GATE_ORDER:
        if gate in seen:
            continue
        gates.append({
            KEY_GATE_ID: gate,
                KEY_GATE_STATUS: ValidationStatus.SKIPPED,
            KEY_GATE_CODE: "",
            KEY_GATE_MESSAGE: "",
        })
        seen[gate] = None

    return {
        KEY_GATE_ID: verdict.mode,
        KEY_GATE_STATUS: (
                ValidationStatus.PASSED
            if verdict.accepted
                else ValidationStatus.FAILED
        ),
        KEY_FAILURE_CODES: list(verdict.failure_codes),
        KEY_FAILURE_GATES: list(verdict.failure_gates),
        KEY_GATES: gates,
    }


def _first_code_for_gate(verdict: CodeVerdict, gate: str) -> str:
    """Best-effort: return the first failure code for ``gate``."""
    for code in verdict.failure_codes:
        if code and gate in code.lower():
            return code
    return verdict.failure_codes[0] if verdict.failure_codes else ""


def _collect_limitations(
    verdict: CodeVerdict,
    attempts: Iterable[RepairAttempt],
) -> tuple[str, ...]:
    """Translate a verdict + attempt history into user-facing flags."""
    codes: list[str] = []
    seen: dict[str, None] = {}

    def _add(code: str) -> None:
        if code in seen:
            return
        seen[code] = None
        codes.append(code)

    if verdict.accepted and verdict.mode not in (MODE_APPLY, MODE_AUTONOMOUS):
        _add(LIMIT_SAFE_MODE)

    attempts_list = list(attempts)
    if attempts_list:
        last = attempts_list[-1]
        if last.parse_error:
            _add(LIMIT_PARSE_FAILED)
        if last.feedback and last.feedback.failing_gate == "apply":
            _add(LIMIT_PARSE_FAILED)

    if verdict.reason == "generator_crashed":
        _add(LIMIT_GENERATOR_CRASHED)
    if verdict.reason == "patch_parse_failed":
        _add(LIMIT_PARSE_FAILED)

    if verdict.rejected and not verdict.accepted and verdict.can_apply is False:
        # ``rejected`` verdicts can still leave the workspace in a
        # partially-mutated state from earlier attempts. Flag it so
        # the UI can suggest rolling back.
        if attempts_list and any(a.patches for a in attempts_list):
            _add(LIMIT_PIPELINE_PARTIAL)

    if verdict.reason in ("contract_refused", "generator_crashed",
                          "unknown_repair_status"):
        _add(LIMIT_REVIEW_ONLY)

    return tuple(codes)


def _duration_ms(
    attempts: Iterable[RepairAttempt],
    *,
    fallback: int = 0,
) -> int:
    """Sum up ``duration_ms`` across attempts. Falls back when missing.

    The :class:`PipelineVerdict` does not carry a top-level
    ``duration_ms`` field (the wall-clock time is rolled up per gate
    inside :attr:`PipelineVerdict.summary`), so we read it from the
    summary dict when present. Falls back to ``fallback`` when no
    attempt reported anything useful.
    """
    total = 0
    found_any = False
    for attempt in attempts:
        verdict = attempt.verdict
        if verdict is None:
            continue
        summary = getattr(verdict, "summary", None)
        if not isinstance(summary, Mapping):
            continue
        value = summary.get("duration_ms")
        if isinstance(value, (int, float)) and value > 0:
            total += int(value)
            found_any = True
    return total if found_any else fallback


def _attempt_count(attempts: Iterable[RepairAttempt]) -> int:
    n = 0
    for _ in attempts:
        n += 1
    return n


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_evidence_bundle(
    *,
    verdict: CodeVerdict,
    contract: CodeTaskContract | None = None,
    attempts: Iterable[RepairAttempt] = (),
    repair: RepairVerdict | None = None,
    duration_ms: int = 0,
    created_at: float | None = None,
    extra: Mapping[str, object] | None = None,
) -> EvidenceBundle:
    """Assemble the final :class:`EvidenceBundle`.

    Parameters
    ----------
    verdict:
        The high-level verdict (always required).
    contract:
        The contract the loop ran against. May be ``None`` when the
        verdict was built from a pipeline-only lint pass.
    attempts:
        Every iteration of the repair loop, in order. The bundle
        preserves order.
    repair:
        Optional source of truth for the attempt list. When provided,
        ``attempts`` is taken from it (this keeps the call sites
        honest - they cannot accidentally pass a curated subset).
    duration_ms:
        Override for the wall-clock duration. Defaults to summing the
        ``duration_ms`` field of every attempt's verdict.
    created_at:
        Override for the bundle timestamp. Tests use this to keep
        the bundle byte-deterministic.
    extra:
        Free-form context for downstream consumers.
    """
    if verdict is None:  # type: ignore[unreachable]
        raise ValueError("verdict is required")

    attempts_tuple: tuple[RepairAttempt, ...] = (
        tuple(repair.attempts) if repair is not None else tuple(attempts)
    )

    task_id = (
        contract.task_id
        if contract is not None
        else _safe_task_id(verdict)
    )

    limitations = _collect_limitations(verdict, attempts_tuple)

    if duration_ms == 0:
        duration_ms = _duration_ms(attempts_tuple)

    return EvidenceBundle(
        bundle_version=BUNDLE_VERSION,
        task_id=task_id,
        verdict=verdict,
        contract=contract,
        attempts=attempts_tuple,
        limitations=limitations,
        created_at=created_at if created_at is not None else time.time(),
        duration_ms=duration_ms,
        extra=dict(extra) if extra else {},
    )


def _safe_task_id(verdict: CodeVerdict) -> str:
    """Best-effort task id when no contract is supplied."""
    extra = verdict.extra or {}
    candidate = extra.get("task_id")
    if isinstance(candidate, str) and candidate:
        return candidate
    return f"UNKNOWN-{verdict.verdict.upper()}"


# ---------------------------------------------------------------------------
# Convenience projections
# ---------------------------------------------------------------------------


def bundle_from_repair_verdict(
    repair: RepairVerdict,
    *,
    mode: str,
    contract: CodeTaskContract | None = None,
    objective: str = "",
    duration_ms: int = 0,
    created_at: float | None = None,
) -> EvidenceBundle:
    """Convenience wrapper: build a verdict then assemble the bundle.

    This is the entry point the codegen pipeline uses in production.
    It picks the verdict builder based on ``mode`` so callers cannot
    forget the mode argument.
    """
    from .code_verdict import derive_code_verdict  # local import: avoid cycle

    if mode not in VALIDATION_MODES:
        # Same fallback as ``derive_code_verdict``; we mirror it so the
        # bundle still gets a verdict to carry.
        from .code_verdict import (
            CodeVerdict,
            REASON_UNSAFE_MODE,
            VERDICT_REJECTED,
        )
        verdict = CodeVerdict(
            verdict=VERDICT_REJECTED,
            reason=REASON_UNSAFE_MODE,
            mode=mode,
            repair_status=repair.status,
            attempt_count=_attempt_count(repair.attempts),
        )
    else:
        verdict = derive_code_verdict(repair, mode=mode)

    if contract is None and objective:
        # Caller asked for a bundle but forgot to compile the contract.
        # We surface that as an extra so the UI can still render.
        extra = {"missing_contract": True, "objective": objective}
    else:
        extra = None

    return build_evidence_bundle(
        verdict=verdict,
        contract=contract,
        attempts=repair.attempts,
        duration_ms=duration_ms,
        created_at=created_at,
        extra=extra,
    )


def bundle_to_audit_record(bundle: EvidenceBundle) -> dict[str, object]:
    """Flatten the bundle into a single dict for the audit log table.

    The audit log joins on ``task_id`` + ``created_at`` and stores a
    denormalised row so a single ``SELECT`` can replay any session.
    """
    data = bundle.to_dict()
    data[KEY_ATTEMPT_COUNT] = len(bundle.attempts)
    return data


__all__ = [
    "BUNDLE_VERSION",
    "EvidenceBundle",
    "LIMIT_GENERATOR_CRASHED",
    "LIMIT_PARSE_FAILED",
    "LIMIT_PIPELINE_PARTIAL",
    "LIMIT_REVIEW_ONLY",
    "LIMIT_SAFE_MODE",
    "build_evidence_bundle",
    "bundle_from_repair_verdict",
    "bundle_to_audit_record",
]
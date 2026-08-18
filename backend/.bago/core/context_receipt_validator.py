"""context_receipt_validator.py — Independent receipt validation for BAGO.

This module is intentionally separate from SessionManager. It only
consumes a ContextReceipt and a small expected-state snapshot, then
returns a reproducible validation report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ASSURANCE_STATES = (
    "unverified",
    "partially_tested",
    "verified_isolation",
    "verified_integration",
    "certified",
)


@dataclass(frozen=True)
class ReceiptValidationReport:
    ok: bool
    assurance_state: str
    checks: tuple[dict[str, Any], ...] = ()
    failures: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "assurance_state": self.assurance_state,
            "checks": list(self.checks),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "evidence": dict(self.evidence),
        }


class ContextReceiptValidator:
    """Independent validator for ContextReceipt values."""

    def validate(
        self,
        receipt: Any,
        *,
        expected_workspace: str = "",
        expected_workspace_state_root: str = "",
        expected_provider: str = "",
        expected_model: str = "",
        expected_context_revision: str = "",
        expected_session_id: str = "",
        expected_session_summary: dict[str, Any] | None = None,
    ) -> ReceiptValidationReport:
        checks: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        warnings: list[str] = []

        def _check(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail})
            if not ok:
                failures.append({"name": name, "detail": detail})

        if receipt is None:
            _check("receipt_present", False, "receipt missing")
            return ReceiptValidationReport(
                ok=False,
                assurance_state="unverified",
                checks=tuple(checks),
                failures=tuple(failures),
                warnings=tuple(warnings),
                evidence={"expected_workspace": expected_workspace},
            )

        _check("receipt_present", True, "receipt available")
        _check("workspace_match", getattr(receipt, "workspace_used", "") == expected_workspace, "workspace mismatch")
        if not expected_workspace_state_root and expected_workspace:
            expected_workspace_state_root = str(Path(expected_workspace) / ".gabo")
        _check("workspace_state_root_match", getattr(receipt, "workspace_state_root", "") == expected_workspace_state_root, "workspace_state_root mismatch")
        _check("provider_match", getattr(receipt, "provider_used", "") == expected_provider, "provider mismatch")
        _check("model_match", getattr(receipt, "model_used", "") == expected_model, "model mismatch")
        _check("revision_match", getattr(receipt, "context_revision", "") == expected_context_revision, "context_revision mismatch")
        _check("tokens_sent", int(getattr(receipt, "tokens_sent", 0) or 0) >= 0, "tokens_sent must be non-negative")
        _check("tokens_reserved", int(getattr(receipt, "tokens_reserved", 0) or 0) >= 0, "tokens_reserved must be non-negative")
        _check("files_represented", isinstance(getattr(receipt, "files_represented", []), list), "files_represented must be a list")
        _check("fragments_recovered", isinstance(getattr(receipt, "fragments_recovered", []), list), "fragments_recovered must be a list")
        _check("session_id_summary", isinstance(getattr(receipt, "session_summary_loaded", {}), dict), "session_summary_loaded must be a dict")

        summary = getattr(receipt, "session_summary_loaded", {}) or {}
        if expected_session_summary:
            for key, value in expected_session_summary.items():
                _check(
                    f"summary_{key}",
                    summary.get(key) == value,
                    f"session_summary.{key} mismatch",
                )
        if expected_session_id:
            _check("summary_session_id", summary.get("session_id", "") == expected_session_id, "session_id mismatch")

        files_represented = list(getattr(receipt, "files_represented", []) or [])
        fragments_recovered = list(getattr(receipt, "fragments_recovered", []) or [])
        if not files_represented:
            warnings.append("no_files_represented")
        if not fragments_recovered:
            warnings.append("no_fragments_recovered")

        ok = not failures
        if not receipt:
            assurance_state = "unverified"
        elif ok:
            assurance_state = "certified"
        elif failures and (files_represented or fragments_recovered):
            assurance_state = "partially_tested"
        else:
            assurance_state = "verified_isolation"

        evidence = {
            "workspace_used": getattr(receipt, "workspace_used", ""),
            "workspace_state_root": getattr(receipt, "workspace_state_root", ""),
            "provider_used": getattr(receipt, "provider_used", ""),
            "model_used": getattr(receipt, "model_used", ""),
            "context_revision": getattr(receipt, "context_revision", ""),
            "files_represented": files_represented,
            "fragments_recovered": fragments_recovered,
            "session_summary_loaded": summary,
        }
        return ReceiptValidationReport(
            ok=ok,
            assurance_state=assurance_state,
            checks=tuple(checks),
            failures=tuple(failures),
            warnings=tuple(warnings),
            evidence=evidence,
        )

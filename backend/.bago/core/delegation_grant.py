"""Persistent, fail-closed delegation grants for scheduled execution.

A schedule is not authority. A DelegationGrant is authority derived from an
operation-bound user authorization for the canonical E6 effect
`schedule.delegate`. Every scheduled run must mint a fresh child Permit whose
authority is a material subset of the grant.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from effect_registry import REGISTRY, EffectRegistryError
from execution_request import ExecutionRequest, stable_digest


DELEGATION_GRANT_CONTRACT = "bago.delegation-grant/v1"
_LOCK = threading.RLock()


class DelegationError(ValueError):
    def __init__(self, message: str, *, code: str = "delegation_invalid") -> None:
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise DelegationError("expires_at is required", code="delegation_expiry_required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DelegationError("Invalid delegation timestamp", code="delegation_invalid_timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_schedule_descriptor(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a privacy-safe, exact authority descriptor for schedule semantics."""
    schedule_type = str(raw.get("schedule_type") or "interval").strip()
    target = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    return {
        "id": str(raw.get("id") or "").strip(),
        "target_type": str(raw.get("target_type") or "").strip(),
        "target_digest": stable_digest(target),
        "schedule_type": schedule_type,
        "interval_s": int(raw.get("interval_s") or 0) if schedule_type == "interval" else None,
        "cron_expr": str(raw.get("cron_expr") or "").strip() if schedule_type == "cron" else "",
        "timezone": str(raw.get("timezone") or "UTC").strip(),
        "overlap_policy": str(raw.get("overlap_policy") or "skip").strip(),
        "misfire_policy": str(raw.get("misfire_policy") or "run_once").strip(),
    }


def schedule_descriptor_digest(raw: dict[str, Any]) -> str:
    return stable_digest(canonical_schedule_descriptor(raw))


class DelegationGrantRegistry:
    def __init__(self, state_dir: Path | str) -> None:
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / "delegation_grants.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "contract": DELEGATION_GRANT_CONTRACT,
                "schema_version": 1,
                "grants": {},
            }
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DelegationError(
                f"Cannot read delegation grant registry: {exc}",
                code="delegation_registry_invalid",
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("grants"), dict):
            raise DelegationError("Delegation grant registry is invalid", code="delegation_registry_invalid")
        payload["contract"] = DELEGATION_GRANT_CONTRACT
        payload["schema_version"] = 1
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        from bago_core.atomic_json import write_json_atomic

        payload["contract"] = DELEGATION_GRANT_CONTRACT
        payload["schema_version"] = 1
        payload["updated_at"] = _iso(_now())
        write_json_atomic(self.path, payload)

    def list(self) -> list[dict[str, Any]]:
        with _LOCK:
            return [dict(item) for item in self._read()["grants"].values() if isinstance(item, dict)]

    def get(self, grant_id: str) -> dict[str, Any]:
        with _LOCK:
            record = self._read()["grants"].get(str(grant_id or ""))
            if not isinstance(record, dict):
                raise DelegationError("DelegationGrant not found", code="delegation_not_found")
            return dict(record)

    def issue_from_authorized_request(
        self,
        request: ExecutionRequest,
        authorization: dict[str, Any],
    ) -> dict[str, Any]:
        """Materialize a grant only after the E6 request Permit was consumed."""
        if request.effect_id != "schedule.delegate":
            raise DelegationError(
                "DelegationGrant can only be issued by schedule.delegate",
                code="delegation_parent_effect_invalid",
            )
        if str(authorization.get("state") or "") != "consumed":
            raise DelegationError(
                "Delegation authority requires a consumed parent Permit",
                code="delegation_parent_permit_not_consumed",
            )
        if str(authorization.get("effect_id") or "") != request.effect_id:
            raise DelegationError("Parent effect mismatch", code="delegation_parent_effect_mismatch")
        if str(authorization.get("operation_fingerprint") or "") != request.fingerprint:
            raise DelegationError(
                "Parent authorization does not bind the delegation request",
                code="delegation_parent_fingerprint_mismatch",
            )

        proof = authorization.get("proof")
        decision = authorization.get("decision")
        if not isinstance(proof, dict) or not isinstance(decision, dict):
            raise DelegationError("Delegation provenance is missing", code="delegation_provenance_missing")
        provenance = proof.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("kind") != "direct_user_interaction":
            raise DelegationError(
                "Delegation must originate in direct user authorization",
                code="delegation_user_origin_unverified",
            )
        if str(decision.get("result") or "") != "allow":
            raise DelegationError("Parent decision is not ALLOW", code="delegation_parent_not_allowed")
        if str(proof.get("operation_fingerprint") or "") != request.fingerprint:
            raise DelegationError("Proof fingerprint mismatch", code="delegation_proof_mismatch")

        target = request.target
        if not isinstance(target, dict):
            raise DelegationError("Delegation request shape is invalid", code="delegation_request_invalid")

        schedule_id = str(target.get("schedule_id") or "").strip()
        schedule_digest = str(target.get("schedule_digest") or "").strip()
        schedule_descriptor = target.get("schedule")
        envelope = target.get("delegation")
        if not schedule_id or not schedule_digest:
            raise DelegationError("Delegation must bind a schedule", code="delegation_schedule_binding_required")
        if not isinstance(schedule_descriptor, dict):
            raise DelegationError(
                "Delegation request must expose the bounded schedule descriptor",
                code="delegation_visible_schedule_required",
            )
        if stable_digest(schedule_descriptor) != schedule_digest:
            raise DelegationError(
                "Visible schedule descriptor does not match schedule_digest",
                code="delegation_visible_schedule_mismatch",
            )
        if str(schedule_descriptor.get("id") or "") != schedule_id:
            raise DelegationError(
                "Visible schedule descriptor is bound to another schedule",
                code="delegation_schedule_mismatch",
            )
        if not isinstance(envelope, dict):
            raise DelegationError(
                "Delegation authority envelope must be human-visible in request.target",
                code="delegation_visible_envelope_required",
            )

        allowed_effects = sorted({str(item).strip() for item in envelope.get("allowed_effects", []) if str(item).strip()})
        if not allowed_effects:
            raise DelegationError("allowed_effects is required", code="delegation_effects_required")
        for effect_id in allowed_effects:
            try:
                effect = REGISTRY.get(effect_id)
            except EffectRegistryError as exc:
                raise DelegationError(str(exc), code="delegation_effect_unknown") from exc
            if not effect.delegable:
                raise DelegationError(
                    f"Effect is not delegable: {effect_id}",
                    code="delegation_effect_not_delegable",
                )

        child_actor_kind = str(envelope.get("child_actor_kind") or "scheduler").strip().lower()
        child_source_surface = str(envelope.get("child_source_surface") or "scheduler").strip()
        if child_actor_kind != "scheduler" or child_source_surface != "scheduler":
            raise DelegationError(
                "Scheduler grants must bind the scheduler actor and source surface",
                code="delegation_runtime_binding_invalid",
            )

        target_digest = str(envelope.get("target_digest") or "").strip()
        visible_child_target = envelope.get("child_target")
        arguments_digest = str(envelope.get("arguments_digest") or "").strip()
        scope = str(envelope.get("scope") or "").strip()
        policy_version = str(envelope.get("policy_version") or "").strip()
        if not target_digest or not arguments_digest or not scope or not policy_version:
            raise DelegationError(
                "Delegation child constraints are incomplete",
                code="delegation_constraints_incomplete",
            )
        if not isinstance(visible_child_target, dict):
            raise DelegationError(
                "Delegation request must expose the non-sensitive child target",
                code="delegation_visible_target_required",
            )
        if stable_digest(visible_child_target) != target_digest:
            raise DelegationError(
                "Visible child target does not match target_digest",
                code="delegation_visible_target_mismatch",
            )
        if policy_version != request.policy_version or policy_version != REGISTRY.digest:
            raise DelegationError(
                "Delegation policy version is stale",
                code="delegation_policy_stale",
            )

        expires_at = _parse_iso(envelope.get("expires_at"))
        now = _now()
        if expires_at <= now:
            raise DelegationError("Delegation is already expired", code="delegation_expired")
        try:
            max_runs = int(envelope.get("max_runs"))
        except (TypeError, ValueError) as exc:
            raise DelegationError("max_runs must be an integer", code="delegation_max_runs_invalid") from exc
        if max_runs < 1:
            raise DelegationError("max_runs must be greater than zero", code="delegation_max_runs_invalid")

        grant_id = str(envelope.get("grant_id") or f"delegation-{uuid.uuid4().hex}").strip()
        if not grant_id or "/" in grant_id or "\\" in grant_id:
            raise DelegationError("Invalid DelegationGrant id", code="delegation_id_invalid")

        static_payload = {
            "contract": DELEGATION_GRANT_CONTRACT,
            "grant_id": grant_id,
            "principal_id": request.principal_id,
            "schedule_id": schedule_id,
            "schedule_digest": schedule_digest,
            "allowed_effects": allowed_effects,
            "target_digest": target_digest,
            "arguments_digest": arguments_digest,
            "scope": scope,
            "policy_version": policy_version,
            "child_actor_kind": child_actor_kind,
            "child_source_surface": child_source_surface,
            "delegation_depth": 1,
            "can_redelegate": False,
            "expires_at": _iso(expires_at),
            "max_runs": max_runs,
        }
        record = {
            **static_payload,
            "grant_fingerprint": stable_digest(static_payload),
            "state": "active",
            "issued_at": _iso(now),
            "run_count": 0,
            "last_claimed_at": "",
            "last_claim_id": "",
            "revoked_at": "",
            "revocation_reason": "",
            "origin": {
                "parent_request_id": request.request_id,
                "parent_operation_fingerprint": request.fingerprint,
                "parent_session_id": request.session_id,
                "parent_source_surface": request.source_surface,
                "parent_permit_id": str(authorization.get("permit_id") or ""),
                "proof_id": str(authorization.get("proof_id") or proof.get("proof_id") or ""),
                "decision_id": str(authorization.get("decision_id") or decision.get("decision_id") or ""),
                "interaction_id": str(proof.get("interaction_id") or ""),
                "authenticated_session_id": str(proof.get("authenticated_session_id") or ""),
                "proof_kind": str(provenance.get("kind") or ""),
                "proof_channel": str(provenance.get("channel") or ""),
                "proof_assurance": "interactive_origin",
            },
        }

        with _LOCK:
            payload = self._read()
            if grant_id in payload["grants"]:
                raise DelegationError("DelegationGrant already exists", code="delegation_conflict")
            payload["grants"][grant_id] = record
            self._write(payload)
        return dict(record)

    def _validate_active_locked(
        self,
        record: dict[str, Any],
        *,
        now: datetime,
    ) -> None:
        state = str(record.get("state") or "")
        if state == "revoked":
            raise DelegationError("DelegationGrant is revoked", code="delegation_revoked")
        if state == "expired":
            raise DelegationError("DelegationGrant is expired", code="delegation_expired")
        if state == "exhausted":
            raise DelegationError("DelegationGrant is exhausted", code="delegation_exhausted")
        expires_at = _parse_iso(record.get("expires_at"))
        if expires_at <= now:
            record["state"] = "expired"
            raise DelegationError("DelegationGrant is expired", code="delegation_expired")
        if int(record.get("run_count", 0) or 0) >= int(record.get("max_runs", 0) or 0):
            record["state"] = "exhausted"
            raise DelegationError("DelegationGrant is exhausted", code="delegation_exhausted")
        if state != "active":
            raise DelegationError("DelegationGrant is not active", code="delegation_not_active")

    def _validate_child_locked(
        self,
        record: dict[str, Any],
        request: ExecutionRequest,
        *,
        schedule_id: str,
        schedule_digest: str,
        now: datetime,
    ) -> None:
        self._validate_active_locked(record, now=now)
        grant_id = str(record.get("grant_id") or "")
        if request.delegation_id != grant_id:
            raise DelegationError("Child request is bound to another grant", code="delegation_id_mismatch")
        if request.principal_id != str(record.get("principal_id") or ""):
            raise DelegationError("Child principal exceeds grant", code="delegation_principal_mismatch")
        if request.actor_kind != str(record.get("child_actor_kind") or ""):
            raise DelegationError("Child actor exceeds grant", code="delegation_actor_mismatch")
        if request.source_surface != str(record.get("child_source_surface") or ""):
            raise DelegationError("Child source surface exceeds grant", code="delegation_surface_mismatch")
        if str(schedule_id or "") != str(record.get("schedule_id") or ""):
            raise DelegationError("Child schedule differs from grant", code="delegation_schedule_mismatch")
        if str(schedule_digest or "") != str(record.get("schedule_digest") or ""):
            raise DelegationError("Schedule changed after delegation", code="delegation_schedule_digest_mismatch")
        expected_parent = f"schedule:{record.get('schedule_id')}"
        if request.parent_execution_id != expected_parent:
            raise DelegationError("Child lineage is not bound to schedule", code="delegation_parent_lineage_mismatch")
        if request.effect_id not in set(record.get("allowed_effects") or []):
            raise DelegationError("Child effect exceeds grant", code="delegation_effect_exceeds_grant")
        try:
            effect = REGISTRY.get(request.effect_id)
        except EffectRegistryError as exc:
            raise DelegationError(str(exc), code="delegation_effect_unknown") from exc
        if not effect.delegable:
            raise DelegationError("Child effect is not delegable", code="delegation_effect_not_delegable")
        if request.target_digest != str(record.get("target_digest") or ""):
            raise DelegationError("Child target exceeds grant", code="delegation_target_exceeds_grant")
        if request.arguments_digest != str(record.get("arguments_digest") or ""):
            raise DelegationError("Child arguments exceed grant", code="delegation_arguments_exceed_grant")
        if request.scope != str(record.get("scope") or ""):
            raise DelegationError("Child scope exceeds grant", code="delegation_scope_exceeds_grant")
        grant_policy = str(record.get("policy_version") or "")
        if request.policy_version != grant_policy or grant_policy != REGISTRY.digest:
            raise DelegationError("Delegation policy is stale", code="delegation_policy_stale")

    def validate_child(
        self,
        grant_id: str,
        request: ExecutionRequest,
        *,
        schedule_id: str,
        schedule_digest: str,
    ) -> dict[str, Any]:
        with _LOCK:
            payload = self._read()
            record = payload["grants"].get(str(grant_id or ""))
            if not isinstance(record, dict):
                raise DelegationError("DelegationGrant not found", code="delegation_not_found")
            try:
                self._validate_child_locked(
                    record,
                    request,
                    schedule_id=schedule_id,
                    schedule_digest=schedule_digest,
                    now=_now(),
                )
            except DelegationError:
                if record.get("state") in {"expired", "exhausted"}:
                    self._write(payload)
                raise
            return dict(record)

    def claim_child(
        self,
        grant_id: str,
        request: ExecutionRequest,
        *,
        schedule_id: str,
        schedule_digest: str,
    ) -> dict[str, Any]:
        """Atomically spend one grant run before a delegated Permit is exposed."""
        with _LOCK:
            payload = self._read()
            record = payload["grants"].get(str(grant_id or ""))
            if not isinstance(record, dict):
                raise DelegationError("DelegationGrant not found", code="delegation_not_found")
            now = _now()
            try:
                self._validate_child_locked(
                    record,
                    request,
                    schedule_id=schedule_id,
                    schedule_digest=schedule_digest,
                    now=now,
                )
            except DelegationError:
                if record.get("state") in {"expired", "exhausted"}:
                    self._write(payload)
                raise
            claim_id = f"delegation-claim-{uuid.uuid4().hex}"
            run_count = int(record.get("run_count", 0) or 0) + 1
            record["run_count"] = run_count
            record["last_claimed_at"] = _iso(now)
            record["last_claim_id"] = claim_id
            if run_count >= int(record.get("max_runs", 0) or 0):
                record["state"] = "exhausted"
            self._write(payload)
            return {
                "claim_id": claim_id,
                "claimed_run": run_count,
                "grant_id": str(record.get("grant_id") or ""),
                "grant_state_after_claim": str(record.get("state") or ""),
                "principal_id": str(record.get("principal_id") or ""),
                "proof_id": str((record.get("origin") or {}).get("proof_id") or ""),
                "decision_id": str((record.get("origin") or {}).get("decision_id") or ""),
                "expires_at": str(record.get("expires_at") or ""),
                "operation_fingerprint": request.fingerprint,
                "effect_id": request.effect_id,
                "schedule_id": str(record.get("schedule_id") or ""),
            }

    def revoke(self, grant_id: str, *, reason: str = "") -> dict[str, Any]:
        with _LOCK:
            payload = self._read()
            record = payload["grants"].get(str(grant_id or ""))
            if not isinstance(record, dict):
                raise DelegationError("DelegationGrant not found", code="delegation_not_found")
            if record.get("state") == "revoked":
                return dict(record)
            record["state"] = "revoked"
            record["revoked_at"] = _iso(_now())
            record["revocation_reason"] = str(reason or "")[:500]
            self._write(payload)
            return dict(record)


__all__ = [
    "DELEGATION_GRANT_CONTRACT",
    "DelegationError",
    "DelegationGrantRegistry",
    "canonical_schedule_descriptor",
    "schedule_descriptor_digest",
]

"""User authorization provenance boundary for governed BAGO execution.

Authority is bound to a generic ExecutionRequest fingerprint. This module does
not execute material effects; ExecutionGateway owns dispatch.
"""

from __future__ import annotations

import base64
import hashlib
from contextlib import contextmanager
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import state_root
from effect_registry import REGISTRY
from execution_request import ExecutionRequest, build_execution_request


AUTHORIZATION_CONTRACT_VERSION = "bago.authorization/v2"
CHALLENGE_TTL_SECONDS = 180
PERMIT_TTL_SECONDS = 120
INTERACTIVE_CHANNELS = frozenset({"ui-react", "desktop"})
_LOCK = threading.RLock()


class AuthorizationError(ValueError):
    """Fail-closed authorization error with a stable machine code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class UserAuthorizationProof:
    proof_id: str
    principal_id: str
    authenticated_session_id: str
    interaction_id: str
    operation_fingerprint: str
    effect_id: str
    user_decision: str
    issued_at: str
    expires_at: str
    provenance: dict[str, str]


@dataclass(frozen=True)
class AuthorizationDecision:
    decision_id: str
    result: str
    proof_id: str
    operation_fingerprint: str
    effect_id: str
    reason: str
    decided_at: str


@dataclass(frozen=True)
class Permit:
    permit_id: str
    token: str
    decision_id: str
    proof_id: str
    operation_fingerprint: str
    request_id: str
    effect_id: str
    session_id: str
    issued_at: str
    expires_at: str


# Transitional compatibility only. New code must use ExecutionRequest directly.
AuthorizationOperation = ExecutionRequest


def build_operation(
    *,
    capability_id: str,
    inputs: Any,
    permissions: Any,
    session_id: str,
) -> ExecutionRequest:
    """Legacy compatibility shim for pre-v2 callers."""
    clean_permissions = sorted({str(item) for item in (permissions or []) if str(item)})
    return build_execution_request(
        effect_id="capability.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=session_id,
        source_surface="legacy.authorization-operation",
        target={
            "package_id": str(capability_id or "").strip(),
            "declared_permissions": clean_permissions,
        },
        arguments=inputs if inputs is not None else {},
        scope="workspace",
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise AuthorizationError(
            "Timestamp de autorización inválido",
            code="authorization_invalid_timestamp",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ledger_path() -> Path:
    return state_root() / "authorization" / "ledger.json"


def authorization_ledger_path() -> Path:
    """Return the canonical authority ledger path for delegated consumers."""

    return _ledger_path()


def _empty_ledger() -> dict[str, Any]:
    return {
        "contract_version": AUTHORIZATION_CONTRACT_VERSION,
        "challenges": {},
        "permits": {},
    }


def _read_ledger() -> dict[str, Any]:
    path = _ledger_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return _empty_ledger()
    if not isinstance(data, dict):
        return _empty_ledger()
    data["contract_version"] = AUTHORIZATION_CONTRACT_VERSION
    data.setdefault("challenges", {})
    data.setdefault("permits", {})
    return data


def _write_ledger(data: dict[str, Any]) -> None:
    path = _ledger_path()
    # This ledger is authority-internal state: the AuthorizationBoundary owns
    # its materialization and is intentionally not a runtime effect adapter.
    # Keep the sink explicit so the inventory can distinguish authority-owned
    # persistence from an ExecutionGateway bypass.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _new_permit_token() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")


class AuthorizationBoundary:
    """Owns challenge, user-origin verification, decision and Permit issuance."""

    def authorize_server_policy(self, request: ExecutionRequest) -> dict[str, Any]:
        """Authorize a registered policy effect before server-owned dispatch.

        Policy effects are not user-approved material mutations. They still
        need an explicit authority decision before an adapter can run. The
        caller must identify a server-owned surface and the effect must be
        marked ``policy`` in the canonical registry; explicit/strong effects
        can never use this path.
        """

        if str(request.actor_kind or "").strip().lower() not in {"server", "system"}:
            raise AuthorizationError(
                "Los efectos de política requieren actor server/system",
                code="authorization_server_actor_required",
            )
        if not str(request.principal_id or "").strip().startswith("bago-"):
            raise AuthorizationError(
                "La política server-owned requiere un principal BAGO",
                code="authorization_server_principal_required",
            )
        if not str(request.source_surface or "").strip().startswith("server."):
            raise AuthorizationError(
                "La superficie no está registrada como server-owned",
                code="authorization_server_surface_required",
            )
        effect = REGISTRY.get(request.effect_id)
        if effect.authorization_mode != "policy":
            raise AuthorizationError(
                f"{request.effect_id} requiere autorización explícita",
                code="authorization_policy_effect_required",
            )
        if request.policy_version != REGISTRY.digest:
            raise AuthorizationError(
                "La política de ejecución está obsoleta",
                code="authorization_policy_stale",
            )
        now = _now()
        decision_id = f"authdec-policy-{uuid.uuid4().hex}"
        proof_id = f"authproof-policy-{uuid.uuid4().hex}"
        return {
            "state": "authorized",
            "kind": "server_policy",
            "decision_id": decision_id,
            "proof_id": proof_id,
            "operation_fingerprint": request.fingerprint,
            "effect_id": request.effect_id,
            "session_id": request.session_id,
            "issued_at": _iso(now),
            "provenance": {
                "kind": "server_policy",
                "principal_id": request.principal_id,
                "source_surface": request.source_surface,
                "policy_version": request.policy_version,
                "contract": AUTHORIZATION_CONTRACT_VERSION,
            },
        }

    def create_challenge(
        self,
        request: ExecutionRequest,
        *,
        interaction_id: str,
    ) -> dict[str, Any]:
        clean_interaction = str(interaction_id or "").strip()
        if not clean_interaction:
            raise AuthorizationError(
                "Falta interaction_id",
                code="authorization_interaction_required",
            )
        now = _now()
        challenge_id = f"authch-{uuid.uuid4().hex}"
        descriptor = request.public_descriptor()
        record = {
            "challenge_id": challenge_id,
            "state": "pending",
            "interaction_id": clean_interaction,
            "request_id": request.request_id,
            "session_id": request.session_id,
            "principal_id": request.principal_id,
            "effect_id": request.effect_id,
            "target": request.target,
            "arguments_digest": request.arguments_digest,
            "scope": request.scope,
            "operation_fingerprint": request.fingerprint,
            "request_descriptor": descriptor,
            "issued_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=CHALLENGE_TTL_SECONDS)),
        }
        # Compatibility field for the current Capability Packages UI.
        package_id = str(request.target.get("package_id") or "").strip()
        if package_id:
            record["capability_id"] = package_id
        with _LOCK:
            ledger = _read_ledger()
            ledger["challenges"][challenge_id] = record
            _write_ledger(ledger)
        return dict(record)

    def approve_challenge(
        self,
        *,
        challenge_id: str,
        interaction_id: str,
        session_id: str,
        channel: str,
    ) -> dict[str, Any]:
        clean_channel = str(channel or "").strip().lower()
        if clean_channel not in INTERACTIVE_CHANNELS:
            raise AuthorizationError(
                "La autorización no procede de una superficie interactiva admitida",
                code="authorization_user_origin_unverified",
            )
        return self._approve_challenge_record(
            challenge_id=challenge_id, interaction_id=interaction_id,
            session_id=session_id, channel=clean_channel,
        )

    def approve_cli_challenge(
        self,
        *,
        challenge_id: str,
        interaction_id: str,
        session_id: str,
        terminal_confirmed: bool,
    ) -> dict[str, Any]:
        """Approve only from a confirmed interactive local terminal."""
        import sys

        if terminal_confirmed is not True or not sys.stdin.isatty():
            raise AuthorizationError(
                "La aprobación CLI requiere confirmación humana en un TTY",
                code="authorization_cli_terminal_required",
            )
        return self._approve_challenge_record(
            challenge_id=challenge_id, interaction_id=interaction_id,
            session_id=session_id, channel="cli",
        )

    def _approve_challenge_record(
        self,
        *,
        challenge_id: str,
        interaction_id: str,
        session_id: str,
        channel: str,
    ) -> dict[str, Any]:
        now = _now()
        with _LOCK:
            ledger = _read_ledger()
            challenge = ledger["challenges"].get(str(challenge_id or ""))
            if not isinstance(challenge, dict):
                raise AuthorizationError(
                    "Challenge inexistente",
                    code="authorization_challenge_not_found",
                )
            if challenge.get("state") != "pending":
                raise AuthorizationError(
                    "Challenge ya resuelto",
                    code="authorization_challenge_not_pending",
                )
            if str(challenge.get("interaction_id") or "") != str(interaction_id or ""):
                raise AuthorizationError(
                    "interaction_id no coincide",
                    code="authorization_interaction_mismatch",
                )
            if str(challenge.get("session_id") or "") != str(session_id or ""):
                raise AuthorizationError(
                    "La sesión no coincide",
                    code="authorization_session_mismatch",
                )
            if _parse_iso(str(challenge.get("expires_at") or "")) <= now:
                challenge["state"] = "expired"
                _write_ledger(ledger)
                raise AuthorizationError(
                    "Challenge expirado",
                    code="authorization_challenge_expired",
                )

            effect_id = str(challenge.get("effect_id") or "")
            operation_fingerprint = str(challenge.get("operation_fingerprint") or "")
            proof = UserAuthorizationProof(
                proof_id=f"authproof-{uuid.uuid4().hex}",
                principal_id=str(challenge.get("principal_id") or "interactive-local-user"),
                authenticated_session_id=str(session_id),
                interaction_id=str(interaction_id),
                operation_fingerprint=operation_fingerprint,
                effect_id=effect_id,
                user_decision="approve",
                issued_at=_iso(now),
                expires_at=_iso(now + timedelta(seconds=PERMIT_TTL_SECONDS)),
                provenance={
                    "kind": "direct_user_interaction",
                    "channel": channel,
                    "contract": AUTHORIZATION_CONTRACT_VERSION,
                },
            )
            decision = AuthorizationDecision(
                decision_id=f"authdec-{uuid.uuid4().hex}",
                result="allow",
                proof_id=proof.proof_id,
                operation_fingerprint=proof.operation_fingerprint,
                effect_id=effect_id,
                reason="verified_direct_user_interaction",
                decided_at=_iso(now),
            )
            raw_token = _new_permit_token()
            permit = Permit(
                permit_id=f"permit-{uuid.uuid4().hex}",
                token=raw_token,
                decision_id=decision.decision_id,
                proof_id=proof.proof_id,
                operation_fingerprint=proof.operation_fingerprint,
                request_id=str(challenge.get("request_id") or ""),
                effect_id=effect_id,
                session_id=str(session_id),
                issued_at=_iso(now),
                expires_at=proof.expires_at,
            )
            permit_hash = _token_hash(raw_token)
            ledger["permits"][permit_hash] = {
                **{key: value for key, value in asdict(permit).items() if key != "token"},
                "state": "active",
                "proof": asdict(proof),
                "decision": asdict(decision),
            }
            challenge["state"] = "approved"
            challenge["approved_at"] = _iso(now)
            challenge["proof_id"] = proof.proof_id
            challenge["decision_id"] = decision.decision_id
            challenge["permit_id"] = permit.permit_id
            _write_ledger(ledger)

        return {
            "proof": asdict(proof),
            "decision": asdict(decision),
            "permit": asdict(permit),
        }

    def issue_delegated_permit(
        self,
        *,
        request: ExecutionRequest,
        state_dir: Path | str,
        schedule_id: str,
        schedule_digest: str,
    ) -> dict[str, Any]:
        """Mint one normal, short-lived Permit from a bounded DelegationGrant.

        Spending one grant run happens before a child Permit is exposed. If
        subsequent Permit persistence fails, authority is lost rather than
        duplicated.
        """
        from delegation_grant import DelegationGrantRegistry

        if not str(request.delegation_id or "").strip():
            raise AuthorizationError(
                "Delegated execution requires delegation_id",
                code="authorization_delegation_required",
            )

        registry = DelegationGrantRegistry(state_dir)
        claim = registry.claim_child(
            request.delegation_id,
            request,
            schedule_id=schedule_id,
            schedule_digest=schedule_digest,
        )

        now = _now()
        delegation_deadline = _parse_iso(str(claim.get("expires_at") or ""))
        permit_deadline = min(
            now + timedelta(seconds=PERMIT_TTL_SECONDS),
            delegation_deadline,
        )
        if permit_deadline <= now:
            raise AuthorizationError(
                "Delegation expired before Permit issuance",
                code="authorization_delegation_expired",
            )

        proof_id = str(claim.get("proof_id") or "").strip()
        if not proof_id:
            raise AuthorizationError(
                "Delegation provenance is incomplete",
                code="authorization_delegation_provenance_missing",
            )

        decision = AuthorizationDecision(
            decision_id=f"authdec-{uuid.uuid4().hex}",
            result="allow",
            proof_id=proof_id,
            operation_fingerprint=request.fingerprint,
            effect_id=request.effect_id,
            reason="delegation_grant_child",
            decided_at=_iso(now),
        )
        raw_token = _new_permit_token()
        permit = Permit(
            permit_id=f"permit-{uuid.uuid4().hex}",
            token=raw_token,
            decision_id=decision.decision_id,
            proof_id=proof_id,
            operation_fingerprint=request.fingerprint,
            request_id=request.request_id,
            effect_id=request.effect_id,
            session_id=request.session_id,
            issued_at=_iso(now),
            expires_at=_iso(permit_deadline),
        )
        permit_hash = _token_hash(raw_token)
        delegated_proof = {
            "proof_id": proof_id,
            "principal_id": request.principal_id,
            "authenticated_session_id": request.session_id,
            "operation_fingerprint": request.fingerprint,
            "effect_id": request.effect_id,
            "user_decision": "delegated",
            "issued_at": _iso(now),
            "expires_at": _iso(permit_deadline),
            "provenance": {
                "kind": "delegation_grant",
                "grant_id": str(claim.get("grant_id") or ""),
                "claim_id": str(claim.get("claim_id") or ""),
                "schedule_id": str(claim.get("schedule_id") or ""),
                "origin_proof_id": proof_id,
                "contract": AUTHORIZATION_CONTRACT_VERSION,
            },
        }

        with _LOCK:
            ledger = _read_ledger()
            ledger["permits"][permit_hash] = {
                **{key: value for key, value in asdict(permit).items() if key != "token"},
                "state": "active",
                "proof": delegated_proof,
                "decision": asdict(decision),
                "delegation": dict(claim),
            }
            _write_ledger(ledger)

        return {
            "proof": delegated_proof,
            "decision": asdict(decision),
            "permit": asdict(permit),
            "delegation": dict(claim),
        }

    def revoke_permit(self, permit_id: str, *, reason: str = "") -> dict[str, Any]:
        """Revoke an issued or already-consumed Permit for future admissions.

        Revocation cannot undo an effect that already completed. It does make
        subsequent compound-child admissions fail closed. The same authority
        lock is held by consumed_authority_lease(), which gives revocation vs.
        material-child dispatch a single linearization order.
        """

        clean_permit_id = str(permit_id or "").strip()
        if not clean_permit_id:
            raise AuthorizationError("permit_id is required", code="authorization_permit_id_required")
        with _LOCK:
            ledger = _read_ledger()
            record = next(
                (
                    item
                    for item in ledger["permits"].values()
                    if isinstance(item, dict) and str(item.get("permit_id") or "") == clean_permit_id
                ),
                None,
            )
            if not isinstance(record, dict):
                raise AuthorizationError("Permit desconocido", code="authorization_permit_invalid")
            if str(record.get("state") or "") == "revoked":
                return dict(record)
            record["state"] = "revoked"
            record["revoked_at"] = _iso(_now())
            record["revocation_reason"] = str(reason or "")[:500]
            _write_ledger(ledger)
            return dict(record)

    @contextmanager
    def consumed_authority_lease(
        self,
        *,
        authorization: dict[str, Any],
        request: ExecutionRequest,
        delegation_state_dir: Path | str | None = None,
    ):
        """Revalidate and pin current authority for one compound child effect.

        This is a read-only admission primitive. It does not mint, consume,
        expand or transfer authority. The authorization lock remains held until
        the child materializer returns, so revoke_permit() linearizes either
        before the child (zero effect) or after it completes.
        """

        permit_id = str((authorization or {}).get("permit_id") or "").strip()
        if not permit_id:
            raise AuthorizationError(
                "Compound child requires a consumed parent Permit reference",
                code="authorization_parent_permit_missing",
            )

        with _LOCK:
            ledger = _read_ledger()
            record = next(
                (
                    item
                    for item in ledger["permits"].values()
                    if isinstance(item, dict) and str(item.get("permit_id") or "") == permit_id
                ),
                None,
            )
            if not isinstance(record, dict):
                raise AuthorizationError("Permit desconocido", code="authorization_permit_invalid")

            state = str(record.get("state") or "")
            if state == "revoked":
                raise AuthorizationError("Permit revocado", code="authorization_permit_revoked")
            if state != "consumed":
                raise AuthorizationError(
                    "Compound child requires a consumed parent Permit",
                    code="authorization_parent_permit_not_consumed",
                )
            if _parse_iso(str(record.get("expires_at") or "")) <= _now():
                raise AuthorizationError("Permit expirado", code="authorization_permit_expired")
            if str(record.get("session_id") or "") != request.session_id:
                raise AuthorizationError(
                    "Permit ligado a otra sesión",
                    code="authorization_permit_session_mismatch",
                )
            if str(record.get("effect_id") or "") != request.effect_id:
                raise AuthorizationError(
                    "Permit ligado a otro effect_id",
                    code="authorization_effect_mismatch",
                )
            if str(record.get("operation_fingerprint") or "") != request.fingerprint:
                raise AuthorizationError(
                    "La operación cambió después de la autorización",
                    code="authorization_operation_mismatch",
                )
            if str(record.get("executed_request_id") or "") != request.request_id:
                raise AuthorizationError(
                    "El Permit consumido pertenece a otra ejecución",
                    code="authorization_execution_lineage_mismatch",
                )

            proof = record.get("proof") if isinstance(record.get("proof"), dict) else {}
            provenance = proof.get("provenance") if isinstance(proof.get("provenance"), dict) else {}
            if str(provenance.get("kind") or "") == "delegation_grant":
                grant_id = str(provenance.get("grant_id") or "").strip()
                if not grant_id or grant_id != str(request.delegation_id or "").strip():
                    raise AuthorizationError(
                        "Delegated parent Permit no longer matches its grant",
                        code="authorization_delegation_mismatch",
                    )
                if delegation_state_dir is None:
                    raise AuthorizationError(
                        "Delegated authority freshness requires state_dir",
                        code="authorization_delegation_state_required",
                    )
                from delegation_grant import DelegationError, DelegationGrantRegistry

                try:
                    with DelegationGrantRegistry(delegation_state_dir).freshness_lease(
                        grant_id,
                        principal_id=request.principal_id,
                        policy_version=request.policy_version,
                    ):
                        yield dict(record)
                except DelegationError as exc:
                    raise AuthorizationError(str(exc), code=exc.code) from exc
                return

            yield dict(record)

    def consume_permit(
        self,
        *,
        permit_token: str,
        request: ExecutionRequest,
    ) -> dict[str, Any]:
        token = str(permit_token or "").strip()
        if not token:
            raise AuthorizationError(
                "La ejecución requiere un Permit emitido por AuthorizationBoundary",
                code="authorization_permit_required",
            )
        now = _now()
        permit_hash = _token_hash(token)
        with _LOCK:
            ledger = _read_ledger()
            record = ledger["permits"].get(permit_hash)
            if not isinstance(record, dict):
                raise AuthorizationError(
                    "Permit desconocido",
                    code="authorization_permit_invalid",
                )
            if record.get("state") != "active":
                raise AuthorizationError(
                    "Permit ya consumido o revocado",
                    code="authorization_permit_replay",
                )
            if str(record.get("session_id") or "") != request.session_id:
                raise AuthorizationError(
                    "Permit ligado a otra sesión",
                    code="authorization_permit_session_mismatch",
                )
            if str(record.get("effect_id") or "") != request.effect_id:
                raise AuthorizationError(
                    "Permit ligado a otro effect_id",
                    code="authorization_effect_mismatch",
                )
            if str(record.get("operation_fingerprint") or "") != request.fingerprint:
                raise AuthorizationError(
                    "La operación cambió después de la autorización",
                    code="authorization_operation_mismatch",
                )
            if _parse_iso(str(record.get("expires_at") or "")) <= now:
                record["state"] = "expired"
                _write_ledger(ledger)
                raise AuthorizationError(
                    "Permit expirado",
                    code="authorization_permit_expired",
                )

            # Consume-before-execute closes replay even if the material effect fails.
            record["state"] = "consumed"
            record["consumed_at"] = _iso(now)
            record["executed_request_id"] = request.request_id
            record["executed_request"] = request.public_descriptor()
            _write_ledger(ledger)
            return dict(record)


__all__ = [
    "AUTHORIZATION_CONTRACT_VERSION",
    "AuthorizationBoundary",
    "AuthorizationDecision",
    "AuthorizationError",
    "AuthorizationOperation",
    "Permit",
    "UserAuthorizationProof",
    "authorization_ledger_path",
    "build_operation",
]

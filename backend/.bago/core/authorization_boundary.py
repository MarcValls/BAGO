"""User authorization provenance boundary for material execution.

This module makes user authorization a server-owned, replay-safe capability.
Client booleans such as `confirmed=true` are not authority.

Flow:
    operation -> challenge -> direct user decision -> proof -> decision
    -> one-time permit -> ExecutionGateway -> material execution
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from bago_core.user_state_paths import state_root


AUTHORIZATION_CONTRACT_VERSION = "bago.authorization/v1"
CHALLENGE_TTL_SECONDS = 180
PERMIT_TTL_SECONDS = 120
INTERACTIVE_CHANNELS = frozenset({"ui-react", "desktop"})
_LOCK = threading.RLock()
_T = TypeVar("_T")


class AuthorizationError(ValueError):
    """Fail-closed authorization error with a stable machine code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AuthorizationOperation:
    capability_id: str
    inputs: Any
    permissions: tuple[str, ...]
    session_id: str

    @property
    def fingerprint(self) -> str:
        payload = {
            "capability_id": self.capability_id,
            "inputs": self.inputs,
            "permissions": list(self.permissions),
            "session_id": self.session_id,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class UserAuthorizationProof:
    proof_id: str
    principal_id: str
    authenticated_session_id: str
    interaction_id: str
    operation_fingerprint: str
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
    reason: str
    decided_at: str


@dataclass(frozen=True)
class Permit:
    permit_id: str
    token: str
    decision_id: str
    proof_id: str
    operation_fingerprint: str
    session_id: str
    issued_at: str
    expires_at: str


def build_operation(
    *,
    capability_id: str,
    inputs: Any,
    permissions: Any,
    session_id: str,
) -> AuthorizationOperation:
    clean_capability = str(capability_id or "").strip()
    clean_session = str(session_id or "").strip()
    if not clean_capability:
        raise AuthorizationError("Falta capability_id", code="authorization_invalid_operation")
    if not clean_session:
        raise AuthorizationError("Falta session_id autenticada", code="authorization_session_required")
    clean_permissions = tuple(sorted({str(item) for item in (permissions or []) if str(item)}))
    return AuthorizationOperation(
        capability_id=clean_capability,
        inputs=inputs if inputs is not None else {},
        permissions=clean_permissions,
        session_id=clean_session,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise AuthorizationError("Timestamp de autorización inválido", code="authorization_invalid_timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ledger_path() -> Path:
    return state_root() / "authorization" / "ledger.json"


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
    data.setdefault("contract_version", AUTHORIZATION_CONTRACT_VERSION)
    data.setdefault("challenges", {})
    data.setdefault("permits", {})
    return data


def _write_ledger(data: dict[str, Any]) -> None:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


class AuthorizationBoundary:
    """Owns challenge, user-origin verification, decision and permit issuance."""

    def create_challenge(
        self,
        operation: AuthorizationOperation,
        *,
        interaction_id: str,
    ) -> dict[str, Any]:
        clean_interaction = str(interaction_id or "").strip()
        if not clean_interaction:
            raise AuthorizationError("Falta interaction_id", code="authorization_interaction_required")
        now = _now()
        challenge_id = f"authch-{uuid.uuid4().hex}"
        record = {
            "challenge_id": challenge_id,
            "state": "pending",
            "interaction_id": clean_interaction,
            "session_id": operation.session_id,
            "capability_id": operation.capability_id,
            "permissions": list(operation.permissions),
            "operation_fingerprint": operation.fingerprint,
            "issued_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=CHALLENGE_TTL_SECONDS)),
        }
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
        now = _now()
        with _LOCK:
            ledger = _read_ledger()
            challenge = ledger["challenges"].get(str(challenge_id or ""))
            if not isinstance(challenge, dict):
                raise AuthorizationError("Challenge inexistente", code="authorization_challenge_not_found")
            if challenge.get("state") != "pending":
                raise AuthorizationError("Challenge ya resuelto", code="authorization_challenge_not_pending")
            if str(challenge.get("interaction_id") or "") != str(interaction_id or ""):
                raise AuthorizationError("interaction_id no coincide", code="authorization_interaction_mismatch")
            if str(challenge.get("session_id") or "") != str(session_id or ""):
                raise AuthorizationError("La sesión no coincide", code="authorization_session_mismatch")
            if _parse_iso(str(challenge.get("expires_at") or "")) <= now:
                challenge["state"] = "expired"
                _write_ledger(ledger)
                raise AuthorizationError("Challenge expirado", code="authorization_challenge_expired")

            proof = UserAuthorizationProof(
                proof_id=f"authproof-{uuid.uuid4().hex}",
                principal_id="interactive-local-user",
                authenticated_session_id=str(session_id),
                interaction_id=str(interaction_id),
                operation_fingerprint=str(challenge["operation_fingerprint"]),
                user_decision="approve",
                issued_at=_iso(now),
                expires_at=_iso(now + timedelta(seconds=PERMIT_TTL_SECONDS)),
                provenance={
                    "kind": "direct_user_interaction",
                    "channel": clean_channel,
                    "contract": AUTHORIZATION_CONTRACT_VERSION,
                },
            )
            decision = AuthorizationDecision(
                decision_id=f"authdec-{uuid.uuid4().hex}",
                result="allow",
                proof_id=proof.proof_id,
                operation_fingerprint=proof.operation_fingerprint,
                reason="verified_direct_user_interaction",
                decided_at=_iso(now),
            )
            raw_token = secrets.token_urlsafe(32)
            permit = Permit(
                permit_id=f"permit-{uuid.uuid4().hex}",
                token=raw_token,
                decision_id=decision.decision_id,
                proof_id=proof.proof_id,
                operation_fingerprint=proof.operation_fingerprint,
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

    def consume_permit(
        self,
        *,
        permit_token: str,
        operation: AuthorizationOperation,
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
                raise AuthorizationError("Permit desconocido", code="authorization_permit_invalid")
            if record.get("state") != "active":
                raise AuthorizationError("Permit ya consumido o revocado", code="authorization_permit_replay")
            if str(record.get("session_id") or "") != operation.session_id:
                raise AuthorizationError("Permit ligado a otra sesión", code="authorization_permit_session_mismatch")
            if str(record.get("operation_fingerprint") or "") != operation.fingerprint:
                raise AuthorizationError(
                    "La operación cambió después de la autorización",
                    code="authorization_operation_mismatch",
                )
            if _parse_iso(str(record.get("expires_at") or "")) <= now:
                record["state"] = "expired"
                _write_ledger(ledger)
                raise AuthorizationError("Permit expirado", code="authorization_permit_expired")

            # Consume-before-execute closes replay even if material execution fails.
            record["state"] = "consumed"
            record["consumed_at"] = _iso(now)
            _write_ledger(ledger)
            return dict(record)


class ExecutionGateway:
    """The only HTTP capability execution path after a verified one-time Permit."""

    def __init__(self, boundary: AuthorizationBoundary | None = None) -> None:
        self.boundary = boundary or AuthorizationBoundary()

    def execute(
        self,
        *,
        permit_token: str,
        operation: AuthorizationOperation,
        executor: Callable[[], _T],
    ) -> tuple[_T, dict[str, Any]]:
        authorization = self.boundary.consume_permit(
            permit_token=permit_token,
            operation=operation,
        )
        result = executor()
        return result, authorization

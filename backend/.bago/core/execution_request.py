"""Generic execution request contract for governed BAGO effects.

An ExecutionRequest describes *what* is requested. It does not grant authority
and it does not carry an executable callable.

The authorization fingerprint binds the requested effect, target, arguments
(digest only), scope, actor/session and policy version.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from effect_registry import REGISTRY, EffectRegistryError


EXECUTION_REQUEST_CONTRACT = "bago.execution-request/v2"


class ExecutionRequestError(ValueError):
    def __init__(self, message: str, *, code: str = "execution_request_invalid") -> None:
        super().__init__(message)
        self.code = code


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError) as exc:
        raise ExecutionRequestError(
            f"ExecutionRequest contains non-serializable data: {exc}",
            code="execution_request_not_serializable",
        ) from exc


def stable_digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    effect_id: str
    actor_kind: str
    principal_id: str
    session_id: str
    source_surface: str
    target: dict[str, Any]
    arguments: Any
    scope: str
    policy_version: str
    request_id: str = field(default_factory=lambda: f"exec-{uuid.uuid4().hex}")
    parent_execution_id: str = ""
    delegation_id: str = ""
    preconditions: tuple[str, ...] = ()

    @property
    def arguments_digest(self) -> str:
        return stable_digest(self.arguments)

    @property
    def target_digest(self) -> str:
        return stable_digest(self.target)

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        # request_id is deliberately excluded: the same exact material
        # operation is reconstructed across challenge/approve/execute HTTP
        # calls. Authority binds to operation semantics, not transport identity.
        return {
            "contract": EXECUTION_REQUEST_CONTRACT,
            "effect_id": self.effect_id,
            "actor_kind": self.actor_kind,
            "principal_id": self.principal_id,
            "session_id": self.session_id,
            "source_surface": self.source_surface,
            "target_digest": self.target_digest,
            "arguments_digest": self.arguments_digest,
            "scope": self.scope,
            "policy_version": self.policy_version,
            "parent_execution_id": self.parent_execution_id,
            "delegation_id": self.delegation_id,
            "preconditions": sorted(self.preconditions),
        }

    @property
    def fingerprint(self) -> str:
        return stable_digest(self.fingerprint_payload)

    def public_descriptor(self) -> dict[str, Any]:
        """Return authorization-safe metadata without raw arguments."""
        return {
            "request_id": self.request_id,
            "contract": EXECUTION_REQUEST_CONTRACT,
            "effect_id": self.effect_id,
            "actor_kind": self.actor_kind,
            "principal_id": self.principal_id,
            "session_id": self.session_id,
            "source_surface": self.source_surface,
            "target": self.target,
            "target_digest": self.target_digest,
            "arguments_digest": self.arguments_digest,
            "scope": self.scope,
            "policy_version": self.policy_version,
            "parent_execution_id": self.parent_execution_id,
            "delegation_id": self.delegation_id,
            "preconditions": list(self.preconditions),
            "operation_fingerprint": self.fingerprint,
        }


def build_execution_request(
    *,
    effect_id: str,
    actor_kind: str,
    principal_id: str,
    session_id: str,
    source_surface: str,
    target: dict[str, Any] | None,
    arguments: Any,
    scope: str | None = None,
    policy_version: str | None = None,
    request_id: str | None = None,
    parent_execution_id: str = "",
    delegation_id: str = "",
    preconditions: tuple[str, ...] | list[str] = (),
) -> ExecutionRequest:
    clean_effect = str(effect_id or "").strip()
    clean_actor = str(actor_kind or "").strip().lower()
    clean_principal = str(principal_id or "").strip()
    clean_session = str(session_id or "").strip()
    clean_surface = str(source_surface or "").strip()
    clean_parent = str(parent_execution_id or "").strip()
    clean_delegation = str(delegation_id or "").strip()

    if not clean_effect:
        raise ExecutionRequestError("effect_id is required", code="execution_effect_required")
    try:
        effect = REGISTRY.get(clean_effect)
    except EffectRegistryError as exc:
        raise ExecutionRequestError(str(exc), code="execution_effect_unknown") from exc
    if not clean_actor:
        raise ExecutionRequestError("actor_kind is required", code="execution_actor_required")
    if not clean_principal:
        raise ExecutionRequestError("principal_id is required", code="execution_principal_required")
    if not clean_session:
        raise ExecutionRequestError("session_id is required", code="execution_session_required")
    if not clean_surface:
        raise ExecutionRequestError("source_surface is required", code="execution_surface_required")
    if target is not None and not isinstance(target, dict):
        raise ExecutionRequestError("target must be an object", code="execution_target_invalid")

    selected_scope = str(scope or effect.default_scope).strip()
    if not selected_scope:
        raise ExecutionRequestError("scope is required", code="execution_scope_required")
    selected_policy = str(policy_version or REGISTRY.digest).strip()
    if not selected_policy:
        raise ExecutionRequestError("policy_version is required", code="execution_policy_required")

    request = ExecutionRequest(
        request_id=str(request_id or f"exec-{uuid.uuid4().hex}").strip(),
        effect_id=clean_effect,
        actor_kind=clean_actor,
        principal_id=clean_principal,
        session_id=clean_session,
        source_surface=clean_surface,
        target=dict(target or {}),
        arguments=arguments if arguments is not None else {},
        scope=selected_scope,
        policy_version=selected_policy,
        parent_execution_id=clean_parent,
        delegation_id=clean_delegation,
        preconditions=tuple(str(item).strip() for item in preconditions if str(item).strip()),
    )
    # Force canonical serialization now, before authority can be requested.
    _ = request.fingerprint
    return request


__all__ = [
    "EXECUTION_REQUEST_CONTRACT",
    "ExecutionRequest",
    "ExecutionRequestError",
    "build_execution_request",
    "stable_digest",
]

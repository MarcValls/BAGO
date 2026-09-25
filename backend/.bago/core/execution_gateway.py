"""Closed execution gateway for governed BAGO effects.

Callers submit an ExecutionRequest plus a Permit. They cannot supply a callable.
The gateway resolves the executable adapter from a server-owned registry keyed
by canonical effect_id.
"""


import threading
from typing import Any

from authorization_boundary import AuthorizationBoundary, AuthorizationError
from effect_registry import REGISTRY
from execution_request import ExecutionRequest
from execution_adapter_contract import EffectAdapter, ExecutionContext, ExecutionGatewayError
from execution_claims import (
    ExecutionClaimError,
    ExecutionClaimStore,
    coerce_execution_claim,
    execution_resource_key,
    execution_claim_store_for,
)


class EffectAdapterRegistry:
    """Server-owned mapping from effect_id to implementation."""

    def __init__(self) -> None:
        self._by_effect: dict[str, EffectAdapter] = {}

    def register(self, adapter: EffectAdapter) -> None:
        effect_ids = getattr(adapter, "effect_ids", frozenset())
        if not effect_ids:
            raise ExecutionGatewayError(
                "Effect adapter must declare at least one effect_id",
                code="execution_adapter_effects_required",
            )
        for effect_id in effect_ids:
            clean = str(effect_id or "").strip()
            if not clean:
                raise ExecutionGatewayError(
                    "Effect adapter contains an empty effect_id",
                    code="execution_adapter_effect_invalid",
                )
            if not REGISTRY.contains(clean):
                raise ExecutionGatewayError(
                    f"Effect adapter declares unknown canonical effect_id {clean}",
                    code="execution_adapter_effect_unknown",
                )
            if clean in self._by_effect:
                raise ExecutionGatewayError(
                    f"Effect adapter already registered for {clean}",
                    code="execution_adapter_duplicate",
                )
        for effect_id in effect_ids:
            self._by_effect[str(effect_id)] = adapter

    def resolve(self, effect_id: str) -> EffectAdapter:
        clean = str(effect_id or "").strip()
        adapter = self._by_effect.get(clean)
        if adapter is None:
            raise ExecutionGatewayError(
                f"No EffectAdapter registered for {clean}",
                code="execution_adapter_missing",
            )
        return adapter

    def registered_effects(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_effect))


from execution_adapters.capability import CapabilityRuntimeEffectAdapter
from execution_adapters.context import ContextAttachEffectAdapter
from execution_adapters.filesystem import FilesystemEffectAdapter, FilesystemReadEffectAdapter
from execution_adapters.workspace import SessionWorkspaceMirrorEffectAdapter, WorkspaceBindEffectAdapter, WorkspaceMirrorSyncEffectAdapter
from execution_adapters.session_state import StateDeleteEffectAdapter, ServerStateEffectAdapter
from execution_adapters.network import GatewayHTTPResponse, NetworkReadEffectAdapter
from execution_adapters.process import ProcessExecutionEffectAdapter
from execution_adapters.pi_sidecar import PiSidecarProcessEffectAdapter
from execution_adapters.plan import PlanRuntimeEffectAdapter
from execution_adapters.project import ProjectWriteEffectAdapter
from execution_adapters.credentials import CredentialWriteEffectAdapter
from execution_adapters.delegation import DelegationGrantEffectAdapter
from execution_adapters.release import ReleaseDownloadEffectAdapter
from execution_adapters.release_signature import ReleaseSignatureEffectAdapter
from execution_adapters.release_stage import ReleaseBundleStageEffectAdapter
from execution_adapters.release_job_state import ReleaseJobStateEffectAdapter
from execution_adapters.release_job_log import ReleaseJobLogEffectAdapter
from execution_adapters.structured_logging import StructuredLoggingEffectAdapter
from execution_adapters.validation_staging import ValidationStagingEffectAdapter
from execution_adapters.release_job_archive import ReleaseJobArchiveEffectAdapter
from execution_adapters.system_update import SystemUpdateApplyEffectAdapter
from execution_adapters.system_install import SystemInstallEffectAdapter
from execution_adapters.system_install_rollback import SystemInstallRollbackEffectAdapter
from execution_adapters.source_update import SystemSourceUpdateEffectAdapter
from execution_adapters.system_install_uninstall import SystemInstallUninstallEffectAdapter
from execution_adapters.manager_settings import ManagerSettingsWriteEffectAdapter
from execution_adapters.capability_import import CapabilityPackageImportEffectAdapter
from execution_adapters.autonomous import AutonomousObservationEffectAdapter, AutonomousRepairEffectAdapter
from execution_adapters.monitor import ProcessMonitorGenerateEffectAdapter
from execution_adapters.canary import SecurityCanaryEffectAdapter
from execution_adapters.repository_inspection import RepositoryInspectionEffectAdapter
from execution_adapters.repository_guard import RepositoryGuardEffectAdapter
from execution_adapters.evidence_bundle import EvidenceBundleGenerateEffectAdapter
from execution_adapters.archive_rollback import SystemInstallArchiveRollbackEffectAdapter
from execution_adapters.runtime_state import RuntimeStateBootstrapEffectAdapter
from execution_adapters.database_write import DatabaseWriteEffectAdapter


def build_default_effect_adapter_registry() -> EffectAdapterRegistry:
    registry = EffectAdapterRegistry()
    registry.register(FilesystemEffectAdapter())
    registry.register(FilesystemReadEffectAdapter())
    registry.register(ContextAttachEffectAdapter())
    registry.register(WorkspaceBindEffectAdapter())
    registry.register(SessionWorkspaceMirrorEffectAdapter())
    registry.register(WorkspaceMirrorSyncEffectAdapter())
    registry.register(StateDeleteEffectAdapter())
    registry.register(ServerStateEffectAdapter())
    registry.register(NetworkReadEffectAdapter())
    registry.register(ProcessExecutionEffectAdapter())
    registry.register(PiSidecarProcessEffectAdapter())
    registry.register(CapabilityRuntimeEffectAdapter())
    registry.register(PlanRuntimeEffectAdapter())
    registry.register(DelegationGrantEffectAdapter())
    registry.register(ProjectWriteEffectAdapter())
    registry.register(CredentialWriteEffectAdapter())
    registry.register(ReleaseDownloadEffectAdapter())
    registry.register(ReleaseSignatureEffectAdapter())
    registry.register(ReleaseBundleStageEffectAdapter())
    registry.register(ReleaseJobStateEffectAdapter())
    registry.register(ReleaseJobLogEffectAdapter())
    registry.register(StructuredLoggingEffectAdapter())
    registry.register(ValidationStagingEffectAdapter())
    registry.register(ReleaseJobArchiveEffectAdapter())
    registry.register(SystemUpdateApplyEffectAdapter())
    registry.register(SystemInstallEffectAdapter())
    registry.register(SystemInstallRollbackEffectAdapter())
    registry.register(SystemSourceUpdateEffectAdapter())
    registry.register(SystemInstallUninstallEffectAdapter())
    registry.register(ManagerSettingsWriteEffectAdapter())
    registry.register(CapabilityPackageImportEffectAdapter())
    registry.register(AutonomousObservationEffectAdapter())
    registry.register(AutonomousRepairEffectAdapter())
    registry.register(ProcessMonitorGenerateEffectAdapter())
    registry.register(SecurityCanaryEffectAdapter())
    registry.register(RepositoryInspectionEffectAdapter())
    registry.register(RepositoryGuardEffectAdapter())
    registry.register(EvidenceBundleGenerateEffectAdapter())
    registry.register(SystemInstallArchiveRollbackEffectAdapter())
    registry.register(RuntimeStateBootstrapEffectAdapter())
    registry.register(DatabaseWriteEffectAdapter())
    return registry


class ExecutionGateway:
    """Consume a Permit and dispatch only through server-owned EffectAdapters."""

    def __init__(
        self,
        boundary: AuthorizationBoundary | None = None,
        adapters: EffectAdapterRegistry | None = None,
        claim_store: ExecutionClaimStore | None = None,
    ) -> None:
        self.boundary = boundary or AuthorizationBoundary()
        self.adapters = adapters or build_default_effect_adapter_registry()
        self._injected_claim_store = claim_store

    def claim_store_for(self, manager: Any) -> ExecutionClaimStore:
        """Resolve coordination storage from the trusted SessionManager state root."""
        if self._injected_claim_store is not None:
            return self._injected_claim_store
        return execution_claim_store_for(manager)

    def execute(
        self,
        *,
        permit_token: str,
        request: ExecutionRequest,
        context: ExecutionContext | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        # Resolve first so a configuration error does not consume a valid Permit.
        adapter = self.adapters.resolve(request.effect_id)
        if self._is_server_policy_only(adapter, request.effect_id):
            raise ExecutionGatewayError(
                f"{request.effect_id} is server-policy-only",
                code="execution_server_policy_only",
            )
        caller_context = context or ExecutionContext()
        authorization = self.boundary.consume_permit(
            permit_token=permit_token,
            request=request,
        )
        # Durable claim storage can create its SQLite database and parent
        # directory. Resolve it only after the parent Permit has been consumed
        # so an invalid/replayed request has no filesystem effect.
        claim_store = (
            self.claim_store_for(caller_context.manager)
            if request.effect_id == "plan.execute"
            else None
        )
        trusted_context = caller_context
        trusted_services = dict(trusted_context.services)
        # Claim objects are gateway-issued coordination context, never inputs
        # accepted from an API caller.
        trusted_services.pop("_execution_claim", None)
        trusted_services.pop("_execution_claim_store", None)
        # Gateway-owned metadata overwrites any caller-supplied value.
        trusted_services["_authorization"] = authorization
        trusted_services["_gateway"] = self
        if claim_store is not None:
            trusted_services["_execution_claim_store"] = claim_store
        trusted_context = ExecutionContext(
            manager=trusted_context.manager,
            services=trusted_services,
        )
        result = adapter.execute(request, trusted_context)
        return result, authorization

    def execute_server_owned(
        self,
        *,
        request: ExecutionRequest,
        context: ExecutionContext | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Dispatch one canonical policy effect without a user Permit.

        This path is intentionally narrower than ``execute``: only adapters
        explicitly marked ``server_policy_only`` and effects declared as
        ``policy`` may use it. Authority is still resolved before dispatch and
        the adapter remains the sole materializer.
        """

        adapter = self.adapters.resolve(request.effect_id)
        if not self._is_server_policy_only(adapter, request.effect_id):
            raise ExecutionGatewayError(
                f"{request.effect_id} is not a server-policy adapter",
                code="execution_server_adapter_required",
            )
        try:
            authorization = self.boundary.authorize_server_policy(request)
        except AuthorizationError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc
        trusted_context = context or ExecutionContext()
        trusted_services = dict(trusted_context.services)
        trusted_services["_authorization"] = authorization
        trusted_services["_gateway"] = self
        trusted_context = ExecutionContext(
            manager=trusted_context.manager,
            services=trusted_services,
        )
        result = adapter.execute(request, trusted_context)
        return result, authorization

    @staticmethod
    def _is_server_policy_only(adapter: Any, effect_id: str) -> bool:
        effects = getattr(adapter, "server_policy_effects", None)
        if effects is not None:
            return str(effect_id) in effects
        return bool(getattr(adapter, "server_policy_only", False))

    def execute_nested(
        self,
        *,
        parent_request: ExecutionRequest,
        child_request: ExecutionRequest,
        context: ExecutionContext,
    ) -> tuple[Any, dict[str, Any]]:
        """Dispatch a declared compound child without minting another Permit.

        The parent ``plan.execute`` Permit is consumed exactly once by
        ``execute``. This method is only an internal gateway dispatch: it
        accepts a child whose effect, target digest, workflow binding and
        idempotency preconditions were declared in the parent request. It
        never creates or consumes authority and rejects child risk above the
        parent's canonical effect.
        """

        if parent_request.effect_id != "plan.execute":
            raise ExecutionGatewayError(
                "Nested dispatch requires a plan.execute parent",
                code="execution_nested_parent_invalid",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or str(authorization.get("state") or "") != "consumed":
            raise ExecutionGatewayError(
                "Nested dispatch requires consumed parent authorization",
                code="execution_nested_authorization_missing",
            )
        if context.services.get("_gateway") is not self:
            raise ExecutionGatewayError(
                "Nested dispatch requires the active gateway context",
                code="execution_nested_gateway_context_missing",
            )
        if str(authorization.get("effect_id") or "") != parent_request.effect_id:
            raise ExecutionGatewayError(
                "Nested authorization effect differs from the parent request",
                code="execution_nested_authorization_effect_mismatch",
            )
        if str(authorization.get("operation_fingerprint") or "") != parent_request.fingerprint:
            raise ExecutionGatewayError(
                "Nested parent authorization fingerprint mismatch",
                code="execution_nested_parent_fingerprint_mismatch",
            )
        if child_request.parent_execution_id != parent_request.request_id:
            raise ExecutionGatewayError(
                "Nested child lineage is not bound to the parent request",
                code="execution_nested_lineage_mismatch",
            )
        if child_request.delegation_id != parent_request.delegation_id:
            raise ExecutionGatewayError(
                "Nested child delegation reference differs from parent",
                code="execution_nested_delegation_mismatch",
            )
        if (
            child_request.session_id != parent_request.session_id
            or child_request.principal_id != parent_request.principal_id
            or child_request.actor_kind != parent_request.actor_kind
        ):
            raise ExecutionGatewayError(
                "Nested child identity exceeds the parent request",
                code="execution_nested_identity_mismatch",
            )
        if child_request.source_surface != "plan.runtime":
            raise ExecutionGatewayError(
                "Nested child must originate in the governed PlanEngine runtime",
                code="execution_nested_surface_invalid",
            )

        parent_target = parent_request.target if isinstance(parent_request.target, dict) else {}
        child_effects = parent_target.get("child_effects")
        if not isinstance(child_effects, list):
            raise ExecutionGatewayError(
                "Parent plan request lacks declared child effects",
                code="execution_nested_children_missing",
            )
        pipeline = child_request.target.get("_pipeline") if isinstance(child_request.target, dict) else None
        if not isinstance(pipeline, dict):
            raise ExecutionGatewayError(
                "Nested child lacks 04-FIX2 pipeline binding",
                code="execution_nested_pipeline_binding_missing",
            )
        operation_id = str(pipeline.get("pipeline_operation_id") or "")
        step_id = str(pipeline.get("step_id") or "")
        if operation_id != str(parent_target.get("pipeline_operation_id") or "") or not step_id:
            raise ExecutionGatewayError(
                "Nested child pipeline binding differs from parent",
                code="execution_nested_pipeline_binding_mismatch",
            )

        preconditions = set(child_request.preconditions)
        idempotency_key = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("step_idempotency_key:")
            ),
            "",
        )
        workflow_fingerprint = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("workflow_fingerprint:")
            ),
            "",
        )
        step_fingerprint = next(
            (
                item.split(":", 1)[1]
                for item in preconditions
                if item.startswith("step_definition_fingerprint:")
            ),
            "",
        )
        if not idempotency_key or not workflow_fingerprint or not step_fingerprint:
            raise ExecutionGatewayError(
                "Nested child lacks idempotency/version preconditions",
                code="execution_nested_preconditions_missing",
            )

        claim = context.services.get("_execution_claim")
        claim_store = context.services.get("_execution_claim_store")
        if claim_store is None:
            claim_store = self.claim_store_for(context.manager)
        try:
            # Normalize cross-import identity; the claim store revalidates it.
            claim = coerce_execution_claim(claim)
        except ValueError as exc:
            raise ExecutionGatewayError(
                str(exc), code="execution_nested_claim_missing"
            ) from exc
        try:
            expected_resource = execution_resource_key(
                child_request.effect_id,
                child_request.target,
                child_request.arguments,
                context.manager,
                session_id=child_request.session_id,
            )
        except (OSError, ValueError) as exc:
            raise ExecutionGatewayError(
                "Nested child resource could not be canonicalized",
                code="execution_nested_claim_resource_invalid",
            ) from exc
        if (
            claim.operation_id != idempotency_key
            or claim.resource_key != expected_resource
            or claim.owner_id != parent_request.request_id
            or f"execution_claim_id:{claim.claim_id}" not in child_request.preconditions
            or f"execution_fencing_token:{claim.fencing_token}" not in child_request.preconditions
        ):
            raise ExecutionGatewayError(
                "Execution claim does not bind to this child operation and resource",
                code="execution_nested_claim_mismatch",
            )

        descriptor = next(
            (
                item
                for item in child_effects
                if isinstance(item, dict)
                and str(item.get("step_id") or "") == step_id
                and str(item.get("effect_id") or "") == child_request.effect_id
            ),
            None,
        )
        if not isinstance(descriptor, dict):
            raise ExecutionGatewayError(
                "Nested child effect is not declared by the parent plan",
                code="execution_nested_child_undeclared",
            )
        if str(descriptor.get("target_digest") or "") != child_request.target_digest:
            raise ExecutionGatewayError(
                "Nested child target differs from the prepared plan",
                code="execution_nested_target_mismatch",
            )
        if str(descriptor.get("arguments_digest") or "") != child_request.arguments_digest:
            raise ExecutionGatewayError(
                "Nested child arguments differ from the prepared plan",
                code="execution_nested_arguments_mismatch",
            )
        if str(descriptor.get("scope") or "") != child_request.scope:
            raise ExecutionGatewayError(
                "Nested child scope differs from the prepared plan",
                code="execution_nested_scope_mismatch",
            )
        if str(descriptor.get("step_definition_fingerprint") or "") != step_fingerprint:
            raise ExecutionGatewayError(
                "Nested child step definition is stale",
                code="execution_nested_step_definition_stale",
            )
        if not idempotency_key.startswith(str(descriptor.get("step_idempotency_key_prefix") or "")):
            raise ExecutionGatewayError(
                "Nested child idempotency key is outside the prepared step",
                code="execution_nested_idempotency_mismatch",
            )
        if workflow_fingerprint != str(parent_target.get("workflow_fingerprint") or ""):
            raise ExecutionGatewayError(
                "Nested child workflow fingerprint is stale",
                code="execution_nested_workflow_stale",
            )

        parent_effect = REGISTRY.get(parent_request.effect_id)
        child_effect = REGISTRY.get(child_request.effect_id)
        allowed_risk_rank = parent_effect.risk_rank
        if parent_effect.authorization_mode == "inherit_max_child":
            try:
                allowed_risk_rank = max(
                    [allowed_risk_rank]
                    + [
                        REGISTRY.get(str(item.get("effect_id") or "")).risk_rank
                        for item in child_effects
                        if isinstance(item, dict)
                    ]
                )
            except Exception as exc:
                raise ExecutionGatewayError(
                    "Parent compound request declares an unknown child effect",
                    code="execution_nested_child_effect_invalid",
                ) from exc
        if child_effect.risk_rank > allowed_risk_rank:
            raise ExecutionGatewayError(
                "Nested child effect exceeds the parent plan risk boundary",
                code="execution_nested_risk_exceeded",
            )
        if child_request.policy_version != parent_request.policy_version or child_request.policy_version != REGISTRY.digest:
            raise ExecutionGatewayError(
                "Nested child policy is stale",
                code="execution_nested_policy_stale",
            )

        adapter = self.adapters.resolve(child_request.effect_id)
        trusted_services = dict(context.services)
        trusted_services["_parent_request"] = parent_request
        nested_context = ExecutionContext(manager=context.manager, services=trusted_services)
        try:
            result = claim_store.execute_if_valid(
                claim,
                lambda: adapter.execute(child_request, nested_context),
            )
        except ExecutionClaimError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc
        return result, authorization


__all__ = [
    "CapabilityRuntimeEffectAdapter",
    "ContextAttachEffectAdapter",
    "CredentialWriteEffectAdapter",
    "DelegationGrantEffectAdapter",
    "EffectAdapter",
    "EffectAdapterRegistry",
    "ExecutionContext",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "FilesystemEffectAdapter",
    "FilesystemReadEffectAdapter",
    "ProjectWriteEffectAdapter",
    "StateDeleteEffectAdapter",
    "PlanRuntimeEffectAdapter",
    "ProcessExecutionEffectAdapter",
    "GatewayHTTPResponse",
    "NetworkReadEffectAdapter",
    "ServerStateEffectAdapter",
    "SessionWorkspaceMirrorEffectAdapter",
    "WorkspaceBindEffectAdapter",
    "WorkspaceMirrorSyncEffectAdapter",
    "build_default_effect_adapter_registry",
]

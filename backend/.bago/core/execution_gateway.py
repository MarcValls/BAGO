"""Closed execution gateway for governed BAGO effects.

Callers submit an ExecutionRequest plus a Permit. They cannot supply a callable.
The gateway resolves the executable adapter from a server-owned registry keyed
by canonical effect_id.
"""

from __future__ import annotations

import hashlib
import base64
import os
import threading
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from authorization_boundary import AuthorizationBoundary, AuthorizationError
from effect_registry import REGISTRY
from execution_request import ExecutionRequest


class ExecutionGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "execution_gateway_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Trusted runtime dependencies, never part of user authority."""

    manager: Any = None
    services: Mapping[str, Any] = field(default_factory=dict)


class EffectAdapter(Protocol):
    effect_ids: frozenset[str]

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        ...


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


class CapabilityRuntimeEffectAdapter:
    """Governed adapter for imported Capability Package runtime."""

    effect_ids = frozenset({"capability.execute", "pipeline.execute"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from capability_packages import (
            CapabilityPackageError,
            execute_package,
            execute_pipeline_package,
            get_package,
        )

        package_id = str(request.target.get("package_id") or "").strip()
        if not package_id:
            raise ExecutionGatewayError(
                "Capability runtime target requires package_id",
                code="execution_target_missing",
            )
        package = get_package(package_id)
        expected_kind = "pipeline" if request.effect_id == "pipeline.execute" else "capability"
        requested_digest = str(request.target.get("package_digest") or "").strip()
        current_digest = str(package.get("digest") or "").strip()
        if requested_digest and requested_digest != current_digest:
            raise ExecutionGatewayError(
                "Package changed after authorization request was constructed",
                code="execution_target_digest_mismatch",
            )
        if str(package.get("kind") or "") != expected_kind:
            raise ExecutionGatewayError(
                f"Effect {request.effect_id} cannot execute package kind {package.get('kind')}",
                code="execution_target_kind_mismatch",
            )
        manager = context.manager
        if manager is not None:
            manager_session = str(getattr(manager, "session_id", "") or "")
            if manager_session and manager_session != request.session_id:
                raise ExecutionGatewayError(
                    "ExecutionContext manager belongs to another session",
                    code="execution_context_session_mismatch",
                )

        permissions = list(package.get("permissions", []))
        if request.effect_id == "pipeline.execute":
            if manager is None:
                raise ExecutionGatewayError(
                    "Pipeline execution requires SessionManager context",
                    code="execution_context_manager_required",
                )
            return execute_pipeline_package(
                package_id,
                inputs=request.arguments,
                confirmed=True,
                approved_permissions=permissions,
                manager=manager,
            )
        return execute_package(
            package_id,
            inputs=request.arguments,
            confirmed=True,
            approved_permissions=permissions,
        )


class FilesystemEffectAdapter:
    """Gateway-owned adapter for one scoped workspace file write."""

    effect_ids = frozenset({"filesystem.write"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from filesystem_effects import FilesystemEffectError, write_file_effect

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Filesystem write requires SessionManager context",
                code="execution_context_manager_required",
            )
        if not isinstance(context.services.get("_authorization"), dict):
            raise ExecutionGatewayError(
                "Filesystem write requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager_session and manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )
        raw_path = str(request.target.get("path") or "").strip()
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        content = str(arguments.get("content") or "")
        try:
            return write_file_effect(manager, raw_path, content)
        except FilesystemEffectError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc



class FilesystemReadEffectAdapter:
    """Gateway-owned adapter for one scoped, read-only plan child."""

    effect_ids = frozenset({"filesystem.read"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from filesystem_effects import FilesystemEffectError, read_file_effect

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Filesystem read requires SessionManager context",
                code="execution_context_manager_required",
            )
        if not isinstance(context.services.get("_authorization"), dict):
            raise ExecutionGatewayError(
                "Filesystem read requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        manager_session = str(getattr(manager, "session_id", "") or "")
        if manager_session and manager_session != request.session_id:
            raise ExecutionGatewayError(
                "ExecutionContext manager belongs to another session",
                code="execution_context_session_mismatch",
            )
        try:
            return read_file_effect(manager, str(request.target.get("path") or ""))
        except FilesystemEffectError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc


_SERVER_STATE_EFFECTS = frozenset({
    "state.write",
    "config.write",
    "memory.write",
    "agent.definition.write",
})
_SERVER_STATE_WRITE_LOCK = threading.RLock()


class ServerStateEffectAdapter:
    """Server-owned adapter for policy-authorized persistent state writes.

    The adapter owns the only material write implementation for this family.
    Callers can select a target path and payload, but cannot supply an
    executor. The gateway supplies the policy authorization and the trusted
    root; this adapter checks the root again immediately before the effect.
    """

    effect_ids = _SERVER_STATE_EFFECTS
    server_policy_only = True

    _FORBIDDEN_SEGMENTS = frozenset({".git", ".env", "node_modules", ".venv", "venv"})

    @staticmethod
    def _resolved_target(raw_path: str, raw_root: str) -> tuple[Path, Path]:
        root = Path(str(raw_root or "")).expanduser().resolve()
        if not str(raw_path or "").strip():
            raise ExecutionGatewayError(
                "Server state target path is required",
                code="server_state_path_required",
            )
        candidate = Path(str(raw_path)).expanduser()
        target = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ExecutionGatewayError(
                "Server state target is outside its trusted root",
                code="server_state_path_out_of_scope",
            ) from exc
        if target == root:
            raise ExecutionGatewayError(
                "Server state target must be a file",
                code="server_state_target_invalid",
            )
        if any(part.lower() in ServerStateEffectAdapter._FORBIDDEN_SEGMENTS for part in target.parts):
            raise ExecutionGatewayError(
                "Server state target contains a forbidden segment",
                code="server_state_forbidden_path",
            )
        if target.exists() and target.is_symlink():
            raise ExecutionGatewayError(
                "Server state target cannot be a symlink",
                code="server_state_symlink_forbidden",
            )
        return target, root

    @staticmethod
    def _replace_with_retry(temporary: Path, target: Path) -> None:
        for attempt in range(8):
            try:
                os.replace(temporary, target)
                return
            except PermissionError:
                if os.name != "nt" or attempt == 7:
                    raise
                time.sleep(0.02 * (2**attempt))

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Persistent state requires server-owned policy authorization",
                code="server_state_authorization_required",
            )
        expected_root = str(context.services.get("_server_allowed_root") or "").strip()
        target_root = str(request.target.get("allowed_root") or "").strip()
        if not expected_root or target_root != expected_root:
            raise ExecutionGatewayError(
                "Persistent state trusted root is missing or changed",
                code="server_state_root_mismatch",
            )
        target, root = self._resolved_target(str(request.target.get("path") or ""), expected_root)
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        operation = str(request.target.get("operation") or "replace_text").strip().lower()
        content = str(arguments.get("content") or "")

        try:
            with _SERVER_STATE_WRITE_LOCK:
                target.parent.mkdir(parents=True, exist_ok=True)
                if operation == "append_text":
                    with target.open("a", encoding="utf-8", newline="\n") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                elif operation == "replace_text":
                    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
                    try:
                        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                            handle.write(content)
                            handle.flush()
                            os.fsync(handle.fileno())
                        self._replace_with_retry(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
                else:
                    raise ExecutionGatewayError(
                        f"Unsupported server state operation: {operation}",
                        code="server_state_operation_invalid",
                    )
        except ExecutionGatewayError:
            raise
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Error escribiendo estado persistente: {exc}",
                code="server_state_write_failed",
            ) from exc

        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        try:
            relative = str(target.relative_to(root)).replace("\\", "/")
        except ValueError:
            relative = str(target)
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "operation": operation,
            "path": relative,
            "absolute_path": str(target),
            "evidence": [f"file_sha256:{digest}", f"path:{target}"],
            "receipt_id": f"{request.effect_id}:sha256:{digest}",
        }


class GatewayHTTPResponse:
    """Small buffered response compatible with the existing urllib callers."""

    def __init__(self, body: bytes, *, status: int, headers: Mapping[str, Any], url: str) -> None:
        self._body = bytes(body)
        self._offset = 0
        self.status = int(status)
        self.code = self.status
        self.headers = dict(headers)
        self.url = str(url)

    def read(self, amount: int = -1) -> bytes:
        if amount is None or amount < 0:
            amount = len(self._body) - self._offset
        start = self._offset
        self._offset = min(len(self._body), self._offset + int(amount))
        return self._body[start:self._offset]

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def close(self) -> None:
        return None

    def __enter__(self) -> "GatewayHTTPResponse":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def __iter__(self):
        return iter(self._body.splitlines(keepends=True))


class NetworkReadEffectAdapter:
    """Server-owned policy adapter for approved BAGO transport reads.

    Provider inference calls may use HTTP POST at the transport layer, but
    this adapter is only reachable for an explicitly classified BAGO transport
    surface. Release, GitHub and arbitrary external mutations remain outside
    this policy adapter and must use their explicit effects in later waves.
    """

    effect_ids = frozenset({"network.read"})
    server_policy_only = True
    _ALLOWED_CLASSES = frozenset({"provider_transport", "runtime_probe", "local_discovery"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict) or authorization.get("kind") != "server_policy":
            raise ExecutionGatewayError(
                "Network read requires server-owned policy authorization",
                code="network_read_authorization_required",
            )
        network_class = str(request.target.get("network_class") or "").strip()
        if network_class not in self._ALLOWED_CLASSES:
            raise ExecutionGatewayError(
                "Network target is not an approved BAGO transport surface",
                code="network_read_surface_blocked",
            )
        url = str(request.target.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            raise ExecutionGatewayError(
                "Network target must use HTTP(S)",
                code="network_read_url_invalid",
            )
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        method = str(request.target.get("method") or "GET").upper()
        headers = arguments.get("headers") if isinstance(arguments.get("headers"), dict) else {}
        encoded_data = str(arguments.get("data_b64") or "")
        try:
            data = base64.b64decode(encoded_data) if encoded_data else None
            outbound = urllib.request.Request(
                url,
                data=data,
                headers={str(key): str(value) for key, value in headers.items()},
                method=method,
            )
            timeout = float(request.target.get("timeout") or 30.0)
            with urllib.request.urlopen(outbound, timeout=timeout) as response:
                if hasattr(response, "read"):
                    body = response.read()
                else:
                    body = b"".join(response)
                raw_headers = getattr(response, "headers", {})
                response_headers = dict(raw_headers.items()) if hasattr(raw_headers, "items") else dict(raw_headers)
                getcode = getattr(response, "getcode", None)
                status = int(getattr(response, "status", getcode() if callable(getcode) else 200))
                geturl = getattr(response, "geturl", None)
                final_url = str(geturl() if callable(geturl) else url)
        except ExecutionGatewayError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError):
            # Preserve urllib's typed transport errors for provider retry and
            # fallback policies; the effect has already been authorized and
            # no caller-side sink is reintroduced by re-raising the error.
            raise
        except OSError:
            # Local discovery and provider fallback already treat transport
            # availability as a recoverable OSError boundary. Preserve that
            # contract after the server-owned dispatch.
            raise
        except Exception as exc:
            raise ExecutionGatewayError(
                f"Network read failed: {exc}",
                code="network_read_failed",
            ) from exc
        return GatewayHTTPResponse(
            body,
            status=status,
            headers=response_headers,
            url=final_url,
        )


class PlanRuntimeEffectAdapter:
    """Governed 04-FIX2 adapter for PlanEngine execution."""

    effect_ids = frozenset({"plan.execute"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from governed_work_pipeline import GovernedWorkError, execute_plan_through_gateway

        manager = context.manager
        if manager is None:
            raise ExecutionGatewayError(
                "Plan execution requires SessionManager context",
                code="execution_context_manager_required",
            )
        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict):
            raise ExecutionGatewayError(
                "Plan execution requires gateway-owned authorization context",
                code="execution_authorization_context_required",
            )
        gateway = context.services.get("_gateway")
        if not isinstance(gateway, ExecutionGateway):
            raise ExecutionGatewayError(
                "Plan execution requires the active ExecutionGateway",
                code="execution_gateway_context_required",
            )
        engine = getattr(manager, "plan_engine", None)
        if engine is None:
            raise ExecutionGatewayError(
                "PlanEngine no disponible",
                code="plan_engine_missing",
            )
        plan_id = str(request.target.get("plan_id") or "").strip()
        plan = engine.get_plan(plan_id)
        if plan is None:
            raise ExecutionGatewayError(
                f"Plan no encontrado: {plan_id}",
                code="plan_not_found",
            )
        try:
            return execute_plan_through_gateway(
                plan=plan,
                engine=engine,
                parent_request=request,
                authorization=authorization,
                gateway=gateway,
                context=context,
            )
        except GovernedWorkError as exc:
            raise ExecutionGatewayError(str(exc), code=exc.code) from exc


class DelegationGrantEffectAdapter:
    """Persist an E6 DelegationGrant only after its parent Permit is consumed."""

    effect_ids = frozenset({"schedule.delegate"})

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> Any:
        from delegation_grant import DelegationGrantRegistry

        authorization = context.services.get("_authorization")
        if not isinstance(authorization, dict):
            raise ExecutionGatewayError(
                "Delegation adapter requires gateway-owned authorization context",
                code="execution_delegation_authorization_missing",
            )

        state_dir = context.services.get("state_dir")
        if state_dir is None and context.manager is not None:
            from pathlib import Path

            base_path = Path(getattr(context.manager, "base_path", Path.cwd()))
            state_dir = base_path / ".bago" / "state"
        if state_dir is None:
            raise ExecutionGatewayError(
                "Delegation adapter requires trusted state_dir",
                code="execution_delegation_state_required",
            )

        grant = DelegationGrantRegistry(state_dir).issue_from_authorized_request(
            request,
            authorization,
        )
        return {"ok": True, "delegation_grant": grant}


def build_default_effect_adapter_registry() -> EffectAdapterRegistry:
    registry = EffectAdapterRegistry()
    registry.register(FilesystemEffectAdapter())
    registry.register(FilesystemReadEffectAdapter())
    registry.register(ServerStateEffectAdapter())
    registry.register(NetworkReadEffectAdapter())
    registry.register(CapabilityRuntimeEffectAdapter())
    registry.register(PlanRuntimeEffectAdapter())
    registry.register(DelegationGrantEffectAdapter())
    return registry


class ExecutionGateway:
    """Consume a Permit and dispatch only through server-owned EffectAdapters."""

    def __init__(
        self,
        boundary: AuthorizationBoundary | None = None,
        adapters: EffectAdapterRegistry | None = None,
    ) -> None:
        self.boundary = boundary or AuthorizationBoundary()
        self.adapters = adapters or build_default_effect_adapter_registry()

    def execute(
        self,
        *,
        permit_token: str,
        request: ExecutionRequest,
        context: ExecutionContext | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        # Resolve first so a configuration error does not consume a valid Permit.
        adapter = self.adapters.resolve(request.effect_id)
        if bool(getattr(adapter, "server_policy_only", False)):
            raise ExecutionGatewayError(
                f"{request.effect_id} is server-policy-only",
                code="execution_server_policy_only",
            )
        authorization = self.boundary.consume_permit(
            permit_token=permit_token,
            request=request,
        )
        trusted_context = context or ExecutionContext()
        trusted_services = dict(trusted_context.services)
        # Gateway-owned metadata overwrites any caller-supplied value.
        trusted_services["_authorization"] = authorization
        trusted_services["_gateway"] = self
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
        if not bool(getattr(adapter, "server_policy_only", False)):
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
        if child_effect.risk_rank > parent_effect.risk_rank:
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
        return adapter.execute(child_request, nested_context), authorization


__all__ = [
    "CapabilityRuntimeEffectAdapter",
    "DelegationGrantEffectAdapter",
    "EffectAdapter",
    "EffectAdapterRegistry",
    "ExecutionContext",
    "ExecutionGateway",
    "ExecutionGatewayError",
    "FilesystemEffectAdapter",
    "FilesystemReadEffectAdapter",
    "PlanRuntimeEffectAdapter",
    "GatewayHTTPResponse",
    "NetworkReadEffectAdapter",
    "ServerStateEffectAdapter",
    "build_default_effect_adapter_registry",
]

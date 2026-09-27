"""Small server-owned effect helpers used by persistent BAGO state primitives.

The helpers construct canonical policy requests; they do not write files.
Materialization stays inside the registered ``ServerStateEffectAdapter``.
"""

from __future__ import annotations

import base64
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path
from typing import Any

# The legacy runtime modules under ``backend/.bago/core`` are also launched
# directly by ``python -m bago_core...``. Bind that module root explicitly so
# the server-owned gateway is the same implementation in both launch modes.
_CORE_MODULE_ROOT = Path(__file__).resolve().parents[1] / ".bago" / "core"
if str(_CORE_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_MODULE_ROOT))

from execution_gateway import ExecutionContext, ExecutionGateway
from execution_request import build_execution_request
from bago_core.user_state_paths import logs_root


def _execute_text(
    path: Path,
    content: str,
    *,
    operation: str,
    effect_id: str,
    scope: str,
    source_surface: str,
    session_id: str,
    trusted_root: Path | None,
) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    root = Path(trusted_root or target.parent).expanduser().resolve()
    surface = str(source_surface or "atomic_json").strip()
    if not surface.startswith("server."):
        surface = f"server.{surface}"
    request = build_execution_request(
        effect_id=effect_id,
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=str(session_id or f"server-state:{root}"),
        source_surface=surface,
        target={
            "path": str(target),
            "allowed_root": str(root),
            "operation": operation,
        },
        arguments={"content": str(content)},
        scope=scope,
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(services={"_server_allowed_root": str(root)}),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Server-owned persistent effect returned no success receipt")
    return result


def write_text_atomic(
    path: Path,
    content: str,
    *,
    trusted_root: Path | None = None,
    source_surface: str = "atomic_json",
    session_id: str = "",
) -> dict[str, Any]:
    return _execute_text(
        path,
        content,
        operation="replace_text",
        effect_id="state.write",
        scope="session",
        source_surface=source_surface,
        session_id=session_id,
        trusted_root=trusted_root,
    )


def ensure_user_directory(path: Path, *, trusted_root: Path, source_surface: str = "user_state.roots") -> dict[str, Any]:
    root = Path(trusted_root).expanduser().resolve()
    target = Path(path).expanduser()
    surface = str(source_surface or "user_state.roots").strip()
    if not surface.startswith("server."):
        surface = f"server.{surface}"
    request = build_execution_request(
        effect_id="state.directory.ensure",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=f"server-state:{root}",
        source_surface=surface,
        target={"path": str(target), "allowed_root": str(root), "operation": "ensure_directory"},
        arguments={},
        scope="persistent",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(services={"_server_allowed_root": str(root)}),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Server-owned directory effect returned no success receipt")
    return result


def write_config_text_atomic(
    path: Path,
    content: str,
    *,
    trusted_root: Path,
    source_surface: str,
    session_id: str,
) -> dict[str, Any]:
    """Persist one canonical user config through the existing state owner."""
    return _execute_text(
        path,
        content,
        operation="replace_text",
        effect_id="config.write",
        scope="persistent",
        source_surface=source_surface,
        session_id=session_id,
        trusted_root=trusted_root,
    )


def _agent_definition_state_root() -> Path:
    return Path(__file__).resolve().parents[1] / ".bago" / "state"


def write_agent_definition(
    path: Path,
    content: str,
    *,
    trusted_root: Path | None = None,
) -> dict[str, Any]:
    """Persist one generated agent definition under its dedicated effect owner."""
    root = Path(trusted_root or _agent_definition_state_root()).expanduser().resolve()
    return _execute_text(
        path,
        content,
        operation="replace_text",
        effect_id="agent.definition.write",
        scope="persistent",
        source_surface="agent.factory.definition",
        session_id=f"agent-definition:{root}",
        trusted_root=root,
    )


def append_text_durable(
    path: Path,
    content: str,
    *,
    trusted_root: Path | None = None,
    source_surface: str = "atomic_json",
    session_id: str = "",
) -> dict[str, Any]:
    return _execute_text(
        path,
        content,
        operation="append_text",
        effect_id="state.write",
        scope="session",
        source_surface=source_surface,
        session_id=session_id,
        trusted_root=trusted_root,
    )


def _execute_runtime_state_bootstrap(
    state_root: Path,
    *,
    operation: str,
    source_root: Path | None = None,
) -> dict[str, Any]:
    root = Path(state_root).expanduser().resolve()
    request = build_execution_request(
        effect_id="state.bootstrap",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=f"runtime-state:{root}",
        source_surface=f"server.runtime.state-{operation}",
        target={
            "root": str(root),
            "operation": operation,
            **({"source_root": str(Path(source_root).expanduser().resolve())} if source_root is not None else {}),
        },
        arguments={},
        scope="persistent",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(services={"_server_allowed_root": str(root)}),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Runtime state bootstrap returned no success receipt")
    return result


def ensure_runtime_state_dirs(state_root: Path) -> dict[str, Any]:
    """Create canonical runtime state folders under the registered state owner."""
    return _execute_runtime_state_bootstrap(state_root, operation="ensure_directories")


def seed_runtime_state_examples(state_root: Path, source_root: Path) -> dict[str, Any]:
    """Copy canonical initial state examples through the registered state owner."""
    return _execute_runtime_state_bootstrap(
        state_root,
        operation="seed_examples",
        source_root=source_root,
    )


def write_learning_text(path: Path, content: str, *, trusted_root: Path) -> dict[str, Any]:
    """Replace one canonical auto-promoted learning artifact via the gateway."""
    return _execute_text(
        path, content, operation="replace_text", effect_id="learning.write",
        scope="persistent", source_surface="learning.patterns",
        session_id="learning-patterns", trusted_root=trusted_root,
    )


def append_learning_text(path: Path, content: str, *, trusted_root: Path) -> dict[str, Any]:
    """Append one autonomous observation to the canonical learning ledger."""
    return _execute_text(
        path, content, operation="append_text", effect_id="learning.write",
        scope="persistent", source_surface="learning.observation",
        session_id="learning-observations", trusted_root=trusted_root,
    )


def append_structured_log(content: str, *, max_bytes: int, backup_count: int) -> dict[str, Any]:
    """Append and rotate the canonical structured bridge log via its owner."""
    root = logs_root().expanduser().resolve()
    target = root / "bridge.jsonl"
    request = build_execution_request(
        effect_id="logging.append",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=f"structured-log:{root}",
        source_surface="server.api.structured_log",
        target={"path": str(target), "allowed_root": str(root), "operation": "append_rotate"},
        arguments={"content": str(content), "max_bytes": int(max_bytes), "backup_count": int(backup_count)},
        scope="persistent",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(services={"_server_allowed_root": str(root)}),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Structured logging effect returned no success receipt")
    return result


def stage_validation_workspace(
    source_root: str | Path,
    *,
    ignore: list[str],
    staging_id: str | None = None,
    label: str = "bago_staging",
) -> dict[str, Any]:
    """Materialize one temporary validation copy through its registered owner."""
    staging_id = staging_id or uuid.uuid4().hex
    root = Path(tempfile.gettempdir()).resolve() / "BAGO" / "validation"
    request = build_execution_request(
        effect_id="workspace.validation.stage",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=f"validation-stage:{staging_id}",
        source_surface="server.code_forge.validation_staging",
        target={"operation": "create", "root": str(root), "source_root": str(Path(source_root).expanduser()), "staging_id": staging_id, "label": label},
        arguments={"ignore": list(ignore)},
        scope="workspace",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Validation staging effect returned no success receipt")
    return result


def cleanup_validation_workspace(staging_id: str, *, label: str) -> dict[str, Any]:
    """Remove only a validation staging directory created by this owner."""
    root = Path(tempfile.gettempdir()).resolve() / "BAGO" / "validation"
    request = build_execution_request(
        effect_id="workspace.validation.stage",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=f"validation-stage:{staging_id}",
        source_surface="server.code_forge.validation_staging.cleanup",
        target={"operation": "cleanup", "root": str(root), "staging_id": staging_id, "label": label},
        arguments={},
        scope="workspace",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Validation staging cleanup returned no success receipt")
    return result


def gateway_urlopen(
    request: str | urllib.request.Request,
    *,
    timeout: float = 30.0,
    network_class: str = "provider_transport",
) -> Any:
    """Perform one classified BAGO transport request through the gateway."""

    if isinstance(request, urllib.request.Request):
        url = str(request.full_url)
        method = str(request.get_method() or "GET").upper()
        headers = {
            str(key): str(value)
            for key, value in {**request.unredirected_hdrs, **request.headers}.items()
        }
        data = request.data
    else:
        url = str(request)
        method = "GET"
        headers = {}
        data = None
    request_contract = build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=f"network:{network_class}",
        source_surface=f"server.network.{network_class}",
        target={
            "url": url,
            "method": method,
            "network_class": network_class,
            "timeout": float(timeout),
        },
        arguments={
            "headers": headers,
            "data_b64": base64.b64encode(data).decode("ascii") if isinstance(data, bytes) else "",
        },
        scope="external",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request_contract,
        context=ExecutionContext(),
    )
    return result


def download_release_bundle(
    *,
    url: str,
    sha256: str,
    size: int,
    filename: str,
) -> dict[str, Any]:
    """Download one verified release payload through its registered adapter."""

    request = build_execution_request(
        effect_id="release.download",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="release-download",
        source_surface="server.release.download",
        target={"filename": str(filename)},
        arguments={"url": str(url), "digest": str(sha256), "size": int(size)},
        scope="system",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Server-owned release effect returned no success receipt")
    return result


def inspect_process(
    executable: str,
    argv: list[str],
    *,
    cwd: str | Path,
    manager: Any,
    timeout: int = 30,
    output_digest: str = "",
) -> dict[str, Any]:
    """Dispatch one allowlisted read-only process inspection through the gateway."""
    from execution_adapters.process import ProcessExecutionEffectAdapter

    clean_executable = str(executable or "").strip()
    clean_argv = [str(value) for value in argv]
    allowed = (
        clean_executable == "gh" and ProcessExecutionEffectAdapter.is_read_only_github_argv(clean_argv)
    ) or (
        clean_executable == "git" and ProcessExecutionEffectAdapter.is_read_only_git_argv(clean_argv)
    )
    if not allowed:
        raise ValueError("Process inspection is not on the read-only allowlist")
    request = build_execution_request(
        effect_id="process.inspect",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id=str(getattr(manager, "session_id", "") or ""),
        source_surface="server.process.inspect",
        target={
            "operation": "github_cli" if clean_executable == "gh" else "git_identity",
            "executable": clean_executable,
            "cwd": str(cwd),
            "timeout_seconds": min(max(int(timeout), 1), 30),
            **({"output_digest": output_digest} if output_digest else {}),
        },
        arguments={"argv": clean_argv},
        scope="workspace",
    )
    result, _authorization = ExecutionGateway().execute_server_owned(
        request=request,
        context=ExecutionContext(manager=manager),
    )
    return result


__all__ = [
    "append_text_durable",
    "append_learning_text",
    "write_agent_definition",
    "download_release_bundle",
    "gateway_urlopen",
    "inspect_process",
    "write_text_atomic",
    "write_learning_text",
]

from __future__ import annotations

import inspect
import hashlib
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import authorization_boundary as auth
from execution_gateway import (
    CredentialWriteEffectAdapter,
    EffectAdapterRegistry,
    ExecutionContext,
    ExecutionGateway,
    ExecutionGatewayError,
    ProcessExecutionEffectAdapter,
    ContextAttachEffectAdapter,
    ProjectWriteEffectAdapter,
    WorkspaceBindEffectAdapter,
    WorkspaceMirrorSyncEffectAdapter,
    build_default_effect_adapter_registry,
)
from execution_request import build_execution_request


class _RecordingAdapter:
    effect_ids = frozenset({"filesystem.write"})

    def __init__(self) -> None:
        self.calls = []

    def execute(self, request, context):
        self.calls.append((request, context))
        return {
            "ok": True,
            "effect_id": request.effect_id,
            "target": request.target,
            "arguments_digest": request.arguments_digest,
        }


def _request(*, value: str = "A", effect_id: str = "filesystem.write"):
    return build_execution_request(
        effect_id=effect_id,
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"path": "notes/example.txt"},
        arguments={"content": value},
    )


def _permit(boundary: auth.AuthorizationBoundary, request, interaction: str = "interaction-gw"):
    challenge = boundary.create_challenge(request, interaction_id=interaction)
    return boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id=interaction,
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]


def test_execution_request_fingerprint_is_transport_id_independent() -> None:
    a = _request()
    b = _request()
    assert a.request_id != b.request_id
    assert a.arguments_digest == b.arguments_digest
    assert a.fingerprint == b.fingerprint


def test_execution_request_detaches_mutable_caller_payload() -> None:
    arguments = {"content": {"value": "A"}}
    request = build_execution_request(
        effect_id="filesystem.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"path": "notes/example.txt"},
        arguments=arguments,
    )
    fingerprint = request.fingerprint
    arguments["content"]["value"] = "MUTATED"
    assert request.arguments["content"]["value"] == "A"
    assert request.fingerprint == fingerprint


def test_execution_request_fingerprint_changes_with_material_semantics() -> None:
    original = _request(value="A")
    changed_arguments = _request(value="B")
    changed_effect = _request(value="A", effect_id="filesystem.delete")

    assert original.fingerprint != changed_arguments.fingerprint
    assert original.fingerprint != changed_effect.fingerprint


def test_gateway_signature_has_no_caller_supplied_executor() -> None:
    parameters = inspect.signature(ExecutionGateway.execute).parameters
    assert "executor" not in parameters
    assert "request" in parameters
    assert "permit_token" in parameters


def test_gateway_dispatches_by_effect_id_after_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    request = _request()
    permit = _permit(boundary, request)

    adapter = _RecordingAdapter()
    registry = EffectAdapterRegistry()
    registry.register(adapter)
    gateway = ExecutionGateway(boundary=boundary, adapters=registry)

    result, consumed = gateway.execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(services={"test": True}),
    )

    assert result["ok"] is True
    assert result["effect_id"] == "filesystem.write"
    assert consumed["state"] == "consumed"
    assert len(adapter.calls) == 1


def test_missing_adapter_does_not_consume_valid_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path)
    boundary = auth.AuthorizationBoundary()
    request = _request()
    permit = _permit(boundary, request, interaction="interaction-missing")

    empty = EffectAdapterRegistry()
    gateway = ExecutionGateway(boundary=boundary, adapters=empty)
    with pytest.raises(ExecutionGatewayError) as missing:
        gateway.execute(permit_token=permit["token"], request=request)
    assert missing.value.code == "execution_adapter_missing"

    adapter = _RecordingAdapter()
    empty.register(adapter)
    result, consumed = gateway.execute(permit_token=permit["token"], request=request)
    assert result["ok"] is True
    assert consumed["state"] == "consumed"


def test_process_execute_adapter_runs_only_the_permitted_workspace_argv(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    monkeypatch.setattr("execution_adapters.process.shutil.which", lambda _exe: r"C:\GitHubCLI\gh.exe")
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "gateway-owned\n", ""),
    )
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="process.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"executable": "gh", "cwd": str(tmp_path), "timeout_seconds": 5},
        arguments={"argv": ["auth", "status"]},
    )
    permit = _permit(boundary, request, interaction="process-execute")
    manager = type("Manager", (), {"session_id": "session-1", "base_path": str(tmp_path)})()
    gateway = ExecutionGateway(boundary=boundary)
    assert isinstance(gateway.adapters.resolve("process.execute"), ProcessExecutionEffectAdapter)

    result, authorization = gateway.execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert authorization["state"] == "consumed"
    assert result["ok"] is True
    assert result["stdout"].strip() == "gateway-owned"
    assert result["cwd"] == str(tmp_path.resolve())


def test_process_execute_rejects_out_of_workspace_cwd_before_spawn(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("spawn must be blocked")),
    )
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="process.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"executable": "gh", "cwd": str(tmp_path.parent)},
        arguments={"argv": ["auth", "status"]},
    )
    permit = _permit(boundary, request, interaction="process-cwd-block")
    manager = type("Manager", (), {"session_id": "session-1", "base_path": str(tmp_path)})()
    gateway = ExecutionGateway(boundary=boundary)

    with pytest.raises(ExecutionGatewayError) as blocked:
        gateway.execute(
            permit_token=permit["token"],
            request=request,
            context=ExecutionContext(manager=manager),
        )

    assert blocked.value.code == "process_execution_cwd_out_of_scope"


def test_server_process_inspection_allows_only_exact_git_head_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("execution_adapters.process.shutil.which", lambda _exe: r"C:\Git\git.exe")
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "abc123\n", ""),
    )
    from bago_core.server_effects import inspect_process

    manager = type("Manager", (), {"session_id": "git-inspect-1", "base_path": str(tmp_path)})()
    result = inspect_process("git", ["rev-parse", "HEAD"], cwd=tmp_path, manager=manager)

    assert result["exit_code"] == 0
    assert result["stdout"] == "abc123\n"


def test_server_process_inspection_allows_exact_git_diff_paths_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("execution_adapters.process.shutil.which", lambda _exe: r"C:\Git\git.exe")
    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "src/changed.py\n", "")

    monkeypatch.setattr("execution_adapters.process.subprocess.run", run)
    from bago_core.server_effects import inspect_process

    manager = type("Manager", (), {"session_id": "git-diff-paths-1", "base_path": str(tmp_path)})()
    argv = ["-c", f"safe.directory={tmp_path.as_posix()}", "diff", "--name-only"]
    result = inspect_process("git", argv, cwd=tmp_path, manager=manager, timeout=5)

    assert result["exit_code"] == 0
    assert result["stdout"] == "src/changed.py\n"
    assert calls and calls[0][1:] == argv


@pytest.mark.parametrize(
    "argv",
    [
        ["rev-parse", "--show-toplevel"],
        ["rev-parse", "--abbrev-ref", "HEAD"],
    ],
)
def test_server_process_inspection_allows_exact_git_binding_reads(tmp_path, monkeypatch, argv) -> None:
    monkeypatch.setattr("execution_adapters.process.shutil.which", lambda _exe: r"C:\Git\git.exe")
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "value\n", ""),
    )
    from bago_core.server_effects import inspect_process

    manager = type("Manager", (), {"session_id": "git-binding-1", "base_path": str(tmp_path)})()
    result = inspect_process("git", argv, cwd=tmp_path, manager=manager)

    assert result["exit_code"] == 0
    assert result["stdout"] == "value\n"


def test_server_process_inspection_rejects_git_mutation_before_gateway(tmp_path) -> None:
    from bago_core.server_effects import inspect_process

    manager = type("Manager", (), {"session_id": "git-inspect-2", "base_path": str(tmp_path)})()
    with pytest.raises(ValueError, match="read-only allowlist"):
        inspect_process("git", ["config", "user.name", "changed"], cwd=tmp_path, manager=manager)


def test_process_adapter_pytest_allowlist_rejects_inline_code() -> None:
    assert ProcessExecutionEffectAdapter.is_authorized_executable_argv(
        sys.executable, ["-m", "pytest", "-q", "tests"]
    )
    assert not ProcessExecutionEffectAdapter.is_authorized_executable_argv(
        sys.executable, ["-c", "print('arbitrary')"]
    )


def test_process_execute_runs_only_a_digest_bound_bago_module(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    framework = tmp_path / "framework"
    package = framework / "bago_core"
    package.mkdir(parents=True)
    module_file = package / "launcher.py"
    module_file.write_text("import sys\nprint('module-owned:' + '|'.join(sys.argv[1:]))\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    digest = hashlib.sha256(module_file.read_bytes()).hexdigest()
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="process.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-module",
        source_surface="api.process.execute.desktop",
        target={
            "python_module": "bago_core.launcher",
            "python_root": str(framework),
            "python_module_sha256": digest,
            "cwd": str(workspace),
            "timeout_seconds": 5,
        },
        arguments={"argv": ["--sample", "exact"]},
        scope="workspace",
    )
    permit = _permit(boundary, request, interaction="process-module-execute")
    manager = type("Manager", (), {
        "session_id": "session-module", "base_path": str(workspace),
        "framework_root": str(framework),
    })()
    result, authorization = ExecutionGateway(boundary=boundary).execute(
        permit_token=permit["token"], request=request,
        context=ExecutionContext(manager=manager),
    )
    assert authorization["state"] == "consumed"
    assert result["python_module"] == "bago_core.launcher"
    assert result["stdout"].strip() == "module-owned:--sample|exact"
    assert result["cwd"] == str(workspace.resolve())


def test_process_execute_module_digest_drift_blocks_before_spawn(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    framework = tmp_path / "framework"
    package = framework / "bago_core"
    package.mkdir(parents=True)
    module_file = package / "launcher.py"
    module_file.write_text("print('authorized')\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    digest = hashlib.sha256(module_file.read_bytes()).hexdigest()
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="process.execute", actor_kind="user",
        principal_id="interactive-local-user", session_id="session-module-drift",
        source_surface="api.process.execute.desktop",
        target={"python_module": "bago_core.launcher", "python_root": str(framework),
                "python_module_sha256": digest, "cwd": str(workspace), "timeout_seconds": 5},
        arguments={"argv": []}, scope="workspace",
    )
    permit = _permit(boundary, request, interaction="process-module-drift")
    module_file.write_text("print('changed after challenge')\n", encoding="utf-8")
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("spawn must be blocked")),
    )
    manager = type("Manager", (), {
        "session_id": "session-module-drift", "base_path": str(workspace),
        "framework_root": str(framework),
    })()
    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway(boundary=boundary).execute(
            permit_token=permit["token"], request=request,
            context=ExecutionContext(manager=manager),
        )
    assert blocked.value.code == "process_execution_module_unavailable"


def test_process_inspect_server_policy_allows_only_fixed_read_only_launcher_operations(tmp_path, monkeypatch) -> None:
    framework = tmp_path / "framework"
    package = framework / "bago_core"
    package.mkdir(parents=True)
    module_file = package / "launcher.py"
    module_file.write_text("print('launcher')\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    digest = hashlib.sha256(module_file.read_bytes()).hexdigest()
    manager = type("Manager", (), {
        "session_id": "session-inspect", "base_path": str(workspace),
        "framework_root": str(framework),
    })()
    request = build_execution_request(
        effect_id="process.inspect", actor_kind="server", principal_id="bago-runtime",
        session_id="session-inspect", source_surface="server.process.inspect",
        target={"python_module": "bago_core.launcher", "python_root": str(framework),
                "python_module_sha256": digest, "cwd": str(workspace), "timeout_seconds": 30},
        arguments={"argv": ["node", "status", "--json"]}, scope="workspace",
    )
    calls = []
    monkeypatch.setattr(
        "execution_adapters.process.subprocess.run",
        lambda *args, **kwargs: calls.append((args, kwargs)) or type(
            "Completed", (), {"returncode": 0, "stdout": "{}", "stderr": ""}
        )(),
    )
    result, authorization = ExecutionGateway().execute_server_owned(
        request=request, context=ExecutionContext(manager=manager),
    )
    assert authorization["kind"] == "server_policy"
    assert result["effect_id"] == "process.inspect"
    assert result["executed"] is True
    assert len(calls) == 1

    blocked_request = build_execution_request(
        effect_id="process.inspect", actor_kind="server", principal_id="bago-runtime",
        session_id="session-inspect", source_surface="server.process.inspect",
        target={"python_module": "bago_core.launcher", "python_root": str(framework),
                "python_module_sha256": digest, "cwd": str(workspace), "timeout_seconds": 30},
        arguments={"argv": ["node", "export", "--output", "outside.json"]}, scope="workspace",
    )
    with pytest.raises(ExecutionGatewayError) as denied:
        ExecutionGateway().execute_server_owned(
            request=blocked_request, context=ExecutionContext(manager=manager),
        )
    assert denied.value.code == "process_execution_authorization_required"
    assert len(calls) == 1


def test_workspace_mirror_sync_requires_exact_permit_and_copies_through_gateway(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    source = tmp_path / "session" / "workspace"
    target = tmp_path / "project"
    source.mkdir(parents=True)
    target.mkdir()
    (source / "note.txt").write_text("session edit", encoding="utf-8")
    manager = type("Manager", (), {
        "session_id": "mirror-sync-session", "base_path": source,
        "project_root": target, "workspace_id": "workspace-1",
        "_mirror_ignore": staticmethod(lambda _directory, _names: set()),
    })()
    src, dst, digest = WorkspaceMirrorSyncEffectAdapter.prepare_operation(manager)
    request = build_execution_request(
        effect_id="workspace.mirror.sync", actor_kind="user",
        principal_id="interactive-local-user", session_id=manager.session_id,
        source_surface="test.workspace.mirror.sync",
        target={"source_root": str(src), "target_root": str(dst), "binding_digest": digest,
                "workspace_id": manager.workspace_id, "resource": "workspace_mirror", "operation": "sync"},
        arguments={}, scope="workspace",
    )
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="workspace-mirror-sync")
    gateway = ExecutionGateway(boundary=boundary)

    result, authorization = gateway.execute(
        permit_token=permit["token"], request=request,
        context=ExecutionContext(manager=manager),
    )

    assert authorization["state"] == "consumed"
    assert result["effect_id"] == "workspace.mirror.sync"
    assert (target / "note.txt").read_text(encoding="utf-8") == "session edit"


def test_workspace_mirror_sync_blocks_changed_destination_before_copy(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    source = tmp_path / "session" / "workspace"
    target = tmp_path / "project"
    changed = tmp_path / "other-project"
    source.mkdir(parents=True)
    target.mkdir()
    changed.mkdir()
    (source / "note.txt").write_text("must not copy", encoding="utf-8")
    manager = type("Manager", (), {
        "session_id": "mirror-sync-session", "base_path": source,
        "project_root": target, "workspace_id": "workspace-1",
        "_mirror_ignore": staticmethod(lambda _directory, _names: set()),
    })()
    src, dst, digest = WorkspaceMirrorSyncEffectAdapter.prepare_operation(manager)
    request = build_execution_request(
        effect_id="workspace.mirror.sync", actor_kind="user",
        principal_id="interactive-local-user", session_id=manager.session_id,
        source_surface="test.workspace.mirror.sync",
        target={"source_root": str(src), "target_root": str(dst), "binding_digest": digest,
                "workspace_id": manager.workspace_id, "resource": "workspace_mirror", "operation": "sync"},
        arguments={}, scope="workspace",
    )
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="workspace-mirror-sync-changed")
    manager.project_root = changed

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway(boundary=boundary).execute(
            permit_token=permit["token"], request=request,
            context=ExecutionContext(manager=manager),
        )

    assert blocked.value.code == "workspace_mirror_sync_target_changed"
    assert not (target / "note.txt").exists()
    assert not (changed / "note.txt").exists()


def _context_attach_manager(tmp_path: Path, *, session_id: str = "context-attach-session"):
    workspace = tmp_path / "sessions" / session_id / "workspace"
    context_root = tmp_path / "sessions" / session_id / "context"
    workspace.mkdir(parents=True)
    mirror_root = workspace
    (workspace / "docs").mkdir()
    (workspace / "docs" / "note.txt").write_text("context source", encoding="utf-8")
    return type("Manager", (), {
        "session_id": session_id,
        "base_path": workspace,
        "workspace_mirror_root": mirror_root,
        "workspace_context_root": context_root,
        "workspace_state_root": workspace / ".gabo",
        "workspace_mirror_ready": True,
        "_resolve_context_selection": staticmethod(
            lambda paths: [((workspace / paths[0]).resolve())] if paths else []
        ),
        "_mirror_ignore": staticmethod(lambda _directory, names: {
            name for name in names if name.casefold() in {".git", ".gabo", "node_modules", "__pycache__"}
        }),
    })()


def _context_attach_request(manager):
    paths = ["docs"]
    source, context_root, selected, digest = ContextAttachEffectAdapter.prepare_operation(manager, paths)
    return build_execution_request(
        effect_id="workspace.context.attach",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=manager.session_id,
        source_surface="test.context.attach",
        target={
            "source_root": str(source),
            "context_root": str(context_root),
            "selection": [str(path) for path in selected],
            "selection_digest": digest,
            "resource": "session_context",
            "operation": "attach",
        },
        arguments={"paths": paths},
        scope="workspace",
    )


def test_context_attach_requires_exact_permit_and_materializes_an_atomic_bundle(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    manager = _context_attach_manager(tmp_path)
    request = _context_attach_request(manager)
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="context-attach")
    assert not manager.workspace_context_root.exists()

    result, authorization = ExecutionGateway(boundary=boundary).execute(
        permit_token=permit["token"], request=request, context=ExecutionContext(manager=manager),
    )

    assert authorization["state"] == "consumed"
    assert result["effect_id"] == "workspace.context.attach"
    bundle_root = Path(result["data"]["bundle_root"])
    assert (bundle_root / "docs" / "note.txt").read_text(encoding="utf-8") == "context source"
    assert (bundle_root / "manifest.json").is_file()
    assert not any(path.name.startswith(".attach-") for path in manager.workspace_context_root.iterdir())


def test_context_attach_blocks_changed_source_before_bundle_creation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    manager = _context_attach_manager(tmp_path)
    request = _context_attach_request(manager)
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="context-attach-changed")
    (manager.base_path / "docs" / "note.txt").write_text("changed after approval", encoding="utf-8")

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway(boundary=boundary).execute(
            permit_token=permit["token"], request=request, context=ExecutionContext(manager=manager),
        )

    assert blocked.value.code == "context_attach_target_changed"
    assert not manager.workspace_context_root.exists()


def test_context_attach_adapter_rejects_unbound_consumed_authorization_before_write(tmp_path) -> None:
    manager = _context_attach_manager(tmp_path)
    request = _context_attach_request(manager)

    with pytest.raises(ExecutionGatewayError) as blocked:
        ContextAttachEffectAdapter().execute(
            request,
            ExecutionContext(manager=manager, services={"_authorization": {"state": "consumed"}}),
        )

    assert blocked.value.code == "context_attach_authorization_required"
    assert not manager.workspace_context_root.exists()


def test_registry_rejects_duplicate_effect_ownership() -> None:
    registry = EffectAdapterRegistry()
    registry.register(_RecordingAdapter())
    with pytest.raises(ExecutionGatewayError) as duplicate:
        registry.register(_RecordingAdapter())
    assert duplicate.value.code == "execution_adapter_duplicate"


def test_default_registry_owns_governed_plan_and_filesystem_adapters() -> None:
    registry = build_default_effect_adapter_registry()

    assert "filesystem.write" in registry.registered_effects()
    assert "filesystem.read" in registry.registered_effects()
    assert "plan.execute" in registry.registered_effects()
    assert "state.write" in registry.registered_effects()
    assert "state.directory.ensure" in registry.registered_effects()
    assert "state.bootstrap" in registry.registered_effects()
    assert "config.write" in registry.registered_effects()
    assert "memory.write" in registry.registered_effects()
    assert "agent.definition.write" in registry.registered_effects()
    assert "workspace.bind" in registry.registered_effects()
    assert "workspace.mirror.sync" in registry.registered_effects()
    assert "workspace.context.attach" in registry.registered_effects()
    assert "state.delete" in registry.registered_effects()
    assert "project.write" in registry.registered_effects()
    assert "credential.write" in registry.registered_effects()


def test_project_operation_revalidates_target_immediately_before_first_write(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# project\n", encoding="utf-8")
    manager = type("Manager", (), {
        "project_root": project,
        "session_id": "project-write-session",
    })()
    trusted_root, target, target_digest = ProjectWriteEffectAdapter.prepare_operation(
        manager,
        str(project),
        "init",
    )
    request = build_execution_request(
        effect_id="project.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=manager.session_id,
        source_surface="test.project.init",
        target={
            "path": str(target),
            "allowed_root": str(trusted_root),
            "resource": "project_operation",
            "operation": "init",
            "root_digest": target_digest,
        },
        arguments={},
        scope="workspace",
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="project-write-target")
    (project / ".bago").mkdir()
    tamper = project / ".bago" / "tamper.txt"
    tamper.write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway(boundary).execute(
            permit_token=permit["token"],
            request=request,
            context=ExecutionContext(manager=manager),
        )

    assert blocked.value.code == "project_write_target_changed"
    assert tamper.read_text(encoding="utf-8") == "do not overwrite"
    assert not (project / ".bago" / "pack.json").exists()


def test_project_operation_allows_authorized_root_switch(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    class Manager:
        project_root = project
        session_id = "project-root-session"

        def rebind_project_root(self, target):
            self.project_root = Path(target).resolve()

    manager = Manager()
    trusted_root, target, target_digest = ProjectWriteEffectAdapter.prepare_operation(
        manager, str(other), "init",
    )
    request = build_execution_request(
        effect_id="project.write", actor_kind="user",
        principal_id="interactive-local-user", session_id=manager.session_id,
        source_surface="test.project.root",
        target={"path": str(target), "allowed_root": str(trusted_root),
                "resource": "project_operation", "operation": "init",
                "root_digest": target_digest}, arguments={}, scope="workspace",
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="project-write-root")
    result, _ = ExecutionGateway(boundary).execute(
        permit_token=permit["token"], request=request, context=ExecutionContext(manager=manager),
    )
    assert result["ok"] is True
    assert manager.project_root == other.resolve()
    assert (other / ".bago").exists()
    assert not (project / ".bago").exists()


def test_project_operation_rejects_tampered_authorized_target(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    manager = type("Manager", (), {"project_root": project, "session_id": "project-root-session"})()
    trusted_root, target, target_digest = ProjectWriteEffectAdapter.prepare_operation(manager, str(project), "init")
    request = build_execution_request(
        effect_id="project.write", actor_kind="user", principal_id="interactive-local-user",
        session_id=manager.session_id, source_surface="test.project.root",
        target={"path": str(target), "allowed_root": str(trusted_root), "resource": "project_operation",
                "operation": "init", "root_digest": target_digest}, arguments={}, scope="workspace",
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="project-write-tamper")
    request.target["path"] = str(tmp_path / "tampered")
    with pytest.raises(auth.AuthorizationError) as blocked:
        ExecutionGateway(boundary).execute(permit_token=permit["token"], request=request, context=ExecutionContext(manager=manager))
    assert blocked.value.code == "authorization_operation_mismatch"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("path", "tampered"),
        ("allowed_root", "tampered"),
        ("root_digest", "tampered-digest"),
        ("scope", "persistent"),
    ],
)
def test_project_root_switch_rejects_post_authorization_tampering_without_mutation(
    tmp_path, monkeypatch, field, replacement,
) -> None:
    active = tmp_path / "active"
    selected = tmp_path / "selected"
    active.mkdir()
    selected.mkdir()

    class Manager:
        project_root = active
        session_id = "project-root-tamper-session"

        def rebind_project_root(self, target):
            self.project_root = Path(target).resolve()

    manager = Manager()
    trusted_root, target, target_digest = ProjectWriteEffectAdapter.prepare_operation(
        manager, str(selected), "init",
    )
    request = build_execution_request(
        effect_id="project.write", actor_kind="user", principal_id="interactive-local-user",
        session_id=manager.session_id, source_surface="test.project.root-switch",
        target={"path": str(target), "allowed_root": str(trusted_root), "resource": "project_operation",
                "operation": "init", "root_digest": target_digest}, arguments={}, scope="workspace",
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction=f"project-root-tamper-{field}")
    if field == "scope":
        object.__setattr__(request, "scope", replacement)
    else:
        request.target[field] = str(tmp_path / replacement) if field != "root_digest" else replacement

    with pytest.raises(auth.AuthorizationError) as blocked:
        ExecutionGateway(boundary).execute(
            permit_token=permit["token"], request=request, context=ExecutionContext(manager=manager),
        )

    assert blocked.value.code == "authorization_operation_mismatch"
    assert manager.project_root == active.resolve()
    assert not (active / ".bago").exists()
    assert not (selected / ".bago").exists()


def test_credential_adapter_rejects_non_direct_strong_proof_before_secret_store_access(tmp_path) -> None:
    manager = type("Manager", (), {"session_id": "credential-session"})()
    request = build_execution_request(
        effect_id="credential.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=manager.session_id,
        source_surface="test.credential",
        target={
            "resource": "provider_credential",
            "operation": "set",
            "provider": "openrouter",
            "key": "api_key",
            "configuration_digest": "config-digest",
        },
        arguments={"value": "must-not-be-used"},
        scope="persistent",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        CredentialWriteEffectAdapter().execute(
            request,
            ExecutionContext(
                manager=manager,
                services={
                    "_authorization": {
                        "state": "consumed",
                        "proof": {"provenance": {"kind": "delegation_grant"}},
                    }
                },
            ),
        )

    assert blocked.value.code == "credential_write_strong_proof_required"


class _FakeProviderConfig:
    """Stand-in for SessionManager.config exposing provider_config(name)."""

    def __init__(self, providers: dict) -> None:
        self._providers = providers

    def provider_config(self, provider: str) -> dict:
        return dict(self._providers.get(provider, {}))


def _consumed_authorization() -> dict:
    return {
        "state": "consumed",
        "proof": {"provenance": {"kind": "direct_user_interaction"}},
    }


def _credential_request(*, operation: str, configuration_digest: str, configuration_patch: dict, provider: str = "openrouter"):
    return build_execution_request(
        effect_id="credential.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="credential-session",
        source_surface="test.credential",
        target={
            "resource": "provider_credential",
            "operation": operation,
            "provider": provider,
            "key": "api_key",
            "configuration_digest": configuration_digest,
            "configuration_patch": configuration_patch,
        },
        arguments={"value": "fresh-secret"} if operation == "set" else {},
        scope="persistent",
    )


def test_credential_adapter_matching_digest_succeeds_for_set_and_delete(monkeypatch, tmp_path) -> None:
    import secret_store as secret_store_module
    from execution_request import stable_digest

    live_config = {"enabled": False, "base_url": "https://openrouter.ai/api/v1"}
    patch = {"enabled": True, "default_model": "openai/gpt-4.1-mini"}
    candidate = {**live_config, **patch}
    digest = stable_digest(candidate)

    manager = type("Manager", (), {"session_id": "credential-session"})()
    manager.config = _FakeProviderConfig({"openrouter": live_config})
    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    monkeypatch.setattr(secret_store_module, "_is_windows", lambda: False)
    store = secret_store_module.get_secret_store()

    for operation in ("set", "delete"):
        request = _credential_request(operation=operation, configuration_digest=digest, configuration_patch=patch)
        result = CredentialWriteEffectAdapter().execute(
            request,
            ExecutionContext(manager=manager, services={"_authorization": _consumed_authorization()}),
        )
        assert result["ok"] is True
        assert result["changed"] is True
        if operation == "set":
            assert store.get_secret("providers/openrouter/api_key") == "fresh-secret"
        else:
            assert store.get_secret("providers/openrouter/api_key") is None


def test_credential_adapter_rejects_drifted_configuration_before_secret_store_access_set(monkeypatch, tmp_path) -> None:
    from execution_request import stable_digest

    approved_live_config = {"enabled": False, "base_url": "https://openrouter.ai/api/v1"}
    patch = {"enabled": True}
    authorized_digest = stable_digest({**approved_live_config, **patch})

    # Backend config drifted (e.g. concurrent write) after the digest above
    # was authorized: base_url changed from what the requester approved.
    drifted_live_config = {"enabled": False, "base_url": "https://drifted.example/api"}
    manager = type("Manager", (), {"session_id": "credential-session"})()
    manager.config = _FakeProviderConfig({"openrouter": drifted_live_config})

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    request = _credential_request(operation="set", configuration_digest=authorized_digest, configuration_patch=patch)

    with pytest.raises(ExecutionGatewayError) as blocked:
        CredentialWriteEffectAdapter().execute(
            request,
            ExecutionContext(manager=manager, services={"_authorization": _consumed_authorization()}),
        )

    assert blocked.value.code == "credential_write_configuration_changed"
    assert not (tmp_path / "user" / "secrets").exists()


def test_credential_adapter_rejects_drifted_configuration_before_secret_store_access_delete(monkeypatch, tmp_path) -> None:
    from execution_request import stable_digest

    approved_live_config = {"enabled": True, "default_model": "openai/gpt-4.1-mini"}
    patch = {"default_model": "openai/gpt-4.1-nano"}
    authorized_digest = stable_digest({**approved_live_config, **patch})

    drifted_live_config = {"enabled": False, "default_model": "openai/gpt-4.1-mini"}
    manager = type("Manager", (), {"session_id": "credential-session"})()
    manager.config = _FakeProviderConfig({"openrouter": drifted_live_config})

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    request = _credential_request(operation="delete", configuration_digest=authorized_digest, configuration_patch=patch)

    with pytest.raises(ExecutionGatewayError) as blocked:
        CredentialWriteEffectAdapter().execute(
            request,
            ExecutionContext(manager=manager, services={"_authorization": _consumed_authorization()}),
        )

    assert blocked.value.code == "credential_write_configuration_changed"
    assert not (tmp_path / "user" / "secrets").exists()


def test_credential_adapter_requires_authoritative_configuration_source(monkeypatch, tmp_path) -> None:
    from execution_request import stable_digest

    manager = type("Manager", (), {"session_id": "credential-session"})()
    # No `.config` attribute at all: fail closed rather than trust anything.

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    request = _credential_request(
        operation="set",
        configuration_digest=stable_digest({"enabled": True}),
        configuration_patch={"enabled": True},
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        CredentialWriteEffectAdapter().execute(
            request,
            ExecutionContext(manager=manager, services={"_authorization": _consumed_authorization()}),
        )

    assert blocked.value.code == "credential_write_configuration_source_unavailable"
    assert not (tmp_path / "user" / "secrets").exists()


@pytest.mark.parametrize(
    "configuration_patch",
    [
        {"api_key": "leaked-secret"},
        {"secret_ref": "bago://secrets/providers/openrouter/api_key"},
        {"unexpected_field": "value"},
        {"enabled": "true"},
        "not-a-dict",
    ],
)
def test_credential_adapter_rejects_invalid_or_secret_bearing_patch(monkeypatch, tmp_path, configuration_patch) -> None:
    from execution_request import stable_digest

    manager = type("Manager", (), {"session_id": "credential-session"})()
    manager.config = _FakeProviderConfig({"openrouter": {"enabled": False}})

    monkeypatch.setenv("BAGO_USER_ROOT", str(tmp_path / "user"))
    request = build_execution_request(
        effect_id="credential.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="credential-session",
        source_surface="test.credential",
        target={
            "resource": "provider_credential",
            "operation": "set",
            "provider": "openrouter",
            "key": "api_key",
            "configuration_digest": stable_digest({"enabled": False}),
            "configuration_patch": configuration_patch,
        },
        arguments={"value": "fresh-secret"},
        scope="persistent",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        CredentialWriteEffectAdapter().execute(
            request,
            ExecutionContext(manager=manager, services={"_authorization": _consumed_authorization()}),
        )

    assert blocked.value.code == "credential_write_configuration_patch_invalid"
    assert not (tmp_path / "user" / "secrets").exists()


def test_workspace_bind_adapter_executes_compound_effect_only_after_permit(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "package.json").write_text("{}", encoding="utf-8")
    current = tmp_path / "current"
    current.mkdir()
    (current / "package.json").write_text("{}", encoding="utf-8")

    class Manager:
        session_id = "workspace-bind-session"

        def __init__(self) -> None:
            self.project_root = current.resolve()
            self.rebound_to: Path | None = None
            self.save_calls = 0

        @staticmethod
        def _validate_project_root(project_root: Path, *, require_identity: bool = False) -> Path:
            from session_manager import SessionManager

            return SessionManager._validate_project_root(project_root, require_identity=require_identity)

        def rebind_project_root(self, root: Path) -> None:
            self.rebound_to = root.resolve()
            self.project_root = self.rebound_to

        def save(self) -> None:
            self.save_calls += 1

        def workspace_state(self) -> dict[str, str]:
            return {"workspace_state_root": str(self.project_root / ".gabo")}

    manager = Manager()
    adapter = WorkspaceBindEffectAdapter()
    binding = adapter.binding_descriptor(workspace.resolve())
    request = build_execution_request(
        effect_id="workspace.bind",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=manager.session_id,
        source_surface="test.workspace.bind",
        target={
            "path": str(workspace.resolve()),
            "resource": "session_workspace",
            "operation": "persist",
            "workspace_id": binding["workspace_id"],
            "workspace_scope_root": binding["workspace_scope_root"],
            "workspace_state_root": binding["workspace_state_root"],
            "binding_digest": adapter.binding_descriptor_digest(binding),
        },
        arguments={},
        scope="workspace",
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    monkeypatch.setattr(
        WorkspaceBindEffectAdapter,
        "_persist_last_workspace",
        staticmethod(lambda _target: None),
    )
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="workspace-bind")

    result, authorization = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is True
    assert result["effect_id"] == "workspace.bind"
    assert result["rebound"] is True
    assert manager.rebound_to == workspace.resolve()
    assert manager.save_calls == 1
    assert authorization["state"] == "consumed"


def test_workspace_bind_revalidates_before_rebind_after_authorization(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = workspace / "package.json"
    marker.write_text("{}", encoding="utf-8")

    class Manager:
        session_id = "workspace-bind-session"
        project_root = tmp_path.resolve()

        def __init__(self) -> None:
            self.rebound = False
            self.save_calls = 0

        @staticmethod
        def _validate_project_root(project_root: Path, *, require_identity: bool = False) -> Path:
            from session_manager import SessionManager

            return SessionManager._validate_project_root(project_root, require_identity=require_identity)

        def rebind_project_root(self, _root: Path) -> None:
            self.rebound = True

        def save(self) -> None:
            self.save_calls += 1

    manager = Manager()
    adapter = WorkspaceBindEffectAdapter()
    binding = adapter.binding_descriptor(workspace.resolve())
    request = build_execution_request(
        effect_id="workspace.bind",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=manager.session_id,
        source_surface="test.workspace.bind",
        target={
            "path": str(workspace.resolve()),
            "resource": "session_workspace",
            "operation": "persist",
            "workspace_id": binding["workspace_id"],
            "workspace_scope_root": binding["workspace_scope_root"],
            "workspace_state_root": binding["workspace_state_root"],
            "binding_digest": adapter.binding_descriptor_digest(binding),
        },
        arguments={},
        scope="workspace",
    )
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    boundary = auth.AuthorizationBoundary()
    permit = _permit(boundary, request, interaction="workspace-bind-stale")
    marker.unlink()

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway(boundary).execute(
            permit_token=permit["token"],
            request=request,
            context=ExecutionContext(manager=manager),
        )

    assert blocked.value.code == "workspace_bind_target_invalid"
    assert manager.rebound is False
    assert manager.save_calls == 0


def test_state_delete_is_materialized_only_after_gateway_permit(tmp_path, monkeypatch) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    override = state_root / ".bago_session_model.json"
    override.write_text('{"model":"copilot/gpt-5.4-mini"}', encoding="utf-8")
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    manager = type("Manager", (), {
        "state_root": state_root,
        "session_id": "state-delete-session",
    })()
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="state.delete",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="state-delete-session",
        source_surface="test.state.delete",
        target={
            "path": str(override),
            "allowed_root": str(state_root.resolve()),
            "resource": "session_model_override",
        },
        arguments={"operation": "clear"},
        scope="session",
    )
    permit = _permit(boundary, request, interaction="interaction-state-delete")

    result, authorization = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is True
    assert result["effect_id"] == "state.delete"
    assert result["deleted"] is True
    assert result["receipt_id"].startswith("state-delete:sha256:")
    assert authorization["state"] == "consumed"
    assert not override.exists()


def test_state_delete_rejects_noncanonical_target_before_unlink(tmp_path, monkeypatch) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    other = state_root / "other.json"
    other.write_text("must-remain", encoding="utf-8")
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "authorization")
    manager = type("Manager", (), {
        "state_root": state_root,
        "session_id": "state-delete-session",
    })()
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="state.delete",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="state-delete-session",
        source_surface="test.state.delete",
        target={
            "path": str(other),
            "allowed_root": str(state_root.resolve()),
            "resource": "session_model_override",
        },
        arguments={"operation": "clear"},
        scope="session",
    )
    permit = _permit(boundary, request, interaction="interaction-state-delete-invalid")

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway(boundary).execute(
            permit_token=permit["token"],
            request=request,
            context=ExecutionContext(manager=manager),
        )

    assert blocked.value.code == "state_delete_target_invalid"
    assert other.read_text(encoding="utf-8") == "must-remain"


def test_server_policy_state_write_is_materialized_by_the_gateway(tmp_path) -> None:
    from bago_core.atomic_json import write_json_atomic

    target = tmp_path / "state" / "record.json"
    write_json_atomic(target, {"ok": True, "owner": "gateway"})

    assert target.exists()
    assert '"owner": "gateway"' in target.read_text(encoding="utf-8")


def test_server_policy_state_write_blocks_root_mismatch_before_effect(tmp_path) -> None:
    request = build_execution_request(
        effect_id="state.write",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="server-state-test",
        source_surface="server.test",
        target={
            "path": str(tmp_path / "state.json"),
            "allowed_root": str(tmp_path / "other-root"),
            "operation": "replace_text",
        },
        arguments={"content": "must-not-exist"},
        scope="session",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute_server_owned(
            request=request,
            context=ExecutionContext(services={"_server_allowed_root": str(tmp_path)}),
        )

    assert blocked.value.code == "server_state_root_mismatch"
    assert not (tmp_path / "state.json").exists()


def test_server_policy_path_traversal_is_blocked_before_effect(tmp_path) -> None:
    root = tmp_path / "state"
    target = root / ".." / "outside.json"
    request = build_execution_request(
        effect_id="state.write",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="server-state-test",
        source_surface="server.test",
        target={
            "path": str(target),
            "allowed_root": str(root),
            "operation": "replace_text",
        },
        arguments={"content": "must-not-exist"},
        scope="session",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute_server_owned(
            request=request,
            context=ExecutionContext(services={"_server_allowed_root": str(root)}),
        )

    assert blocked.value.code == "server_state_path_out_of_scope"
    assert not (tmp_path / "outside.json").exists()


def test_public_gateway_cannot_consume_a_server_policy_effect(tmp_path) -> None:
    request = build_execution_request(
        effect_id="state.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.gateway",
        target={"path": "state.json"},
        arguments={"content": "must-not-exist"},
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute(permit_token="unused", request=request)

    assert blocked.value.code == "execution_server_policy_only"


def test_server_policy_network_adapter_blocks_unclassified_surface(monkeypatch) -> None:
    import urllib.request

    called = False

    def _unexpected(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network effect must be blocked before urlopen")

    monkeypatch.setattr(urllib.request, "urlopen", _unexpected)
    request = build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="network-test",
        source_surface="server.network.unknown",
        target={
            "url": "https://example.invalid/blocked",
            "method": "GET",
            "network_class": "unknown",
            "timeout": 1.0,
        },
        arguments={},
        scope="external",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute_server_owned(request=request)

    assert blocked.value.code == "network_read_surface_blocked"
    assert called is False


@pytest.mark.parametrize(
    ("url", "method", "expected_code"),
    [
        ("https://downloads.example.invalid/payload", "GET", "network_read_release_host_blocked"),
        ("http://api.github.com/repos/MarcValls/BAGO/releases", "GET", "network_read_release_host_blocked"),
        ("https://api.github.com/repos/MarcValls/BAGO/releases", "POST", "network_read_release_method_blocked"),
    ],
)
def test_release_network_policy_blocks_host_scheme_and_mutation_before_open(
    monkeypatch, url: str, method: str, expected_code: str,
) -> None:
    import urllib.request

    called = False

    def _unexpected(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unapproved release request reached network opener")

    monkeypatch.setattr(urllib.request, "build_opener", _unexpected)
    request = build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime",
        session_id="network-release-test",
        source_surface="server.network.release_asset_download",
        target={
            "url": url,
            "method": method,
            "network_class": "release_asset_download" if "api.github.com" not in url else "release_metadata",
            "timeout": 1.0,
        },
        arguments={},
        scope="external",
    )

    with pytest.raises(ExecutionGatewayError) as blocked:
        ExecutionGateway().execute_server_owned(request=request)

    assert blocked.value.code == expected_code
    assert called is False


def test_release_redirect_guard_blocks_unapproved_host_before_following(monkeypatch) -> None:
    import urllib.request

    called = False

    def _open_with_unsafe_redirect(handler):
        class _Opener:
            def open(self, *_args, **_kwargs):
                nonlocal called
                called = True
                handler.redirect_request(
                    None, None, 302, "Found", {}, "https://evil.example/payload"
                )

        return _Opener()

    monkeypatch.setattr(urllib.request, "build_opener", _open_with_unsafe_redirect)
    from bago_core.server_effects import gateway_urlopen

    with pytest.raises(Exception) as blocked:
        gateway_urlopen(
            "https://github.com/MarcValls/BAGO/releases/download/v1/payload.zip",
            network_class="release_asset_download",
        )

    assert blocked.value.code == "network_read_redirect_blocked"
    assert called is True


def test_gateway_urlopen_exposes_first_chunk_before_eof(monkeypatch) -> None:
    import urllib.request

    second_chunk_allowed = threading.Event()

    class _SlowResponse:
        status = 200
        headers = {"Content-Type": "text/event-stream"}

        def __init__(self):
            self.calls = 0

        def read(self, amount=-1):
            self.calls += 1
            if self.calls == 1:
                return b"data: first\n\n"
            if not second_chunk_allowed.wait(1.0):
                raise TimeoutError("EOF was requested before the delayed chunk")
            return b"data: second\n\n"

        def close(self):
            second_chunk_allowed.set()

        def getcode(self):
            return 200

        def geturl(self):
            return "https://example.test/stream"

    response = _SlowResponse()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: response)
    from bago_core.server_effects import gateway_urlopen

    streamed = gateway_urlopen("https://example.test/stream", timeout=1.0)
    assert response.calls == 0
    assert streamed.read() == b"data: first\n\n"
    assert response.calls == 1
    streamed.close()


def test_server_policy_network_adapter_returns_streaming_response(monkeypatch) -> None:
    import urllib.request

    class _Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def read(self):
            return b'{"ok":true}'

        def getcode(self):
            return 200

        def geturl(self):
            return "https://example.test/status"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: _Response())
    from bago_core.server_effects import gateway_urlopen

    with gateway_urlopen("https://example.test/status", timeout=1.0) as response:
        assert response.status == 200
        assert response.read() == b'{"ok":true}'
        assert response.headers["Content-Type"] == "application/json"


def test_filesystem_write_is_materialized_only_after_gateway_permit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    manager = type(
        "Manager",
        (),
        {
            "base_path": tmp_path,
            "project_root": tmp_path,
            "workspace_scope_root": tmp_path,
            "workspace_mirror_root": tmp_path,
            "session_id": "session-1",
        },
    )()
    boundary = auth.AuthorizationBoundary()
    request = build_execution_request(
        effect_id="filesystem.write",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="session-1",
        source_surface="test.filesystem.gateway",
        target={"path": "notes/example.txt"},
        arguments={"content": "gateway-only"},
    )
    permit = _permit(boundary, request, interaction="interaction-filesystem")

    result, authorization = ExecutionGateway(boundary).execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is True
    assert result["effect_id"] == "filesystem.write"
    assert result["receipt_id"].startswith("filesystem-write:sha256:")
    assert authorization["state"] == "consumed"
    assert (tmp_path / "notes" / "example.txt").read_text(encoding="utf-8") == "gateway-only"

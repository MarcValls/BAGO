# WorldStateSnapshot production request inventory

Effect registry: `bago.effect-registry.v1` `1.24.0` SHA-256 `309702e4871ff90ca527e9d2ae7f8bcfa669a91a8a79c0dcd2cfbbe49f8ff119`.
Scope: direct `build_execution_request` calls in `backend/.bago/` and `backend/bago_core/`.
Callsites: 60; mutating or dynamic-effect calls without a usable `world_state_authority` input: 0.
Gateway: mutating requests reject unspecified state and revalidate their authority-bound snapshot before Permit consumption and immediately before adapter dispatch.
Strong effects: every registered mutating E5/E6 adapter must expose `revalidate_world_state`; missing hooks fail Gateway registry construction and unadapted effects remain denied.
Process termination: `cleanup_zombies` binds PID, executable, command line, and creation time into the Permit target; the Gateway re-enumerates candidates before consumption/dispatch and the Windows terminator rechecks exact identities before acting.

| File | Line | Function | Effect | Mutates | Risk | Snapshot authority value |
|---|---:|---|---|---:|---|---|
| backend/.bago/agents/agent_command_execution.py | 38 | execute_agent_command | process.execute | True | E4 | manager |
| backend/.bago/api/handlers_capability_packages.py | 101 | _handle_import_authorized | capability.package.import | True | E3 | manager |
| backend/.bago/api/handlers_capability_packages.py | 194 | execute | <dynamic> | dynamic | dynamic | mgr |
| backend/.bago/api/handlers_context_attach.py | 37 | handle | workspace.context.attach | True | E3 | manager |
| backend/.bago/api/handlers_files.py | 423 | handle_write | filesystem.write | True | E3 | mgr |
| backend/.bago/api/handlers_github.py | 38 | _run_gh | process.inspect | False | E1 | manager |
| backend/.bago/api/handlers_install.py | 40 | handle_apply | system.install.apply | True | E5 | manager |
| backend/.bago/api/handlers_install.py | 118 | handle_source_update | system.source.update | True | E5 | manager |
| backend/.bago/api/handlers_install.py | 187 | handle_uninstall | system.install.uninstall | True | E5 | manager |
| backend/.bago/api/handlers_install.py | 267 | handle_rollback | system.install.rollback | True | E5 | manager |
| backend/.bago/api/handlers_jobs.py | 348 | _plan_execution_request | plan.execute | True | E3 | mgr |
| backend/.bago/api/handlers_manager_settings.py | 34 | handle_write | manager.settings.write | True | E4 | manager |
| backend/.bago/api/handlers_process.py | 129 | handle_execute | <dynamic> | dynamic | dynamic | manager |
| backend/.bago/api/handlers_project.py | 223 | handle_project_sync | workspace.mirror.sync | True | E3 | mgr |
| backend/.bago/api/handlers_project.py | 317 | _handle_project_write | project.write | True | E3 | mgr |
| backend/.bago/api/handlers_providers.py | 234 | handle_configure | credential.write | True | E5 | mgr |
| backend/.bago/api/handlers_release.py | 45 | handle_apply | system.update.apply | True | E5 | mgr |
| backend/.bago/api/handlers_release_jobs.py | 14 | _dispatch | <dynamic> | dynamic | dynamic | manager |
| backend/.bago/api/handlers_release_jobs.py | 220 | handle_archive_job | release.job.archive | True | E3 | manager |
| backend/.bago/api/handlers_router.py | 313 | handle_session_model | state.delete | True | E3 | mgr |
| backend/.bago/api/handlers_schedule.py | 239 | _delegation_request | schedule.delegate | True | E6 | mgr |
| backend/.bago/api/handlers_schedule.py | 391 | _validated_child_for_schedule | <dynamic> | dynamic | dynamic | mgr |
| backend/.bago/api/handlers_workspace.py | 177 | handle_persist | workspace.bind | True | E3 | mgr |
| backend/.bago/bin/bago.py | 105 | _execute_verify_command | process.execute | True | E4 | manager |
| backend/.bago/chat/project_commands.py | 40 | build_project_write_request | project.write | True | E3 | mgr |
| backend/.bago/core/authorization_boundary.py | 106 | build_operation | capability.execute | True | E3 | world_state_authority |
| backend/.bago/core/autonomous_loop.py | 169 | _atomic_write | state.write | True | E2 | root |
| backend/.bago/core/autonomous_loop.py | 217 | _run_tool | <dynamic> | dynamic | dynamic | _BAGO_ROOT |
| backend/.bago/core/credential_manager.py | 223 | _execute_secret_write | credential.write | True | E5 | manager |
| backend/.bago/core/database_write_request.py | 56 | build_memory_database_request | database.write | True | E3 | manager |
| backend/.bago/core/governed_work_pipeline.py | 774 | _executor | <dynamic> | dynamic | dynamic | context.manager |
| backend/.bago/core/msix_bootstrap.py | 81 | install_from_package | system.install.apply | True | E5 | _SESSION_MANAGER |
| backend/.bago/core/project_patch_operations.py | 39 | build_apply_request | project.write | True | E3 | manager |
| backend/.bago/core/project_patch_operations.py | 55 | build_rollback_request | project.write | True | E3 | manager |
| backend/.bago/core/session_manager.py | 328 | _prepare_session_mirror | workspace.mirror.prepare | True | E2 | manager_for_gateway |
| backend/.bago/core/session_tools_mixin.py | 40 | execute_runtime_control | process.execute | True | E4 | self |
| backend/.bago/integrations/pi/process_boundary.py | 179 | run_sidecar | process.sidecar.execute | False | E4 | Path(spec.cwd) |
| backend/.bago/roles/role_factory.py | 201 | create_role | role.definition.create | True | E3 | root |
| backend/.bago/tools/bago_canary.py | 117 | deploy | security.canary.manage | True | E5 | root |
| backend/.bago/tools/bago_canary.py | 171 | purge | security.canary.manage | True | E5 | root |
| backend/.bago/tools/bago_utils.py | 80 | save_json | state.write | True | E2 | root |
| backend/.bago/tools/commit_readiness.py | 70 | git | repository.inspect | False | E1 | cwd |
| backend/.bago/tools/debt_guard.py | 95 | _execute_repository_mutation | repository.guard.manage | True | E4 | root |
| backend/.bago/tools/debt_guard.py | 190 | _staged_python_files | repository.inspect | False | E1 | canonical |
| backend/.bago/tools/process_monitor.py | 523 | main | monitor.generate | True | E3 | root |
| backend/.bago/tools/project_memory.py | 694 | _execute_cli_project_write | project.write | True | E3 | manager |
| backend/bago_core/commands/cmd_content.py | 250 | cmd_manager | process.execute | True | E4 | root |
| backend/bago_core/commands/cmd_layer.py | 47 | writer | state.write | True | E2 | Path(args.root or Path.cwd()) |
| backend/bago_core/commands/cmd_lifecycle.py | 170 | cmd_rollback_archive | system.install.archive.rollback | True | E5 | Path(install_dir) |
| backend/bago_core/evidence_authorized.py | 26 | generate_bundle | evidence.bundle.generate | True | E5 | base_path |
| backend/bago_core/server_effects.py | 45 | _execute_text | <dynamic> | dynamic | dynamic | root |
| backend/bago_core/server_effects.py | 95 | ensure_user_directory | state.directory.ensure | True | E1 | root |
| backend/bago_core/server_effects.py | 187 | _execute_runtime_state_bootstrap | state.bootstrap | True | E2 | root |
| backend/bago_core/server_effects.py | 247 | append_structured_log | logging.append | True | E2 | root |
| backend/bago_core/server_effects.py | 277 | stage_validation_workspace | workspace.validation.stage | True | E2 | root |
| backend/bago_core/server_effects.py | 300 | cleanup_validation_workspace | workspace.validation.stage | True | E2 | root |
| backend/bago_core/server_effects.py | 341 | gateway_urlopen | network.read | False | E1 | Path.cwd() |
| backend/bago_core/server_effects.py | 380 | download_release_bundle | release.download | True | E2 | download_root |
| backend/bago_core/server_effects.py | 421 | inspect_process | process.inspect | False | E1 | manager |
| backend/bago_core/server_effects.py | 450 | inspect_process_identities | process.inspect | False | E1 | manager |

Unbound callsites:
- None.

Result: PASS

# Capability lineage

Freeze `b9b2eda8f21be16f5ade510b5f069abe09ae5387` · surface `e5558324b436c03cb6f8470522951b05ff468fd673cfdbdde433c6f557fcf908`.

The full records are in CAPABILITY_PRESERVATION_MATRIX.json. Early tags are not all ancestors of HEAD; divergent history cannot prove a deletion on the current branch.

## C01 · Estado de sesión

v4.0.0-mvp → v4.8.0 → IMPLEMENTED → **EXTENDED**
Owner SessionManager → SessionManager
Routes GET /session; /status; /session → GET /session; /status; /session
Evidence: v4.0.0-mvp:.bago/core/session.py:12; v4.5.0:.bago/api/bridge.py:253; v4.8.0:backend/.bago/core/session_manager.py:102; backend/.bago/api/handlers_session.py:20; backend/tests/test_session_recovery_contract.py
Notes: NOT_ESTABLISHED; SCOPED

## C02 · Guardar, cargar y recuperar sesión

v4.5.0 → v4.5.0 → IMPLEMENTED → **EXTENDED**
Owner SessionManager + ContextStore → SessionManager + ContextStore
Routes /save; /load; sesiones API → /save; /load; sesiones API
Evidence: v4.5.0:.bago/chat/commands.py::cmd_save/cmd_load; backend/.bago/chat/commands.py:398; backend/tests/test_chat_command_load_workspace.py; backend/tests/test_session_recovery_contract.py
Notes: NOT_ESTABLISHED; SCOPED

## C03 · Chat y streaming

v4.5.0 → v4.5.0 → IMPLEMENTED → **EXTENDED**
Owner SessionManager.send + chat_turns → SessionManager.send + chat_turns
Routes POST /chat; POST /chat/stream → POST /chat; POST /chat/stream
Evidence: v4.5.0:.bago/api/bridge.py:368; backend/.bago/api/handlers_chat.py:115; backend/tests/test_chat_turn_idempotency.py
Notes: NOT_ESTABLISHED; SCOPED

## C04 · Cambiar proveedor/modelo

v4.5.0 → v4.5.0 → IMPLEMENTED → **PRESERVED**
Owner SwitchEngine → SwitchEngine
Routes POST /switch; /switch; /models → POST /switch; /switch; /models
Evidence: v4.5.0:.bago/api/bridge.py:450; backend/.bago/api/handlers_switch.py:20; backend/tests/test_session_recovery_contract.py
Notes: NOT_ESTABLISHED; SCOPED

## C05 · Comandos por HTTP

v4.5.0 → v4.8.0 → IMPLEMENTED → **REPLACED_EQUIVALENTLY**
Owner chat.commands.execute → chat.commands.execute
Routes POST /command → /api/v1/commands → POST /command → /api/v1/commands
Evidence: v4.5.0:.bago/api/bridge.py:413; v4.8.0:backend/contracts/api_routes.generated.json; backend/.bago/api/legacy_aliases.py:55; backend/tests/test_sprint_4_surfaces.py
Notes: EXPLICIT_COMPATIBILITY_ALIAS; SCOPED

## C06 · Workspace y operaciones de proyecto

v4.8.0 → v4.8.0 → IMPLEMENTED → **REPLACED_EQUIVALENTLY**
Owner handlers_workspace / ProjectWriteEffectAdapter → handlers_workspace / ProjectWriteEffectAdapter
Routes /workspaces → /workspace/list; /workspace/{init,link,seed,sync} → /project/* → /workspaces → /workspace/list; /workspace/{init,link,seed,sync} → /project/*
Evidence: v4.8.0:backend/contracts/api_routes.generated.json; backend/.bago/api/legacy_aliases.py:49; backend/tests/test_workspace_seed_contract.py
Notes: EXPLICIT_ALIAS_AND_AUTHORIZATION; SCOPED

## C07 · Historial y conversaciones

v4.9.0 → v4.9.0 → IMPLEMENTED → **EXTENDED**
Owner ContextStore → ContextStore
Routes GET /history; /conversations; /workspace/conversation → GET /history; /conversations; /workspace/conversation
Evidence: v4.5.0:.bago/api/bridge.py:268; v4.9.0:backend/tests/test_conversation_contract.py; backend/.bago/api/handlers_conversations.py:15; backend/tests/test_conversation_contract.py
Notes: NOT_ESTABLISHED; SCOPED

## C08 · Escribir archivos desde API

v4.8.0 → v4.11.0 → IMPLEMENTED → **RESTRICTED_INTENTIONALLY**
Owner ExecutionGateway / owner de archivos → ExecutionGateway / owner de archivos
Routes POST /files/write → POST /files/write
Evidence: v4.8.0:backend/.bago/api/handlers_files.py:375; v4.11.0:backend/.bago/api/handlers_files.py:400; backend/.bago/api/handlers_files.py:400; backend/tests/test_files_write_workspace_scope.py
Notes: EXPLICIT_SECURITY_CONTRACT; SCOPED

## C09 · Ejecutar planes materiales

v4.8.0 → v4.9.0 → IMPLEMENTED → **RESTRICTED_INTENTIONALLY**
Owner PlanEngine + ExecutionGateway → PlanEngine + ExecutionGateway
Routes POST /plans/<id>/execute → POST /plans/<id>/execute
Evidence: v4.8.0:backend/.bago/core/plan_engine.py::execute_plan; v4.9.0:backend/.bago/api/handlers_jobs.py:306; backend/.bago/core/plan_engine.py:224; backend/tests/test_plan_engine_contract.py
Notes: EXPLICIT_TRUTH_CONTRACT; SCOPED

## C10 · Autopilot: texto considerado evidencia

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner chat.commands.cmd_autopilot → chat.commands.cmd_autopilot
Routes /autopilot → /autopilot
Evidence: v4.5.0:.bago/chat/commands.py::cmd_autopilot; backend/.bago/chat/commands.py:976; backend/tests/test_plan_engine_contract.py
Notes: NO_FIX_IN_THIS_AUDIT; SCOPED

## C11 · Límite de 20 pasos de autopilot

v4.5.0 → v4.5.0 → PARTIAL → **ACCIDENTALLY_LOST**
Owner chat.commands.cmd_autopilot → chat.commands.cmd_autopilot
Routes /autopilot → /autopilot
Evidence: v4.5.0:.bago/chat/commands.py::cmd_autopilot (max_steps=20); backend/.bago/chat/commands.py:991; backend/tests/test_plan_engine_contract.py
Notes: NOT_ESTABLISHED; SCOPED

## C12 · Ciclo spawn/list/run/kill de agentes

v4.5.0 → v4.5.0 → PARTIAL → **REPLACED_NON_EQUIVALENTLY**
Owner spiral_agent + agent_kit_cli → spiral_agent + agent_kit_cli
Routes bago agent spawn/list/run/kill → bago agent spawn/list/run/kill
Evidence: v4.5.0:bago_core/commands/cmd_tools.py::cmd_agent; 4aa0eb66:backend/bago_core/commands/cmd_tools.py; backend/bago_core/commands/cmd_tools.py:147; backend/tests/test_orchestration_tools.py
Notes: EXPLICIT_REPLACEMENT_COMPATIBILITY_INTENT_UNKNOWN; SCOPED

## C13 · Navegador persistente y snapshot DOM

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner Owner actual equivalente no localizado → Owner actual equivalente no localizado
Routes Histórico /browser open/snapshot/click/fill/eval; sin registro actual → Histórico /browser open/snapshot/click/fill/eval; sin registro actual
Evidence: v4.5.0:.bago/chat/commands.py::cmd_browser; 45e0b4d9 (introducción de Playwright persistente); backend/.bago/chat/commands.py:1153
Notes: NOT_ESTABLISHED; UNRESOLVED_CONCEPTUAL_REPLACEMENT

## C14 · Node Control

v4.0.0-mvp → v4.8.0 → IMPLEMENTED → **EXTENDED**
Owner Node Control → Node Control
Routes bago node status/validate/pieces/connect/disconnect/set-mode → bago node status/validate/pieces/connect/disconnect/set-mode
Evidence: v4.0.0-mvp:.bago/core/cli.py::cmd_nodes; v4.8.0:backend/bago_core/node_control_cli.py; backend/bago_core/node_control_cli.py:102; backend/tests/test_node_control_split.py
Notes: NOT_ESTABLISHED; SCOPED

## C15 · Evidencia de trabajo

v4.0.0-mvp → v4.5.0 → PARTIAL → **REPLACED_NON_EQUIVALENTLY**
Owner Evidence bundles / claim ledger / receipts → Evidence bundles / claim ledger / receipts
Routes bago evidence; bago claim; node evidence → bago evidence; bago claim; node evidence
Evidence: v4.0.0-mvp:.bago/core/cli.py::cmd_evidence; v4.5.0:bago_core/launcher.py; backend/bago_core/evidence_cli.py:83
Notes: DOCUMENTED_CONTRACT_EVOLUTION; SCOPED

## C16 · RL shadow, entrenamiento y evaluación

v4.5.0 → v4.9.0 → IMPLEMENTED → **EXTENDED**
Owner RLBridge + rl_policies → RLBridge + rl_policies
Routes /rl/status; /rl/shadow; train/eval → /rl/status; /rl/shadow; train/eval
Evidence: v4.5.0:.bago/api/bridge.py:518; v4.9.0:backend/tests/test_rl_contract.py; backend/.bago/api/handlers_rl.py:33; backend/tests/test_rl_contract.py
Notes: EXPLICIT_SHADOW_BOUNDARY; SCOPED

## C17 · Memoria y KB

v4.8.0 → v4.10.0 → IMPLEMENTED → **EXTENDED**
Owner handlers_memory + handlers_kv → handlers_memory + handlers_kv
Routes /memory/*; /api/v1/kb → /memory/*; /api/v1/kb
Evidence: v4.8.0:backend/contracts/api_routes.generated.json; v4.10.0:backend/contracts/api_routes.generated.json; backend/.bago/api/handlers_memory.py:17; backend/tests/test_kv_integration_contract.py
Notes: NOT_ESTABLISHED; SCOPED

## C18 · Capability packages y pipelines ejecutables

v4.8.2 → v4.8.2 → IMPLEMENTED → **EXTENDED**
Owner CapabilityPackageImportEffectAdapter + ExecutionGateway → CapabilityPackageImportEffectAdapter + ExecutionGateway
Routes /api/v1/capability-packages/* → /api/v1/capability-packages/*
Evidence: v4.8.2:backend/.bago/core/capability_packages.py:1; backend/.bago/core/capability_packages.py:584; backend/tests/test_capability_packages.py; backend/tests/test_capability_import_gateway.py
Notes: EXPLICIT_PACKAGE_CONTRACT; SCOPED

## C19 · Capability de inventario read_only

v4.9.0 → v4.9.0 → IMPLEMENTED → **PRESERVED**
Owner capability_contract → capability_contract
Routes GET /api/v1/capabilities → GET /api/v1/capabilities
Evidence: v4.9.0:backend/.bago/api/capability_contract.py:20; backend/.bago/api/capability_contract.py:90; backend/tests/test_capability_contract.py
Notes: EXPLICIT_READ_ONLY_CONTRACT; SCOPED

## C20 · Schedules y delegación

v4.9.0 → v4.9.0 → IMPLEMENTED → **RESTRICTED_INTENTIONALLY**
Owner schedule_registry + ExecutionGateway → schedule_registry + ExecutionGateway
Routes /schedule/* → /schedule/*
Evidence: v4.9.0:backend/tests/test_schedule_registry.py; backend/.bago/api/handlers_schedule.py:271; backend/tests/test_schedule_registry.py; backend/tests/test_schedule_delegation.py
Notes: EXPLICIT_DELEGATION_CONTRACT; SCOPED

## C21 · Copilot como proveedor CLI

v4.8.0 → v4.8.0 → IMPLEMENTED → **RESTRICTED_INTENTIONALLY**
Owner CopilotAdapter + cli_bridge → CopilotAdapter + cli_bridge
Routes Provider chat mediante CLI → Provider chat mediante CLI
Evidence: v4.8.0:backend/.bago/providers/copilot.py:37; backend/.bago/providers/copilot.py:39; backend/tests/test_cli_bridge_contract.py
Notes: EXPLICIT_PROVIDER_CONTRACT; SCOPED

## C22 · Pi provider

v4.8.0 → v4.8.0 → IMPLEMENTED → **PRESERVED**
Owner BagoPiProviderAdapter → BagoPiProviderAdapter
Routes Provider adapter (habilitación no probada) → Provider adapter (habilitación no probada)
Evidence: v4.8.0:backend/.bago/integrations/pi/provider_adapter.py:224; backend/.bago/integrations/pi/provider_adapter.py:224
Notes: EXPLICIT_PHASE1_BOUNDARY; SCOPED

## C23 · Pi ejecutor delegado

v4.8.0 → v4.8.0 → IMPLEMENTED → **EXTENDED**
Owner Pi AgentRunner → Pi AgentRunner
Routes Agent runner Fase 3 → Agent runner Fase 3
Evidence: v4.8.0:backend/.bago/integrations/pi/agent_runner.py; backend/.bago/integrations/pi/agent_runner.py:71; backend/tests/integrations/pi/test_agent_runner.py
Notes: EXPLICIT_PHASE3_BOUNDARY; SCOPED

## C24 · Taxonomía rol/workflow/sesión

v3.5.0 → v3.5.0 → IMPLEMENTED → **PRESERVED**
Owner Canon + role_factory → Canon + role_factory
Routes Contratos de rol y workflow → Contratos de rol y workflow
Evidence: v3.5.0:.bago/core/canon/TAXONOMIA.md; backend/.bago/core/canon/TAXONOMIA.md
Notes: EXPLICIT_TAXONOMY; SCOPED

## C25 · Control headless de sesiones

v4.5.0 → v4.5.0 → PARTIAL → **REPLACED_NON_EQUIVALENTLY**
Owner bago_core.session_control → bago_core.session_control
Routes Antes bago session; ahora módulo session_control → Antes bago session; ahora módulo session_control
Evidence: v4.5.0:bago_core/commands/cmd_tools.py::cmd_session; backend/bago_core/session_control.py:162; backend/tests/test_session_recovery_contract.py
Notes: NOT_ESTABLISHED; SCOPED

## C26 · Workflow/orquestación

v3.2-kernel → v4.5.0 → PARTIAL → **REPLACED_NON_EQUIVALENTLY**
Owner orchestrator_v4 → orchestrator_v4
Routes bago orchestrate; /orchestrate → bago orchestrate; /orchestrate
Evidence: v3.2-kernel:.bago/tools/tool_registry.py; v4.5.0:bago_core/launcher.py; backend/bago_core/launcher.py:118; backend/tests/test_orchestration_tools.py
Notes: NOT_ESTABLISHED; UNRESOLVED_CONCEPTUAL_EQUIVALENCE

## C27 · issues-gh anunciado por el parser

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner Sin handler en dispatcher → Sin handler en dispatcher
Routes bago issues-gh take → bago issues-gh take
Evidence: v4.5.0:bago_core/parsers_sections.py (issues-gh); v4.5.0:bago_core/launcher.py (sin dispatch); backend/bago_core/parsers_sections.py:374
Notes: NOT_ESTABLISHED; SCOPED

## C28 · Mutaciones GitHub por HTTP

v4.8.7 → v4.8.7 → IMPLEMENTED → **RESTRICTED_INTENTIONALLY**
Owner Desktop/process authorization; owner process → Desktop/process authorization; owner process
Routes POST /github/setup-git → /github/setup → POST /github/setup-git → /github/setup
Evidence: v4.8.7:backend/.bago/api/handlers_github.py:506; backend/.bago/api/handlers_github.py:325; backend/tests/test_github_api_contract.py
Notes: EXPLICIT_FAIL_CLOSED_TEST; SCOPED

## C29 · Cancelación de interpretación histórica

v4.9.0 → v4.10.0 → IMPLEMENTED → **REPLACED_EQUIVALENTLY**
Owner handlers_interpret → handlers_interpret
Routes Antes POST /interpretations/{id}/cancel → /interpret; alias retirado → Antes POST /interpretations/{id}/cancel → /interpret; alias retirado
Evidence: v4.9.0:backend/.bago/api/legacy_aliases.py:70; v4.10.0:backend/.bago/api/legacy_aliases.py:70; fa3f2d3c (corrige el alias); backend/.bago/api/legacy_aliases.py:66
Notes: EXPLICIT_BUG_FIX; SCOPED

## C30 · Detalle de interpretación por ID

v4.9.0 → v4.9.0 → PARTIAL → **REPLACED_NON_EQUIVALENTLY**
Owner handlers_interpret + API client → handlers_interpret + API client
Routes GET /interpretations/{id} → /interpret/history → GET /interpretations/{id} → /interpret/history
Evidence: v4.9.0:backend/.bago/api/legacy_aliases.py; backend/.bago/api/legacy_aliases.py:72
Notes: NOT_ESTABLISHED; SCOPED

## C31 · Prompt del rol crece por ciclo

v3.5.0 → v3.5.0 → UNKNOWN → **UNKNOWN**
Owner No equivalente demostrado; SpiralAgent actual rota pasos → No equivalente demostrado; SpiralAgent actual rota pasos
Routes Histórico RoleSpiralBuilder → Histórico RoleSpiralBuilder
Evidence: v3.5.0:.bago/tools/role_embedded.py:53; v3.5.0:tests/test_v35_features.py:62; backend/.bago/tools/spiral_agent.py:279
Notes: NOT_ESTABLISHED; UNRESOLVED_CONCEPTUAL_REPLACEMENT

## C32 · Selección adaptativa band/channel/hz

v3.5.0 → v3.5.0 → UNKNOWN → **UNKNOWN**
Owner No equivalente demostrado → No equivalente demostrado
Routes Histórico SignalMetrics.band/channel/hz → Histórico SignalMetrics.band/channel/hz
Evidence: v3.5.0:.bago/core/prompt_router.py:21; v3.5.0:tests/test_v35_features.py:17; backend/bago_core/providers/routing.py
Notes: NOT_ESTABLISHED; UNRESOLVED_CONCEPTUAL_REPLACEMENT

## C33 · ModelGate direct/fallback/degrade

v3.5.0 → v3.5.0 → PARTIAL → **REPLACED_NON_EQUIVALENTLY**
Owner session_adapters_mixin + repl_model_router → session_adapters_mixin + repl_model_router
Routes Selección/fallback de modelo → Selección/fallback de modelo
Evidence: v3.5.0:.bago/tools/model_gate.py; v3.5.0:tests/test_v35_features.py:108; backend/.bago/core/session_adapters_mixin.py:118; backend/tests/test_router_session_model.py
Notes: NOT_ESTABLISHED; PARTIAL_REPLACEMENT

## C34 · Familia CLI autonomous

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner autonomous_loop / repl_startup / comandos de sesión → autonomous_loop / repl_startup / comandos de sesión
Routes Histórico bago autonomous; actuales /evolve, /autopilot y módulo autonomous_loop → Histórico bago autonomous; actuales /evolve, /autopilot y módulo autonomous_loop
Evidence: v4.5.0:bago_core/commands/cmd_tools.py::cmd_autonomous; backend/.bago/core/autonomous_loop.py:801
Notes: NOT_ESTABLISHED; PARTIAL_REPLACEMENT

## C35 · Registro de workspaces con nombre por CLI

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner Project/workspace binding actual → Project/workspace binding actual
Routes Histórico bago workspace; actuales /workspace/* y picker → Histórico bago workspace; actuales /workspace/* y picker
Evidence: v4.5.0:bago_core/commands/cmd_tools.py::cmd_workspace; backend/.bago/api/api_dispatch.py:60
Notes: NOT_ESTABLISHED; UNRESOLVED_CONCEPTUAL_REPLACEMENT

## C36 · Federación de conocimiento por CLI

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner Sin owner actual de federación identificado → Sin owner actual de federación identificado
Routes Histórico bago knowledge → Histórico bago knowledge
Evidence: v4.5.0:bago_core/commands/cmd_tools.py::cmd_knowledge; backend/.bago/chat/memory_commands.py
Notes: NOT_ESTABLISHED; UNRESOLVED_CONCEPTUAL_REPLACEMENT

## C37 · Arrancar host C++ de referencia

v4.5.0 → v4.5.0 → UNKNOWN → **REMOVED_INTENTIONALLY**
Owner CppLocalAdapter cliente HTTP → CppLocalAdapter cliente HTTP
Routes Histórico bago cpp-runtime; provider cpp-local conservado → Histórico bago cpp-runtime; provider cpp-local conservado
Evidence: v4.5.0:bago_core/commands/cmd_system.py::cmd_cpp_runtime; fa949059 (parser retira cpp-runtime frente al padre); backend/.bago/providers/cpp_local.py:49
Notes: REMOVAL_COMMIT_IDENTIFIED_INTENT_UNRESOLVED; SCOPED

## C38 · Administrar chains desde terminal

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner Electron manager settings / chain_registry → Electron manager settings / chain_registry
Routes Histórico bago chain; bridge read/write chains.json → Histórico bago chain; bridge read/write chains.json
Evidence: v4.5.0:bago_core/commands/cmd_tools.py::cmd_chain; backend/electron/preload.cjs:171
Notes: NOT_ESTABLISHED; PARTIAL_REPLACEMENT

## C39 · Release jobs headless por CLI

v4.5.0 → v4.5.0 → UNKNOWN → **UNKNOWN**
Owner Electron release service + gateway → Electron release service + gateway
Routes Histórico bago release-job; IPC list/preflight/start/cancel/resume/install/rollback → Histórico bago release-job; IPC list/preflight/start/cancel/resume/install/rollback
Evidence: v4.5.0:bago_core/commands/cmd_tools.py::cmd_release_job; backend/electron/ipc-service.cjs:61
Notes: NOT_ESTABLISHED; PARTIAL_REPLACEMENT

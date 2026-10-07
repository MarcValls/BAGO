# BAGO · Auditoría histórica de capacidades

Candidato `b9b2eda8f21be16f5ade510b5f069abe09ae5387`; versión de checkout `4.11.3`; árbol dirty preservado.

Freeze lógico: `e5558324b436c03cb6f8470522951b05ff468fd673cfdbdde433c6f557fcf908`; 1893 archivos rastreados o fuentes nuevas relevantes. El alcance y exclusiones están en freeze-before.json.

55 tags locales inspeccionados; 24 con ROUTE_META extraíble; 153 pares método+ruta únicos actuales. No equivalen a número de capacidades.

La matriz contiene familias trazadas manualmente. La reconstrucción semántica global permanece parcial donde se indica equivalencia pendiente; ninguna fila certifica runtime por presencia de fuente.

Clasificaciones de las filas: {'EXTENDED': 9, 'PRESERVED': 7, 'REPLACED': 8, 'RESTRICTED': 5, 'LOST': 10}.

## Hallazgos

### S01 · Agent: mismo nombre de familia, dos registros

4aa0eb66 añade la interceptación list/run/describe/plan; spawn/kill/status siguen en spiral_agent.

Un agente creado por spawn no tiene continuidad de identidad demostrada hacia list/run.

Estado: `CONFIRMED_DISPATCH_SPLIT`. Accidentalidad: CANDIDATE; intención de migración no demostrada.

Verificación propuesta: Probar spawn → list → run → kill con la misma identidad; exigir migración o namespaces explícitos.

### S02 · Autopilot convierte prosa en done

Debilidad presente en v4.5.0; persiste tras introducir vocabulario de evidencia.

done sin receipt material, en contradicción con execute_plan; blocked también devuelve ok=true.

Estado: `FUNCTION_BOUNDARY_REPRODUCED`. Accidentalidad: NO_NEW_OVERWRITE_PROVEN; inconsistencia actual confirmada.

Verificación propuesta: Unificar el criterio de ejecución del handler y motor; negativo con solo texto y sin receipt.

### S03 · Autopilot sin límite histórico de 20 pasos

v4.5.0 limita a 20; snapshot actual recorre todos los pasos.

El probe de 25 pasos produce 25 llamadas de ejecución simulada frente a 20 históricas.

Estado: `FUNCTION_BOUNDARY_REPRODUCED`. Accidentalidad: CANDIDATE; no commit de retirada ni intención atribuidos.

Verificación propuesta: Decidir el límite actual y probar cancelación, error y corte; no restaurar automáticamente una política histórica.

### S04 · issues-gh: comando aceptado, salida 0 sin handler

Presente también en v4.5.0.

Un consumidor puede interpretar éxito aunque solo se imprimió ayuda.

Estado: `FUNCTION_BOUNDARY_REPRODUCED`. Accidentalidad: HISTORICAL_DEFECT_PRESERVED.

Verificación propuesta: Conformidad parser↔dispatcher y código de error para rutas sin implementación.

### S05 · Interpretación por ID devuelve colección

Alias actual reenvía a history; cliente espera InterpretationResult.

Contrato cliente/API incoherente. Callsite UI no encontrado; impacto runtime no probado.

Estado: `SOURCE_TRACED`. Accidentalidad: CANDIDATE; intención no establecida.

Verificación propuesta: Contrato de detalle por ID o retirada explícita del método; probar que el ID se usa.

### S06 · Cancelar interpretación creaba otra interpretación

v4.9/v4.10 alias cancel→interpret; retirado antes de v4.11.0.

Sobrescritura semántica histórica confirmada y corregida; no es una cancelación funcional perdida.

Estado: `CORRECTED_BY_fa3f2d3c`. Accidentalidad: EXPLICIT_BUG_FIX.

Verificación propuesta: Mantener negativa de que cancelar no invoca interpretar; reconciliar método residual del cliente.

### S07 · Inventario read_only confundido con todas las capacidades

Paquetes ejecutables aparecen en v4.8.2; inventario observado en v4.9.0 coexiste con roles/workflows.

Usar un solo endpoint como catálogo del Framework omitiría capacidades históricas reales.

Estado: `INTERPRETATION_RISK_NOT_CODE_OVERWRITE`. Accidentalidad: NO_CODE_OVERWRITE_PROVEN.

Verificación propuesta: Mantener IDs semánticos y distinguir provider, host, paquete, rol, workflow e inventario.

## Matriz

| ID | Capacidad | Clasificación | Owner / ruta | Evidencia |
|---|---|---|---|---|
| C01 | Estado de sesión | EXTENDED (Contrato de consulta) | SessionManager · GET /session; /status; /session | backend/.bago/api/handlers_session.py:20 |
| C02 | Guardar, cargar y recuperar sesión | EXTENDED (Persistencia y binding) | SessionManager + ContextStore · /save; /load; sesiones API | backend/.bago/chat/commands.py:398 |
| C03 | Chat y streaming | EXTENDED (Superficie HTTP y control del turno) | SessionManager.send + chat_turns · POST /chat; POST /chat/stream | backend/.bago/api/handlers_chat.py:115 |
| C04 | Cambiar proveedor/modelo | PRESERVED (Propósito y delegación al owner) | SwitchEngine · POST /switch; /switch; /models | backend/.bago/api/handlers_switch.py:20 |
| C05 | Comandos por HTTP | REPLACED (Ruta con alias de compatibilidad) | chat.commands.execute · POST /command → /api/v1/commands | backend/.bago/api/legacy_aliases.py:55 |
| C06 | Workspace y operaciones de proyecto | REPLACED (Rutas antiguas, owner actual gobernado) | handlers_workspace / ProjectWriteEffectAdapter · /workspaces → /workspace/list; /workspace/{init,link,seed,sync} → /project/* | backend/.bago/api/legacy_aliases.py:49 |
| C07 | Historial y conversaciones | EXTENDED (Persistencia por conversación) | ContextStore · GET /history; /conversations; /workspace/conversation | backend/.bago/api/handlers_conversations.py:15 |
| C08 | Escribir archivos desde API | RESTRICTED (Autorización antes del efecto) | ExecutionGateway / owner de archivos · POST /files/write | backend/.bago/api/handlers_files.py:400 |
| C09 | Ejecutar planes materiales | RESTRICTED (Significado de ejecución exitosa) | PlanEngine + ExecutionGateway · POST /plans/<id>/execute | backend/.bago/core/plan_engine.py:224 |
| C10 | Autopilot: texto considerado evidencia | PRESERVED (Debilidad semántica histórica; no preservación correcta) | chat.commands.cmd_autopilot · /autopilot | backend/.bago/chat/commands.py:976 |
| C11 | Límite de 20 pasos de autopilot | LOST (Garantía del handler al comparar snapshots) | chat.commands.cmd_autopilot · /autopilot | backend/.bago/chat/commands.py:991 |
| C12 | Ciclo spawn/list/run/kill de agentes | REPLACED (Cambio de owner con compatibilidad rota o sin migración demostrada) | spiral_agent + agent_kit_cli · bago agent spawn/list/run/kill | backend/bago_core/commands/cmd_tools.py:147 |
| C13 | Navegador persistente y snapshot DOM | LOST (Interfaz REPL /browser y controller histórico; sustitución conceptual pendiente) | Owner actual equivalente no localizado · Histórico /browser open/snapshot/click/fill/eval; sin registro actual | backend/.bago/chat/commands.py:1153 |
| C14 | Node Control | EXTENDED (Nodos, instalaciones, piezas y conectores) | Node Control · bago node status/validate/pieces/connect/disconnect/set-mode | backend/bago_core/node_control_cli.py:102 |
| C15 | Evidencia de trabajo | REPLACED (Evolución de formato y autoridad) | Evidence bundles / claim ledger / receipts · bago evidence; bago claim; node evidence | backend/bago_core/evidence_cli.py:83 |
| C16 | RL shadow, entrenamiento y evaluación | EXTENDED (Observación y aprendizaje sin autoridad de ejecución) | RLBridge + rl_policies · /rl/status; /rl/shadow; train/eval | backend/.bago/api/handlers_rl.py:33 |
| C17 | Memoria y KB | EXTENDED (Dos servicios con contratos propios) | handlers_memory + handlers_kv · /memory/*; /api/v1/kb | backend/.bago/api/handlers_memory.py:17 |
| C18 | Capability packages y pipelines ejecutables | EXTENDED (Contrato ZIP + entrada ejecutable) | CapabilityPackageImportEffectAdapter + ExecutionGateway · /api/v1/capability-packages/* | backend/.bago/core/capability_packages.py:584 |
| C19 | Capability de inventario read_only | PRESERVED (bago-runtime-inventory, no censo de todo el producto) | capability_contract · GET /api/v1/capabilities | backend/.bago/api/capability_contract.py:90 |
| C20 | Schedules y delegación | RESTRICTED (Autorización de ejecuciones diferidas) | schedule_registry + ExecutionGateway · /schedule/* | backend/.bago/api/handlers_schedule.py:271 |
| C21 | Copilot como proveedor CLI | RESTRICTED (Transporte LLM y herramientas del proveedor) | CopilotAdapter + cli_bridge · Provider chat mediante CLI | backend/.bago/providers/copilot.py:39 |
| C22 | Pi provider | PRESERVED (Fase 1 sin tools, desactivada por defecto) | BagoPiProviderAdapter · Provider adapter (habilitación no probada) | backend/.bago/integrations/pi/provider_adapter.py:224 |
| C23 | Pi ejecutor delegado | EXTENDED (Contrato de ejecución separado del provider) | Pi AgentRunner · Agent runner Fase 3 | backend/.bago/integrations/pi/agent_runner.py:71 |
| C24 | Taxonomía rol/workflow/sesión | PRESERVED (Contrato documental, runtime no reconstruido por completo) | Canon + role_factory · Contratos de rol y workflow | backend/.bago/core/canon/TAXONOMIA.md |
| C25 | Control headless de sesiones | REPLACED (Alias CLI retirado, módulo alternativo conservado) | bago_core.session_control · Antes bago session; ahora módulo session_control | backend/bago_core/session_control.py:162 |
| C26 | Workflow/orquestación | REPLACED (Interfaz y modelo de workflow; equivalencia incompleta) | orchestrator_v4 · bago orchestrate; /orchestrate | backend/bago_core/launcher.py:118 |
| C27 | issues-gh anunciado por el parser | PRESERVED (Defecto histórico, no capacidad funcional probada) | Sin handler en dispatcher · bago issues-gh take | backend/bago_core/parsers_sections.py:374 |
| C28 | Mutaciones GitHub por HTTP | RESTRICTED (Facades antiguas devuelven 410) | Desktop/process authorization; owner process · POST /github/setup-git → /github/setup | backend/.bago/api/handlers_github.py:325 |
| C29 | Cancelación de interpretación histórica | REPLACED (Corrección de alias semánticamente falso) | handlers_interpret · Antes POST /interpretations/{id}/cancel → /interpret; alias retirado | backend/.bago/api/legacy_aliases.py:66 |
| C30 | Detalle de interpretación por ID | PRESERVED (Incompatibilidad residual entre alias y cliente) | handlers_interpret + API client · GET /interpretations/{id} → /interpret/history | backend/.bago/api/legacy_aliases.py:72 |
| C31 | Prompt del rol crece por ciclo | LOST (Implementación exacta RoleSpiralBuilder; concepto por resolver) | No equivalente demostrado; SpiralAgent actual rota pasos · Histórico RoleSpiralBuilder | backend/.bago/tools/spiral_agent.py:279 |
| C32 | Selección adaptativa band/channel/hz | LOST (Implementación SignalMetrics; concepto por resolver) | No equivalente demostrado · Histórico SignalMetrics.band/channel/hz | backend/bago_core/providers/routing.py |
| C33 | ModelGate direct/fallback/degrade | REPLACED (Reemplazo conceptual parcial; garantías sin equivalencia probada) | session_adapters_mixin + repl_model_router · Selección/fallback de modelo | backend/.bago/core/session_adapters_mixin.py:118 |
| C34 | Familia CLI autonomous | LOST (Interfaz pública completa; comportamientos parciales conservados) | autonomous_loop / repl_startup / comandos de sesión · Histórico bago autonomous; actuales /evolve, /autopilot y módulo autonomous_loop | backend/.bago/core/autonomous_loop.py:801 |
| C35 | Registro de workspaces con nombre por CLI | LOST (Interfaz named add/remove/select/list/status) | Project/workspace binding actual · Histórico bago workspace; actuales /workspace/* y picker | backend/.bago/api/api_dispatch.py:60 |
| C36 | Federación de conocimiento por CLI | LOST (Interfaz knowledge source-list/add/remove/pull/pull-all) | Sin owner actual de federación identificado · Histórico bago knowledge | backend/.bago/chat/memory_commands.py |
| C37 | Arrancar host C++ de referencia | LOST (Launcher cpp-runtime; el adapter cliente permanece) | CppLocalAdapter cliente HTTP · Histórico bago cpp-runtime; provider cpp-local conservado | backend/.bago/providers/cpp_local.py:49 |
| C38 | Administrar chains desde terminal | LOST (Interfaz CLI; persistencia Electron conservada) | Electron manager settings / chain_registry · Histórico bago chain; bridge read/write chains.json | backend/electron/preload.cjs:171 |
| C39 | Release jobs headless por CLI | LOST (Interfaz de terminal; operaciones de release conservadas en otras superficies) | Electron release service + gateway · Histórico bago release-job; IPC list/preflight/start/cancel/resume/install/rollback | backend/electron/ipc-service.cjs:61 |

## Límites y puerta previa a la separación del Framework

- Live execution of each public route and external CLI host is NOT_RUN.
- Legacy registry/inline surfaces before ROUTE_META have manual family traces, not exhaustive automatic enumeration.
- Conceptual replacement for v3 prompt-cycle and SignalMetrics remains unresolved.
- All local tags inspected as objects; remote publication state is outside this audit.
- Migration of old saved state formats and full v3 workflow semantics not demonstrated.

La siguiente fase debe resolver continuidad agent spawn/list/run, semántica autopilot y pérdidas históricas por interfaz antes de mover owners. Los probes de DOM históricos deben revisarse como antecedentes; no se reactivan por encontrar su código.

Reproducción: `python collect.py freeze` solo crea el freeze inicial; `python collect.py collect`, `python probe_semantics.py`, `python collect.py check`, `python build_report.py`. Ejecutar desde este directorio o pasar la ruta completa. No sobrescribir el freeze original.

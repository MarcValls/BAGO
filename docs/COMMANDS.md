# BAGO — Command Reference

> **Auto-generated** from `tool_registry.py`. Do not edit manually.
> Last generated: 2026-05-18 16:12 UTC
>
> Source of truth: `.bago/tools/tool_registry.py`
> Generator: `.bago/tools/generate_commands_doc.py`

## Summary

| Bucket | Count |
|--------|-------|
| ⚙️ Core | 39 |
| 🧪 Experimental | 80 |
| ⚠️ Dangerous | 8 |
| 🗄️ Legacy (deprecated) | 28 |
| **Total active** | **127** |

---

## ⚙️ Core

Stable commands. Pre-flight **required**. Always available.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago advisor` | Advisor LLM adaptativo: ask\|next\|explain\|run\|context\|rubber-duck — orientación continua con modelo pequeño local | • generacion | safe | required |
| `bago ask` | Router lenguaje natural → tools BAGO | • consumo | safe | required |
| `bago audit` | Auditoría y calidad: full \| pack \| scan \| commit \| push \| doctor \| heal \| quality \| purity | • memoria | safe | required |
| `bago context` | Contexto del workspace: detect \| map \| git \| stale | • consumo | safe | required |
| `bago dashboard` | Muestra el dashboard del pack | • memoria | safe | required |
| `bago devmode` | Alterna entre modo usuario (project-first) y modo desarrollador (framework-visible). Subcomandos: --enable \| --disable \| --status \| --info | • memoria | safe | required |
| `bago diff` | Muestra ficheros modificados entre las últimas sesiones BAGO | • consumo | safe | required |
| `bago doc-agent` | Agente de documentación: detecta y actualiza COMMANDS.md, LAYERS.md y README.md. Subcomandos/flags: --check \| --dry-run \| --json \| --only <doc> \| --no-stage | • generacion | mutating | required |
| `bago docs` | Genera docs/COMMANDS.md desde tool_registry.py (fuente única de verdad) | • generacion | safe | required |
| `bago flow` | Flowchart ASCII de workflows + gestión de estado activo (start/done/status) | • motor | safe | required |
| `bago goals` | Gestor de objetivos del pack con seguimiento de progreso | • memoria | safe | required |
| `bago health` | Salud del framework: score \| report \| stability \| efficiency \| consistency \| sincerity | • memoria | safe | required |
| `bago ideas` | Emite ideas W2 | • memoria | safe | required |
| `bago launch` | BAGO — interfaz conversacional principal. El usuario habla con BAGO; BAGO orquesta todos los agentes y modelos internamente. Escalado automático: local → local-grande → cloud según contexto. Uso: bago launch  \|  --provider <p>  \|  --model <m>  \|  --task <tarea> | • dominio | safe | required |
| `bago menu` | Menú interactivo jerárquico de comandos BAGO (curses). Sidebar de 10 grupos por flujo de trabajo + lista + preview. Uso: bago menu  \|  bago menu --list  (no interactivo) | • motor | safe | required |
| `bago next` | Meta-comando de ciclo mínimo: elige idea + acepta + inicia flujo en un paso | • motor | safe | required |
| `bago orphans` | Detector de módulos huérfanos: archivos .py en tools/ sin registro. --baseline \| --fix \| --strict | • consumo | safe | required |
| `bago pack-cache` | Cache híbrida pack.json -> bago.db (sync \| check \| status) | • infraestructura | safe | required |
| `bago project` | Memoria distribuida por proyecto: init \| link \| unlink \| state \| learn \| promote | • memoria | safe | required |
| `bago recent-projects` | Historial de proyectos BAGO recientes: repos visitados, ideas implementadas, sesiones. Se alimenta automáticamente al arrancar. Uso: bago recent-projects  \|  uso interno: --record | • memoria | safe | required |
| `bago review` | Code review automatizado fail-closed con estado explícito por scanner | • generacion | safe | required |
| `bago risk` | Matriz de riesgo del proyecto — evalúa impacto y probabilidad | • memoria | safe | required |
| `bago route` | Router hibrido balanceado/adaptativo: decide entre Ollama local, Codex y Copilot | • motor | safe | required |
| `bago scope` | Detecta scope (framework/project/both) de scripts Python por análisis estático | • consumo | safe | required |
| `bago secrets` | Escanea el repositorio buscando secretos y credenciales expuestas | • consumo | safe | required |
| `bago self` | BAGO Self-Repair — BAGO se centra en sí mismo y repara sus propios fallos. Dos modos: autoreparación (--auto) y manual (menú interactivo). Uso: bago self \| --auto \| --list \| --regenerate \| --error 'descripción' | • motor | safe | required |
| `bago session` | Ciclo de sesión: open \| close \| harvest \| v2 | • memoria | safe | required |
| `bago setup` | Wizard de configuración inicial: notificaciones (Telegram/WhatsApp/ntfy), git hooks. --check \| --reset \| --clean-history | • generacion | safe | required |
| `bago snapshot` | Compara dos snapshots de estado BAGO: diferencias en tools, ideas e inventario. | • memoria | safe | required |
| `bago sprint` | Gestor de sprints BAGO — crear, listar, cerrar sprints de trabajo | • memoria | safe | required |
| `bago status` | Estado actual: flujo activo, tarea pendiente y salud del sistema | • memoria | safe | required |
| `bago supervision` | BAGO Supervision Layer — capa de guardianes sistémicos. Convierte fallos recurrentes en agentes con memoria, artefacto y contrato. Subcomandos: run [--loop pre_release\|post_test_cleanup\|legacy_decay\|contract_drift] \| status \| check <agente> \| report [--json] [--loop] | 🔍 calidad | safe | required |
| `bago sync` | Regenera TREE.txt y CHECKSUMS | • memoria | safe | required |
| `bago task` | Muestra la tarea W2 pendiente. --done \| --assign <agente> \| --clear | • memoria | safe | required |
| `bago validate` | Verifica el pack (manifiesto, estado, roles, ZIP) — subcomandos: manifest, state, contents | • memoria | safe | required |
| `bago version` | Gestión de versiones beta/release: bump \| beta \| release \| tag \| commit \| sync-check | • memoria | mutating | required |
| `bago why` | Explica qué hace un comando BAGO, cuándo usarlo y sus relaciones | • generacion | safe | required |
| `bago workflow` | Selector de workflow (interactivo) | • motor | safe | required |
| `bago workspace-select` | Selector de espacio de trabajo: elige entre framework (self), directorio padre o ruta/repo externo. Persiste en repo_context.json. Se invoca automáticamente al arrancar si no hay workspace configurado. Uso: bago workspace-select  \|  opciones: --json --plain | • memoria | safe | required |

---

## 🧪 Experimental

Actively developed. May change between minor versions.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago ableton-template` | Genera un scaffold de proyecto Ableton techno 4/4 | • dominio | safe | optional |
| `bago agent` | Multi-Agent Gateway: dispatch \| list \| status — orquesta herramientas BAGO desde cualquier agente externo (local, Ollama, MCP/Claude, Codex, cloud). Adapters: local \| ollama \| mcp \| codex \| cloud | • motor | safe | optional |
| `bago agent-config` | Configurador de agentes BAGO: TUI interactivo (Agentes, Habilidades, Instrucciones, MCP, Complementos) | • motor | safe | optional |
| `bago alias-manager` | Crea y ejecuta atajos de comandos bago personalizados. Los alias se guardan en .bago/state/bago_aliases.json. Subcomandos: --list \| --set <nombre> <cmd> \| --run <nombre> \| --del <nombre> \| --show <nombre> | • motor | safe | optional |
| `bago artifact-counter` | Mide y reporta la producción de artefactos útiles por sesión. Excluye artefactos de protocolo (sessions, changes, evidences). Útil para ver la velocidad real de entrega por sesión. | • memoria | safe | optional |
| `bago assign` | Asigna tareas a agentes/roles. list-agents \| assign <id> <agente> \| pending \| assigned | • motor | safe | optional |
| `bago autonomy` | Reconciliación automática del flujo activo: aplica pasos seguros sin permiso, reporta el resto. | • motor | mutating | optional |
| `bago benchmark` | Banco de pruebas de eficiencia BAGO (10 min). --duration N \| --suite fast\|full \| --json | • memoria | safe | optional |
| `bago boot` | BAGO Boot Examiner — Arranca BAGO de forma examinada: detecta proyecto, escanea campo de modelos, verifica safeguards y fabrica frases-operador. Uso: bago boot [examine\|status\|phrases] | • motor | safe | required |
| `bago build-clean` | Elimina node_modules/dist/build para liberar espacio en disco. Dry-run por defecto. | • generacion | mutating | optional |
| `bago build-run` | Ejecuta el proceso de build de las apps del proyecto (server, web, electron, raíz). | • motor | safe | optional |
| `bago canon` | Bucle de Shepard: 4 modos x 3 voces · DETECT→DIAGNOSE→VERIFY→EVOLVE. Orquesta el ciclo completo de salud del framework. Modos: MODULAR (monolitos), SCAN (huerfanos/doc), CREATE (integracion), EVOLVE (lecciones). Uso: bago canon [--mode M] [--voice N] [--loop] [--json] | • motor | safe | optional |
| `bago chronicle` | Sesión Chronicle integrando Copilot CLI /chronicle — historial de sesiones y recomendaciones | • memoria | safe | optional |
| `bago code-metrics` | Métricas de código: líneas de código, conteo de archivos y tipos por app. Excluye node_modules, dist, build y archivos de lock. Soporta filtros de extensión y configuración via bago_config. | • consumo | safe | optional |
| `bago code-search` | Busca texto o patrones en el código fuente del proyecto. Sin dependencias externas. Excluye node_modules/dist/build. Subcomandos: --regex \| -i (case-insensitive) \| --ext ts,py \| --files \| --count | • consumo | safe | optional |
| `bago config-check` | Valida integridad de configs JSON en state/config/ y cruza con registry | • consumo | safe | optional |
| `bago create` | BAGO modo creación: layout 3 paneles tipo Copilot. Panel izquierdo: sesiones + personalizaciones. Panel central: área de trabajo + input hito. Panel derecho: cambios git / archivos. Flags: --once (render único) \| --tab cambios\|archivos | • motor | safe | optional |
| `bago deactivate` | Crea un archivo comprimido de desactivación y lo oculta en Windows | • generacion | mutating | optional |
| `bago debt` | Ledger de deuda técnica — registra, prioriza y hace seguimiento | • memoria | safe | optional |
| `bago deps` | Auditoría de dependencias (requirements/pyproject) | • consumo | safe | optional |
| `bago doc-index` | Índice reverso de cobertura documental: qué documentos en docs/ cubren qué herramientas. Detecta tools sin documentar y permite añadir anotaciones @covers a los .md. | • consumo | safe | optional |
| `bago env-manager` | Gestión de archivos de entorno (.env) del proyecto. Shim de compatibilidad para env.py. Subcomandos: list [-v] \| table \| diff [app] \| check \| set <app> KEY=value \| setup | • consumo | mutating | optional |
| `bago field` | BAGO Field — Escáner del campo magnético de modelos/providers. Detecta disponibilidad, genera matriz de campo y gestiona bago-local. Uso: bago field [scan\|status\|pull <model>\|calibrate <model>] | • motor | safe | required |
| `bago find-tool` | Busca la herramienta BAGO adecuada para un problema | • consumo | safe | optional |
| `bago focus-mode` | Muestra la tarea activa en modo enfoque minimalista. Diseñado para mostrar en un corner de pantalla o en el prompt. Subcomandos: --compact (una línea) \| --watch (refresca 30s) \| --clear | • memoria | safe | optional |
| `bago gateway` | Messaging gateway unificado: WhatsApp, Telegram, Signal, Email, ntfy, Utopia P2P | • motor | safe | optional |
| `bago git-status` | Resumen compacto del estado de git del proyecto activo. Usa comandos git estándar. Funciona en cualquier repositorio git. Subcomandos: --log N (últimos N commits) \| --short (una línea) \| --diff | • consumo | safe | optional |
| `bago habit` | Detecta hábitos de trabajo positivos y mejorables desde patrones de sesiones | • memoria | safe | optional |
| `bago hardcode` | Detecta datos hardcodeados que deberían ser dinámicos (rutas, intérpretes, versiones, puertos) | • consumo | safe | optional |
| `bago heal-paths` | Detecta y repara rutas rotas tras reorganizaciones. Memoria persistente en state/. | • generacion | safe | optional |
| `bago html-export` | Genera un informe HTML autocontenido del proyecto BAGO. Incluye ideas implementadas, herramientas, métricas por semana y estado. Subcomandos: --out DIR \| --open (abre en navegador tras generar) | • generacion | safe | optional |
| `bago image-studio` | Generador de assets visuales coherentes (sprites, botones, fondos, iconos, tiles, banners) con perfil de proyecto | • dominio | safe | optional |
| `bago image_gen` | Generador de imagenes PNG local sin API | • dominio | safe | optional |
| `bago inbox` | Inbox de tareas autónomas: add <intent> \| list \| clear | • consumo | safe | optional |
| `bago insights` | Análisis de patrones e insights del historial de sesiones BAGO | • memoria | safe | optional |
| `bago lint-runner` | Ejecuta el linter en las apps del proyecto y agrega resultados. Detecta scripts lint/typecheck en cada package.json. Subcomandos: --app <nombre> \| --type (typecheck) \| --fix \| --list | • consumo | mutating | optional |
| `bago llm` | Motor LLM local offline: modelos GGUF en pendrive via Ollama (macOS/Linux/Windows) | • motor | safe | optional |
| `bago llm-node` | Nodo LLM del Neural Bus: escucha llm.request, llama a Ollama con streaming, emite llm.chunk + llm.response. Modos: chat\|tool_suggest\|classify_intent | • motor | safe | optional |
| `bago log-viewer` | Visor de logs en tiempo real para apps del monorepo. Detecta severidad (ERROR/WARN/INFO) y colorea la salida. Lee la ruta del proyecto desde global_state.json. | • consumo | safe | optional |
| `bago lsp` | Orquestación de Language Servers — registra y gestiona servidores LSP para inteligencia de código | • motor | safe | optional |
| `bago music` | Pipeline musical (MarcValls/BAGO_MUSIC_PIPELINE): plan \| convert \| transpose \| validate \| render \| run | • dominio | safe | optional |
| `bago music-saas` | CLI para BAGO Music SaaS — status, dev server, Telegram webhook, GitHub Actions build | • dominio | safe | optional |
| `bago naming` | Lint de convenciones de nombres | • consumo | safe | optional |
| `bago net-scan` | Escáner de red: detecta adaptadores, estado de cable, velocidad y vecinos ARP. Útil para diagnóstico de conectividad local. Subcomandos: --scan (ARP de red local) \| --watch (monitoriza cambios) \| --adapters | • consumo | mutating | optional |
| `bago neural` | Neural Bus — servidor SSE de mensajes inter-agente (start/stop/status/nodes/map) | • motor | safe | optional |
| `bago neural-toolbox` | Motor de activación dinámica de herramientas: convierte contexto en lenguaje natural en un toolbox adaptado. Perfiles derivados del registry, filtros scope/risk, feedback adaptativo. Subcomandos: --context \| --run \| --explain \| --json \| --dry-run | • motor | safe | optional |
| `bago notify-bago` | Notificación BAGO universal: whatsapp (Green API), telegram, desktop. | • generacion | safe | optional |
| `bago notify-desktop` | Envía notificaciones de escritorio (Windows toast via BurntToast PowerShell). | • generacion | safe | optional |
| `bago notify-whatsapp` | Notificación BAGO vía WhatsApp usando CallMeBot API. | • generacion | safe | optional |
| `bago npath` | Neural Path — grafo cognitivo versionado: branch/commit/merge/unmerge/split/recall/map | • memoria | safe | optional |
| `bago orphan-shield` | Detecta 4 tipos de huérfanos: archivos .py no registrados, entradas de registry sin archivo, comandos del router sin registry y tools sin cobertura documental. | • consumo | safe | optional |
| `bago personality-panel` | Panel de personalidad y configuración de agentes BAGO. Gestiona el perfil de personalidad del usuario en user_personality_profile.json. Configura estilo, idioma y vocabulario preferido de los agentes. | • generacion | safe | optional |
| `bago ping-server` | Verifica que el servidor local responde vía HTTP. Muestra status, latencia y errores. Lee la URL desde apps/server/.env. Subcomandos: --url <URL> \| --path <endpoint> \| --watch (ping cada 5s) | • consumo | safe | optional |
| `bago placeholder_scan` | Detecta placeholders y datos ficticios en código Python (FAKE_DATE, STUB_RAISE, ELLIPSIS_BODY, TODO_COMMENT, PLACEHOLDER_STR) | • consumo | safe | optional |
| `bago preflight-check` | Pre-flight checks declarativos para herramientas BAGO: file/env/cmd conditions. | • consumo | safe | optional |
| `bago project-summary` | Dashboard ejecutivo del proyecto: ideas implementadas, herramientas, tamaño en disco, estado de git y todos pendientes. Fuente única de verdad para el estado actual del proyecto. | • memoria | safe | optional |
| `bago recientes` | Bitácora paginada de últimos trabajos: sesiones, sprints, ideas, cierres y commits ordenados cronológicamente | • memoria | safe | optional |
| `bago reopen` | Reanuda sesión desde el último cierre sin reconstruir contexto manualmente | • memoria | safe | optional |
| `bago repo` | Gestión de repositorios: clone \| list \| switch | • consumo | safe | optional |
| `bago research` | Modo Research integrando GitHub Copilot CLI /research — investigación temática estructurada | • generacion | safe | optional |
| `bago rubber-duck` | Rubber duck debugging automático: repite qué hace el código, detecta pasos faltantes e inconsistencias — auto-trigger en toolsmith create | • generacion | safe | optional |
| `bago rules` | Catálogo de reglas BAGO | • generacion | safe | optional |
| `bago safeguard` | BAGO Safeguard Panel — Gestiona los 4 genes de protección del sistema: identity, safety_contract, kill_switch_policy, project_boundary. Uso: bago safeguard [status\|explain <gene>\|set <gene> <state>\|history] | • motor | mutating | required |
| `bago script-runner` | Ejecuta cualquier script npm/pnpm del workspace del monorepo. Detecta scripts en root y apps/*/package.json. Lee el proyecto activo desde global_state.json. | • motor | mutating | optional |
| `bago search-history` | Busca en el historial de ideas implementadas. Sin argumentos muestra las últimas 10 ideas. Uso: bago search-history <término> [término2 ...] | • consumo | safe | optional |
| `bago seed` | BAGO Seed — planta la huella mínima de BAGO en un proyecto externo: crea .bago/pack.json + state/ + launcher y registra la siembra. Subcomandos: [path] \| --name \| --dry-run \| --list \| --status | • generacion | mutating | optional |
| `bago select` | Selector interactivo de ideas por slot con plan de implementación | • motor | safe | optional |
| `bago siembra` | Gestión de siembras BAGO v3.0: create \| list \| update \| diff \| sync \| status | • memoria | mutating | optional |
| `bago size-check` | Detecta archivos .py en .bago/tools/ con más de 400 líneas y los reporta como monolitos candidatos a dividir. | • consumo | safe | optional |
| `bago skill` | Skill Layer (Fractal AGI nivel-2): mini-spirals de 3-6 pasos. list \| run <id> \| status | • motor | safe | optional |
| `bago spanish` | Detecta inconsistencias ortográficas en español: tildes y singular/plural en claves y rutas | • consumo | safe | optional |
| `bago spiral-agent` | Agent Layer (Fractal AGI nivel-1): BagoAgents con skills dinámicas. spawn \| list \| run <id> \| kill \| status | • motor | safe | optional |
| `bago sprite-studio` | Generador de sprites BIANCA via Codex/HF sin API key, con galería browser | • dominio | safe | optional |
| `bago state-manager` | API unificada para el estado BAGO: health, sprint y knowledge. Gestiona global_state.json y ficheros divididos (health.json, sprint.json, knowledge_index.json). Subcomandos: --status \| --materialize \| --split \| --read <sección> \| --test | • memoria | mutating | optional |
| `bago template-gen` | Genera archivos de proyecto desde plantillas predefinidas (component, hook, api-route, test, etc.). Variables: {{PROJECT}}, {{APP}}, {{NAME}}, {{DATE}}, {{AUTHOR}}. Subcomandos: --list \| --show <nombre> \| --add <nombre> \| --out <dir> | • generacion | mutating | optional |
| `bago toolsmith` | Agente dinámico de toolboxes: assign\|sprint\|agent\|missing\|create\|catalog\|listen — asigna cajas de herramientas por tarea y crea tools faltantes | • motor | safe | optional |
| `bago types` | Chequeo de tipos estáticos | • consumo | safe | optional |
| `bago weekly-report` | Informe semanal de actividad BAGO: ideas implementadas, sesiones y velocidad. Por defecto últimos 7 días. Genera resumen Markdown. Subcomandos: --days N \| --save (guarda en .bago/state/reports/) | • memoria | safe | optional |
| `bago work_matrix` | Matriz de rutas de trabajo: qué agente y herramientas MCP usar según el tipo de tarea | • memoria | safe | optional |
| `bago workflow-navigator` | Navegador de workflows BAGO: sugiere el workflow más adecuado dado el contexto actual. Lee WORKFLOW_GRAPH.json y el estado del sistema. Subcomandos: --from <workflow> \| --list \| --graph \| --test | • motor | safe | optional |

---

## ⚠️ Dangerous

High-impact commands. Require `--yes` or `--unsafe`; `--dry-run` is accepted only when declared by the command.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago auto` | Modo automático: evalúa y actúa. --loop para bucle, --infinite para sin límite (Ctrl+C) | • motor | **dangerous** | optional |
| `bago autonomous` | Loop autónomo BAGO: SENSE→PLAN→ACT→OBSERVE→LEARN→DECIDE [--dry-run] [--loop] [--unsafe] | • motor | **dangerous** | optional |
| `bago cabinet` | Gabinete BAGO: orquesta agentes en paralelo e informa unificado | • motor | **dangerous** | optional |
| `bago db` | Gestiona bago.db: estado de ideas, historial guardian, init/status/reset | • motor | **dangerous** | optional |
| `bago install` | Auto-lanzamiento al insertar el pendrive (macOS/Linux/Windows/Android/iPad) | • motor | **dangerous** | optional |
| `bago orchestrate` | Orquestador de workflows multi-tool en secuencia con condiciones | • motor | **dangerous** | optional |
| `bago peer` | Comunicacion peer-to-peer LAN (serve/discover/ping/send/chat) | • motor | **dangerous** | optional |
| `bago spiral` | Bucle espiral cromático (Shepard Loop): 12 pasos de auto-redescrición AGI. --execute para actuar, --status, --history | • motor | **dangerous** | optional |

---

## 🗄️ Legacy

Deprecated. Use the indicated replacement instead.

| Command | Use instead | Description |
|---------|-------------|-------------|
| `bago check` | `bago audit purity` | Chequeo estático de pureza |
| `bago code-quality` | `bago audit quality` | Orquestador de calidad de código — ejecuta agentes especializados |
| `bago commit` | `bago audit commit` | Evaluación de preparación para commit |
| `bago consistency` | `bago health consistency` | Guard anti-drift: valida CI, preflight, README y badge del framework |
| `bago cosecha` | `bago session harvest` | Cosecha de artefactos del proyecto |
| `bago detector` | `bago context detect` | Detector de contexto del repo |
| `bago doctor` | `bago audit doctor` | Diagnóstico completo del entorno BAGO: Python, Git, Ollama, modelo LLM, espacio |
| `bago efficiency` | `bago health efficiency` | Medidor de eficiencia inter-versiones |
| `bago git` | `bago context git` | Contexto git (log/diff/brief) para workflows |
| `bago heal` | `bago audit heal` | Auto-detecta y repara problemas del framework de forma segura y trazable |
| `bago learn` | `bago project learn` | Guarda un aprendizaje en learnings.md del proyecto vinculado |
| `bago map` | `bago context map` | Mapa de contexto del repositorio |
| `bago pre-push` | `bago audit push` | Gate de sincronizacion remota: bloquea pushes con BAGO roto |
| `bago project-init` | `bago project init` | Inicializa .bago/ local en el directorio del proyecto actual |
| `bago project-link` | `bago project link` | Vincula el proyecto al framework (sesiones se guardan en el proyecto) |
| `bago project-state` | `bago project state` | Muestra el estado del proyecto actualmente vinculado |
| `bago project-unlink` | `bago project unlink` | Desvincula el proyecto — sesiones vuelven al framework |
| `bago promote` | `bago project promote` | Promueve un aprendizaje del proyecto al knowledge del framework |
| `bago repo-clone` | `bago repo clone` | Clona repositorios GitHub en workspace con auto-BAGO setup |
| `bago repo-list` | `bago repo list` | Lista repositorios clonados en workspace con estado |
| `bago repo-switch` | `bago repo switch` | Cambia contexto activo entre repositorios del workspace |
| `bago report` | `bago health report` | Health report en Markdown |
| `bago scan` | `bago audit scan` | Escaneo de calidad de código: hallazgos, severidad, autofixable |
| `bago session_close` | `bago session close` | Genera el informe de cierre de sesion BAGO |
| `bago sincerity` | `bago health sincerity` | Centinela de sinceridad: detecta sincofancía en docs .md |
| `bago stability` | `bago health stability` | Resumen de estabilidad del pack |
| `bago stale` | `bago context stale` | Detecta tools obsoletas o sin mantenimiento |
| `bago v2` | `bago session v2` | Checklist de cierre v2 |

---

## Notes

- **Policy** — preflight enforcement: `required` (always runs) · `optional` (skipped with `--skip-preflight`) · `none`
- **Risk** — `safe` (read-only) · `mutating` (writes state) · `**dangerous**` (destructive or high-impact, needs `--yes` or `--unsafe`)
- **Legacy** commands still execute but print a deprecation hint. They will be removed in v4.0.
- Run `bago help <cmd>` for per-command usage.

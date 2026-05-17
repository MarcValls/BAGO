# BAGO — Command Reference

> **Auto-generated** from `tool_registry.py`. Do not edit manually.
> Last generated: 2026-05-16 17:15 UTC
>
> Source of truth: `.bago/tools/tool_registry.py`
> Generator: `.bago/tools/generate_commands_doc.py`

## Summary

| Bucket | Count |
|--------|-------|
| ⚙️ Core | 20 |
| 🧪 Experimental | 89 |
| ⚠️ Dangerous | 8 |
| 🗄️ Legacy (deprecated) | 28 |
| **Total active** | **117** |

---

## ⚙️ Core

Stable commands. Pre-flight **required**. Always available.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago audit` | AuditorÃ­a y calidad: full \| pack \| scan \| commit \| push \| doctor \| heal \| quality \| purity | 💚 salud | safe | required |
| `bago context` | Contexto del workspace: detect \| map \| git \| stale | 💚 salud | safe | required |
| `bago devmode` | Alterna entre modo usuario (project-first) y modo desarrollador (framework-visible). Subcomandos: --enable \| --disable \| --status \| --info | • configuraciÃ³n | safe | required |
| `bago doc-agent` | Agente de documentaciÃ³n: detecta y actualiza COMMANDS.md, LAYERS.md y README.md. Subcomandos/flags: --check \| --dry-run \| --json \| --only <doc> \| --no-stage | 🔍 calidad | mutating | required |
| `bago flow` | Flowchart ASCII de workflows + gestiÃ³n de estado activo (start/done/status) | ▶️ ejecución | safe | required |
| `bago health` | Salud del framework: score \| report \| stability \| efficiency \| consistency \| sincerity | 💚 salud | safe | required |
| `bago launch` | BAGO — interfaz conversacional principal. El usuario habla con BAGO; BAGO orquesta todos los agentes y modelos internamente. Escalado automático: local → local-grande → cloud según contexto. Uso: bago launch  \|  --provider <p>  \|  --model <m>  \|  --task <tarea> | • interfaz | safe | required |
| `bago menu` | MenÃº interactivo jerÃ¡rquico de comandos BAGO (curses). Sidebar de 10 grupos por flujo de trabajo + lista + preview. Uso: bago menu  \|  bago menu --list  (no interactivo) | • ejecuciÃ³n | safe | required |
| `bago orphans` | Detector de mÃ³dulos huÃ©rfanos: archivos .py en tools/ sin registro. --baseline \| --fix \| --strict | 🔬 avanzado | safe | required |
| `bago project` | Memoria distribuida por proyecto: init \| link \| unlink \| state \| learn \| promote | 💚 salud | safe | required |
| `bago recent-projects` | Historial de proyectos BAGO recientes: repos visitados, ideas implementadas, sesiones. Se alimenta automÃ¡ticamente al arrancar. Uso: bago recent-projects  \|  uso interno: --record | • configuraciÃ³n | safe | required |
| `bago scope` | Detecta scope (framework/project/both) de scripts Python por anÃ¡lisis estÃ¡tico | 💚 salud | safe | required |
| `bago secrets` | Escanea el repositorio buscando secretos y credenciales expuestas | 🔍 calidad | safe | required |
| `bago session` | Ciclo de sesiÃ³n: open \| close \| harvest \| v2 | ▶️ ejecución | safe | required |
| `bago setup` | Wizard de configuraciÃ³n inicial: notificaciones (Telegram/WhatsApp/ntfy), git hooks. --check \| --reset \| --clean-history | 🔬 avanzado | safe | required |
| `bago status` | Estado actual: flujo activo, tarea pendiente y salud del sistema | 📊 analítica | safe | required |
| `bago sync` | Regenera TREE.txt y CHECKSUMS | 💚 salud | safe | required |
| `bago pack-cache` | Cache híbrida de pack en SQLite: sync \| check \| status | • infraestructura | safe | required |
| `bago task` | Muestra la tarea W2 pendiente. --done \| --assign <agente> \| --clear | ▶️ ejecución | safe | required |
| `bago validate` | Verifica el pack (manifiesto, estado, roles, ZIP) â€” subcomandos: manifest, state, contents | 💚 salud | safe | required |
| `bago workspace-select` | Selector de espacio de trabajo: elige entre framework (self), directorio padre o ruta/repo externo. Persiste en repo_context.json. Se invoca automÃ¡ticamente al arrancar si no hay workspace configurado. Uso: bago workspace-select  \|  opciones: --json --plain | • configuraciÃ³n | safe | required |

---

## 🧪 Experimental

Actively developed. May change between minor versions.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago ableton-template` | Genera un scaffold de proyecto Ableton techno 4/4 | 🎨 visual | safe | optional |
| `bago advisor` | Advisor LLM adaptativo: ask\|next\|explain\|run\|context\|rubber-duck â€” orientaciÃ³n continua con modelo pequeÃ±o local | • infraestructura | safe | optional |
| `bago agent` | Multi-Agent Gateway: dispatch \| list \| status â€” orquesta herramientas BAGO desde cualquier agente externo (local, Ollama, MCP/Claude, Codex, cloud). Adapters: local \| ollama \| mcp \| codex \| cloud | • infraestructura | safe | optional |
| `bago alias-manager` | Crea y ejecuta atajos de comandos bago personalizados. Los alias se guardan en .bago/state/bago_aliases.json. Subcomandos: --list \| --set <nombre> <cmd> \| --run <nombre> \| --del <nombre> \| --show <nombre> | • configuraciÃ³n | safe | optional |
| `bago artifact-counter` | Mide y reporta la producciÃ³n de artefactos Ãºtiles por sesiÃ³n. Excluye artefactos de protocolo (sessions, changes, evidences). Ãštil para ver la velocidad real de entrega por sesiÃ³n. | • analÃ­tica | safe | optional |
| `bago ask` | Router lenguaje natural â†’ tools BAGO | 🔬 avanzado | safe | optional |
| `bago assign` | Asigna tareas a agentes/roles. list-agents \| assign <id> <agente> \| pending \| assigned | 🔬 avanzado | safe | optional |
| `bago autonomy` | ReconciliaciÃ³n automÃ¡tica del flujo activo: aplica pasos seguros sin permiso, reporta el resto. | • ejecuciÃ³n | mutating | optional |
| `bago benchmark` | Banco de pruebas de eficiencia BAGO (10 min). --duration N \| --suite fast\|full \| --json | 🔬 avanzado | safe | optional |
| `bago build-clean` | Elimina node_modules/dist/build para liberar espacio en disco. Dry-run por defecto. | 💚 salud | mutating | optional |
| `bago build-run` | Ejecuta el proceso de build de las apps del proyecto (server, web, electron, raÃ­z). | • ejecuciÃ³n | safe | optional |
| `bago canon` | Bucle de Shepard: 4 modos x 3 voces Â· DETECTâ†’DIAGNOSEâ†’VERIFYâ†’EVOLVE. Orquesta el ciclo completo de salud del framework. Modos: MODULAR (monolitos), SCAN (huerfanos/doc), CREATE (integracion), EVOLVE (lecciones). Uso: bago canon [--mode M] [--voice N] [--loop] [--json] | 🔍 calidad | safe | optional |
| `bago chronicle` | SesiÃ³n Chronicle integrando Copilot CLI /chronicle â€” historial de sesiones y recomendaciones | 📊 analítica | safe | optional |
| `bago code-metrics` | MÃ©tricas de cÃ³digo: lÃ­neas de cÃ³digo, conteo de archivos y tipos por app. Excluye node_modules, dist, build y archivos de lock. Soporta filtros de extensiÃ³n y configuraciÃ³n via bago_config. | • analÃ­tica | safe | optional |
| `bago code-search` | Busca texto o patrones en el cÃ³digo fuente del proyecto. Sin dependencias externas. Excluye node_modules/dist/build. Subcomandos: --regex \| -i (case-insensitive) \| --ext ts,py \| --files \| --count | 🔍 calidad | safe | optional |
| `bago config-check` | Valida integridad de configs JSON en state/config/ y cruza con registry | 💚 salud | safe | optional |
| `bago dashboard` | Muestra el dashboard del pack | 📊 analítica | safe | optional |
| `bago deactivate` | Crea un archivo comprimido de desactivaciÃ³n y lo oculta en Windows | 💚 salud | mutating | optional |
| `bago debt` | Ledger de deuda tÃ©cnica â€” registra, prioriza y hace seguimiento | 🔍 calidad | safe | optional |
| `bago deps` | AuditorÃ­a de dependencias (requirements/pyproject) | 🔍 calidad | safe | optional |
| `bago diff` | Muestra ficheros modificados entre las Ãºltimas sesiones BAGO | 📊 analítica | safe | optional |
| `bago doc-index` | Ãndice reverso de cobertura documental: quÃ© documentos en docs/ cubren quÃ© herramientas. Detecta tools sin documentar y permite aÃ±adir anotaciones @covers a los .md. | 🔍 calidad | safe | optional |
| `bago docs` | Genera docs/COMMANDS.md desde tool_registry.py (fuente Ãºnica de verdad) | 🔍 calidad | safe | optional |
| `bago env-manager` | GestiÃ³n de archivos de entorno (.env) del proyecto. Shim de compatibilidad para env.py. Subcomandos: list [-v] \| table \| diff [app] \| check \| set <app> KEY=value \| setup | • configuraciÃ³n | mutating | optional |
| `bago find-tool` | Busca la herramienta BAGO adecuada para un problema | 🔬 avanzado | safe | optional |
| `bago focus-mode` | Muestra la tarea activa en modo enfoque minimalista. DiseÃ±ado para mostrar en un corner de pantalla o en el prompt. Subcomandos: --compact (una lÃ­nea) \| --watch (refresca 30s) \| --clear | • ejecuciÃ³n | safe | optional |
| `bago git-status` | Resumen compacto del estado de git del proyecto activo. Usa comandos git estÃ¡ndar. Funciona en cualquier repositorio git. Subcomandos: --log N (Ãºltimos N commits) \| --short (una lÃ­nea) \| --diff | • infraestructura | safe | optional |
| `bago goals` | Gestor de objetivos del pack con seguimiento de progreso | ▶️ ejecución | safe | optional |
| `bago habit` | Detecta hÃ¡bitos de trabajo positivos y mejorables desde patrones de sesiones | 📊 analítica | safe | optional |
| `bago hardcode` | Detecta datos hardcodeados que deberÃ­an ser dinÃ¡micos (rutas, intÃ©rpretes, versiones, puertos) | 🔍 calidad | safe | optional |
| `bago heal-paths` | Detecta y repara rutas rotas tras reorganizaciones. Memoria persistente en state/. | 💚 salud | safe | optional |
| `bago html-export` | Genera un informe HTML autocontenido del proyecto BAGO. Incluye ideas implementadas, herramientas, mÃ©tricas por semana y estado. Subcomandos: --out DIR \| --open (abre en navegador tras generar) | 🎨 visual | safe | optional |
| `bago ideas` | Emite ideas W2 | ▶️ ejecución | safe | optional |
| `bago image-studio` | Generador de assets visuales coherentes (sprites, botones, fondos, iconos, tiles, banners) con perfil de proyecto | 🎨 visual | safe | optional |
| `bago image_gen` | Generador de imagenes PNG local sin API | 🎨 visual | safe | optional |
| `bago inbox` | Inbox de tareas autÃ³nomas: add <intent> \| list \| clear | 🔬 avanzado | safe | optional |
| `bago insights` | AnÃ¡lisis de patrones e insights del historial de sesiones BAGO | 📊 analítica | safe | optional |
| `bago lint-runner` | Ejecuta el linter en las apps del proyecto y agrega resultados. Detecta scripts lint/typecheck en cada package.json. Subcomandos: --app <nombre> \| --type (typecheck) \| --fix \| --list | 🔍 calidad | mutating | optional |
| `bago llm` | Motor LLM local offline: modelos GGUF en pendrive via Ollama (macOS/Linux/Windows) | 🔬 avanzado | safe | optional |
| `bago llm-node` | Nodo LLM del Neural Bus: escucha llm.request, llama a Ollama con streaming, emite llm.chunk + llm.response. Modos: chat\|tool_suggest\|classify_intent | • infraestructura | safe | optional |
| `bago log-viewer` | Visor de logs en tiempo real para apps del monorepo. Detecta severidad (ERROR/WARN/INFO) y colorea la salida. Lee la ruta del proyecto desde global_state.json. | • ejecuciÃ³n | safe | optional |
| `bago lsp` | OrquestaciÃ³n de Language Servers â€” registra y gestiona servidores LSP para inteligencia de cÃ³digo | 🔬 avanzado | safe | optional |
| `bago music` | Pipeline musical (MarcValls/BAGO_MUSIC_PIPELINE): plan \| convert \| transpose \| validate \| render \| run | 🔬 avanzado | safe | optional |
| `bago naming` | Lint de convenciones de nombres | 🔍 calidad | safe | optional |
| `bago net-scan` | EscÃ¡ner de red: detecta adaptadores, estado de cable, velocidad y vecinos ARP. Ãštil para diagnÃ³stico de conectividad local. Subcomandos: --scan (ARP de red local) \| --watch (monitoriza cambios) \| --adapters | • infraestructura | mutating | optional |
| `bago neural` | Neural Bus â€” servidor SSE de mensajes inter-agente (start/stop/status/nodes/map) | • infraestructura | safe | optional |
| `bago neural-toolbox` | Motor de activaciÃ³n dinÃ¡mica de herramientas: convierte contexto en lenguaje natural en un toolbox adaptado. Perfiles derivados del registry, filtros scope/risk, feedback adaptativo. Subcomandos: --context \| --run \| --explain \| --json \| --dry-run | • core | safe | optional |
| `bago next` | Meta-comando de ciclo mÃ­nimo: elige idea + acepta + inicia flujo en un paso | ▶️ ejecución | safe | optional |
| `bago notify-bago` | NotificaciÃ³n BAGO universal: whatsapp (Green API), telegram, desktop. | 🔬 avanzado | safe | optional |
| `bago notify-desktop` | EnvÃ­a notificaciones de escritorio (Windows toast via BurntToast PowerShell). | 🔬 avanzado | safe | optional |
| `bago notify-whatsapp` | NotificaciÃ³n BAGO vÃ­a WhatsApp usando CallMeBot API. | 🔬 avanzado | safe | optional |
| `bago npath` | Neural Path â€” grafo cognitivo versionado: branch/commit/merge/unmerge/split/recall/map | • conocimiento | safe | optional |
| `bago orphan-shield` | Detecta 4 tipos de huÃ©rfanos: archivos .py no registrados, entradas de registry sin archivo, comandos del router sin registry y tools sin cobertura documental. | 🔍 calidad | safe | optional |
| `bago personality-panel` | Panel de personalidad y configuraciÃ³n de agentes BAGO. Gestiona el perfil de personalidad del usuario en user_personality_profile.json. Configura estilo, idioma y vocabulario preferido de los agentes. | • configuraciÃ³n | safe | optional |
| `bago ping-server` | Verifica que el servidor local responde vÃ­a HTTP. Muestra status, latencia y errores. Lee la URL desde apps/server/.env. Subcomandos: --url <URL> \| --path <endpoint> \| --watch (ping cada 5s) | 💚 salud | safe | optional |
| `bago placeholder_scan` | Detecta placeholders y datos ficticios en cÃ³digo Python (FAKE_DATE, STUB_RAISE, ELLIPSIS_BODY, TODO_COMMENT, PLACEHOLDER_STR) | 🔍 calidad | safe | optional |
| `bago preflight-check` | Pre-flight checks declarativos para herramientas BAGO: file/env/cmd conditions. | 💚 salud | safe | optional |
| `bago project-summary` | Dashboard ejecutivo del proyecto: ideas implementadas, herramientas, tamaÃ±o en disco, estado de git y todos pendientes. Fuente Ãºnica de verdad para el estado actual del proyecto. | • analÃ­tica | safe | optional |
| `bago recientes` | BitÃ¡cora paginada de Ãºltimos trabajos: sesiones, sprints, ideas, cierres y commits ordenados cronolÃ³gicamente | • analÃ­tica | safe | optional |
| `bago reopen` | Reanuda sesiÃ³n desde el Ãºltimo cierre sin reconstruir contexto manualmente | ▶️ ejecución | safe | optional |
| `bago repo` | GestiÃ³n de repositorios: clone \| list \| switch | 💚 salud | safe | optional |
| `bago research` | Modo Research integrando GitHub Copilot CLI /research â€” investigaciÃ³n temÃ¡tica estructurada | 🔬 avanzado | safe | optional |
| `bago review` | Code review automatizado fail-closed con estado explÃ­cito por scanner | 🔍 calidad | safe | optional |
| `bago risk` | Matriz de riesgo del proyecto â€” evalÃºa impacto y probabilidad | 🔍 calidad | safe | optional |
| `bago route` | Router hibrido balanceado/adaptativo: decide entre Ollama local, Codex y Copilot | 🔬 avanzado | safe | optional |
| `bago rubber-duck` | Rubber duck debugging automÃ¡tico: repite quÃ© hace el cÃ³digo, detecta pasos faltantes e inconsistencias â€” auto-trigger en toolsmith create | 🔍 calidad | safe | optional |
| `bago rules` | CatÃ¡logo de reglas BAGO | 🔬 avanzado | safe | optional |
| `bago script-runner` | Ejecuta cualquier script npm/pnpm del workspace del monorepo. Detecta scripts en root y apps/*/package.json. Lee el proyecto activo desde global_state.json. | • ejecuciÃ³n | mutating | optional |
| `bago search-history` | Busca en el historial de ideas implementadas. Sin argumentos muestra las Ãºltimas 10 ideas. Uso: bago search-history <tÃ©rmino> [tÃ©rmino2 ...] | • conocimiento | safe | optional |
| `bago seed` | BAGO Seed â€” planta la huella mÃ­nima de BAGO en un proyecto externo: crea .bago/pack.json + state/ + launcher y registra la siembra. Subcomandos: [path] \| --name \| --dry-run \| --list \| --status | • infraestructura | mutating | optional |
| `bago select` | Selector interactivo de ideas por slot con plan de implementaciÃ³n | ▶️ ejecución | safe | optional |
| `bago siembra` | GestiÃ³n de siembras BAGO v3.0: create \| list \| update \| diff \| sync \| status | 💚 salud | mutating | optional |
| `bago size-check` | Detecta archivos .py en .bago/tools/ con mÃ¡s de 400 lÃ­neas y los reporta como monolitos candidatos a dividir. | 🔍 calidad | safe | optional |
| `bago skill` | Skill Layer (Fractal AGI nivel-2): mini-spirals de 3-6 pasos. list \| run <id> \| status | 🔬 avanzado | safe | optional |
| `bago snapshot` | Compara dos snapshots de estado BAGO: diferencias en tools, ideas e inventario. | • analÃ­tica | safe | optional |
| `bago spanish` | Detecta inconsistencias ortogrÃ¡ficas en espaÃ±ol: tildes y singular/plural en claves y rutas | 🔍 calidad | safe | optional |
| `bago spiral-agent` | Agent Layer (Fractal AGI nivel-1): BagoAgents con skills dinÃ¡micas. spawn \| list \| run <id> \| kill \| status | 🔬 avanzado | safe | optional |
| `bago sprint` | Gestor de sprints BAGO â€” crear, listar, cerrar sprints de trabajo | ▶️ ejecución | safe | optional |
| `bago sprite-studio` | Generador de sprites BIANCA via Codex/HF sin API key, con galerÃ­a browser | 🎨 visual | safe | optional |
| `bago state-manager` | API unificada para el estado BAGO: health, sprint y knowledge. Gestiona global_state.json y ficheros divididos (health.json, sprint.json, knowledge_index.json). Subcomandos: --status \| --materialize \| --split \| --read <secciÃ³n> \| --test | • infraestructura | mutating | optional |
| `bago template-gen` | Genera archivos de proyecto desde plantillas predefinidas (component, hook, api-route, test, etc.). Variables: {{PROJECT}}, {{APP}}, {{NAME}}, {{DATE}}, {{AUTHOR}}. Subcomandos: --list \| --show <nombre> \| --add <nombre> \| --out <dir> | • ejecuciÃ³n | mutating | optional |
| `bago toolsmith` | Agente dinÃ¡mico de toolboxes: assign\|sprint\|agent\|missing\|create\|catalog\|listen â€” asigna cajas de herramientas por tarea y crea tools faltantes | • infraestructura | safe | optional |
| `bago types` | Chequeo de tipos estÃ¡ticos | 🔍 calidad | safe | optional |
| `bago version` | GestiÃ³n de versiones beta/release: bump \| beta \| release \| tag \| commit \| sync-check \| sync-state | 🔬 avanzado | mutating | optional |
| `bago weekly-report` | Informe semanal de actividad BAGO: ideas implementadas, sesiones y velocidad. Por defecto Ãºltimos 7 dÃ­as. Genera resumen Markdown. Subcomandos: --days N \| --save (guarda en .bago/state/reports/) | • analÃ­tica | safe | optional |
| `bago why` | Explica quÃ© hace un comando BAGO, cuÃ¡ndo usarlo y sus relaciones | 🔬 avanzado | safe | optional |
| `bago work_matrix` | Matriz de rutas de trabajo: quÃ© agente y herramientas MCP usar segÃºn el tipo de tarea | • analÃ­tica | safe | optional |
| `bago workflow` | Selector de workflow (interactivo) | ▶️ ejecución | safe | optional |
| `bago workflow-navigator` | Navegador de workflows BAGO: sugiere el workflow mÃ¡s adecuado dado el contexto actual. Lee WORKFLOW_GRAPH.json y el estado del sistema. Subcomandos: --from <workflow> \| --list \| --graph \| --test | 🔬 avanzado | safe | optional |

---

## ⚠️ Dangerous

High-impact commands. Require `--confirm` or `--dry-run`.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago auto` | Modo automÃ¡tico: evalÃºa y actÃºa. --loop para bucle, --infinite para sin lÃ­mite (Ctrl+C) | ▶️ ejecución | **dangerous** | optional |
| `bago autonomous` | Loop autÃ³nomo BAGO: SENSEâ†’PLANâ†’ACTâ†’OBSERVEâ†’LEARNâ†’DECIDE [--dry-run] [--loop] [--unsafe] | 🔬 avanzado | **dangerous** | optional |
| `bago cabinet` | Gabinete BAGO: orquesta agentes en paralelo e informa unificado | 🔬 avanzado | **dangerous** | optional |
| `bago db` | Gestiona bago.db: estado de ideas, historial guardian, init/status/reset | 🔬 avanzado | **dangerous** | optional |
| `bago install` | Auto-lanzamiento al insertar el pendrive (macOS/Linux/Windows/Android/iPad) | 🔬 avanzado | **dangerous** | optional |
| `bago orchestrate` | Orquestador de workflows multi-tool en secuencia con condiciones | 🔬 avanzado | **dangerous** | optional |
| `bago peer` | Comunicacion peer-to-peer LAN (serve/discover/ping/send/chat) | 🔬 avanzado | **dangerous** | optional |
| `bago spiral` | Bucle espiral cromÃ¡tico (Shepard Loop): 12 pasos de auto-redescriciÃ³n AGI. --execute para actuar, --status, --history | 🔬 avanzado | **dangerous** | optional |

---

## 🗄️ Legacy

Deprecated. Use the indicated replacement instead.

| Command | Use instead | Description |
|---------|-------------|-------------|
| `bago check` | `bago audit purity` | Chequeo estÃ¡tico de pureza |
| `bago code-quality` | `bago audit quality` | Orquestador de calidad de cÃ³digo â€” ejecuta agentes especializados |
| `bago commit` | `bago audit commit` | EvaluaciÃ³n de preparaciÃ³n para commit |
| `bago consistency` | `bago health consistency` | Guard anti-drift: valida CI, preflight, README y badge del framework |
| `bago cosecha` | `bago session harvest` | Cosecha de artefactos del proyecto |
| `bago detector` | `bago context detect` | Detector de contexto del repo |
| `bago doctor` | `bago audit doctor` | DiagnÃ³stico completo del entorno BAGO: Python, Git, Ollama, modelo LLM, espacio |
| `bago efficiency` | `bago health efficiency` | Medidor de eficiencia inter-versiones |
| `bago git` | `bago context git` | Contexto git (log/diff/brief) para workflows |
| `bago heal` | `bago audit heal` | Auto-detecta y repara problemas del framework de forma segura y trazable |
| `bago learn` | `bago project learn` | Guarda un aprendizaje en learnings.md del proyecto vinculado |
| `bago map` | `bago context map` | Mapa de contexto del repositorio |
| `bago pre-push` | `bago audit push` | Gate de sincronizacion remota: bloquea pushes con BAGO roto |
| `bago project-init` | `bago project init` | Inicializa .bago/ local en el directorio del proyecto actual |
| `bago project-link` | `bago project link` | Vincula el proyecto al framework (sesiones se guardan en el proyecto) |
| `bago project-state` | `bago project state` | Muestra el estado del proyecto actualmente vinculado |
| `bago project-unlink` | `bago project unlink` | Desvincula el proyecto â€” sesiones vuelven al framework |
| `bago promote` | `bago project promote` | Promueve un aprendizaje del proyecto al knowledge del framework |
| `bago repo-clone` | `bago repo clone` | Clona repositorios GitHub en workspace con auto-BAGO setup |
| `bago repo-list` | `bago repo list` | Lista repositorios clonados en workspace con estado |
| `bago repo-switch` | `bago repo switch` | Cambia contexto activo entre repositorios del workspace |
| `bago report` | `bago health report` | Health report en Markdown |
| `bago scan` | `bago audit scan` | Escaneo de calidad de cÃ³digo: hallazgos, severidad, autofixable |
| `bago session_close` | `bago session close` | Genera el informe de cierre de sesion BAGO |
| `bago sincerity` | `bago health sincerity` | Centinela de sinceridad: detecta sincofancÃ­a en docs .md |
| `bago stability` | `bago health stability` | Resumen de estabilidad del pack |
| `bago stale` | `bago context stale` | Detecta tools obsoletas o sin mantenimiento |
| `bago v2` | `bago session v2` | Checklist de cierre v2 |

---

## Notes

- **Policy** — preflight enforcement: `required` (always runs) · `optional` (skipped with `--skip-preflight`) · `none`
- **Risk** — `safe` (read-only) · `mutating` (writes state) · `**dangerous**` (destructive, needs `--confirm`)
- **Legacy** commands still execute but print a deprecation hint. They will be removed in v4.0.
- Run `bago help <cmd>` for per-command usage.

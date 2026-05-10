# BAGO — Command Reference

> **Auto-generated** from `tool_registry.py`. Do not edit manually.
> Last generated: 2026-05-10 01:50 UTC
>
> Source of truth: `.bago/tools/tool_registry.py`
> Generator: `.bago/tools/generate_commands_doc.py`

## Summary

| Bucket | Count |
|--------|-------|
| ⚙️ Core | 12 |
| 🧪 Experimental | 39 |
| ⚠️ Dangerous | 7 |
| 🗄️ Legacy (deprecated) | 28 |
| **Total active** | **58** |

---

## ⚙️ Core

Stable commands. Pre-flight **required**. Always available.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago audit` | Auditoría y calidad: full \| pack \| scan \| commit \| push \| doctor \| heal \| quality \| purity | 💚 salud | safe | required |
| `bago context` | Contexto del workspace: detect \| map \| git \| stale | 💚 salud | safe | required |
| `bago flow` | Flowchart ASCII de workflows + gestión de estado activo (start/done/status) | ▶️ ejecución | safe | required |
| `bago health` | Salud del framework: score \| report \| stability \| efficiency \| consistency \| sincerity | 💚 salud | safe | required |
| `bago project` | Memoria distribuida por proyecto: init \| link \| unlink \| state \| learn \| promote | 💚 salud | safe | required |
| `bago scope` | Detecta scope (framework/project/both) de scripts Python por análisis estático | 💚 salud | safe | required |
| `bago secrets` | Escanea el repositorio buscando secretos y credenciales expuestas | 🔍 calidad | safe | required |
| `bago session` | Ciclo de sesión: open \| close \| harvest \| v2 | ▶️ ejecución | safe | required |
| `bago status` | Estado actual: flujo activo, tarea pendiente y salud del sistema | 📊 analítica | safe | required |
| `bago sync` | Regenera TREE.txt y CHECKSUMS | 💚 salud | safe | required |
| `bago task` | Muestra la tarea W2 pendiente | ▶️ ejecución | safe | required |
| `bago validate` | Verifica el pack (solo lectura) | 💚 salud | safe | required |

---

## 🧪 Experimental

Actively developed. May change between minor versions.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago ableton-template` | Genera un scaffold de proyecto Ableton techno 4/4 | 🎨 visual | safe | optional |
| `bago ask` | Router lenguaje natural → tools BAGO | 🔬 avanzado | safe | optional |
| `bago chronicle` | Sesión Chronicle integrando Copilot CLI /chronicle — historial de sesiones y recomendaciones | 📊 analítica | safe | optional |
| `bago config-check` | Valida integridad de configs JSON en state/config/ y cruza con registry | 💚 salud | safe | optional |
| `bago dashboard` | Muestra el dashboard del pack | 📊 analítica | safe | optional |
| `bago deactivate` | Crea un archivo comprimido de desactivación y lo oculta en Windows | 💚 salud | mutating | optional |
| `bago debt` | Ledger de deuda técnica — registra, prioriza y hace seguimiento | 🔍 calidad | safe | optional |
| `bago deps` | Auditoría de dependencias (requirements/pyproject) | 🔍 calidad | safe | optional |
| `bago diff` | Muestra ficheros modificados entre las últimas sesiones BAGO | 📊 analítica | safe | optional |
| `bago docs` | Genera docs/COMMANDS.md desde tool_registry.py (fuente única de verdad) | 🔍 calidad | safe | optional |
| `bago find-tool` | Busca la herramienta BAGO adecuada para un problema | 🔬 avanzado | safe | optional |
| `bago goals` | Gestor de objetivos del pack con seguimiento de progreso | ▶️ ejecución | safe | optional |
| `bago habit` | Detecta hábitos de trabajo positivos y mejorables desde patrones de sesiones | 📊 analítica | safe | optional |
| `bago ideas` | Emite ideas W2 | ▶️ ejecución | safe | optional |
| `bago image-studio` | Generador de assets visuales coherentes (sprites, botones, fondos, iconos, tiles, banners) con perfil de proyecto | 🎨 visual | safe | optional |
| `bago image_gen` | Generador de imagenes PNG local sin API | 🎨 visual | safe | optional |
| `bago inbox` | Inbox de tareas autónomas: add <intent> \| list \| clear | 🔬 avanzado | safe | optional |
| `bago insights` | Análisis de patrones e insights del historial de sesiones BAGO | 📊 analítica | safe | optional |
| `bago llm` | Motor LLM local offline: modelos GGUF en pendrive via Ollama (macOS/Linux/Windows) | 🔬 avanzado | safe | optional |
| `bago lsp` | Orquestación de Language Servers — registra y gestiona servidores LSP para inteligencia de código | 🔬 avanzado | safe | optional |
| `bago music` | Pipeline musical: plan, convert, inventory y etapas MusicXML honestas | 🔬 avanzado | safe | optional |
| `bago naming` | Lint de convenciones de nombres | 🔍 calidad | safe | optional |
| `bago next` | Meta-comando de ciclo mínimo: elige idea + acepta + inicia flujo en un paso | ▶️ ejecución | safe | optional |
| `bago recientes` | Bitácora paginada de últimos trabajos: sesiones, sprints, ideas, cierres y commits ordenados cronológicamente | 📊 analítica | safe | optional |
| `bago reopen` | Reanuda sesión desde el último cierre sin reconstruir contexto manualmente | ▶️ ejecución | safe | optional |
| `bago repo` | Gestión de repositorios: clone \| list \| switch | 💚 salud | safe | optional |
| `bago research` | Modo Research integrando GitHub Copilot CLI /research — investigación temática estructurada | 🔬 avanzado | safe | optional |
| `bago review` | Code review automatizado — analiza cambios y genera feedback | 🔍 calidad | safe | optional |
| `bago risk` | Matriz de riesgo del proyecto — evalúa impacto y probabilidad | 🔍 calidad | safe | optional |
| `bago route` | Router hibrido balanceado/adaptativo: decide entre Ollama local, Codex y Copilot | 🔬 avanzado | safe | optional |
| `bago rules` | Catálogo de reglas BAGO | 🔬 avanzado | safe | optional |
| `bago select` | Selector interactivo de ideas por slot con plan de implementación | ▶️ ejecución | safe | optional |
| `bago siembra` | Gestión de siembras BAGO v3.0: create \| list \| update \| diff \| sync \| status | 💚 salud | mutating | optional |
| `bago sprint` | Gestor de sprints BAGO — crear, listar, cerrar sprints de trabajo | ▶️ ejecución | safe | optional |
| `bago sprite-studio` | Generador de sprites BIANCA via Codex/HF sin API key, con galería browser | 🎨 visual | safe | optional |
| `bago types` | Chequeo de tipos estáticos | 🔍 calidad | safe | optional |
| `bago version` | Gestión de versiones beta/release: bump \| beta \| release \| tag \| commit \| sync-check | 🔬 avanzado | mutating | optional |
| `bago why` | Explica qué hace un comando BAGO, cuándo usarlo y sus relaciones | 🔬 avanzado | safe | optional |
| `bago workflow` | Selector de workflow (interactivo) | ▶️ ejecución | safe | optional |

---

## ⚠️ Dangerous

High-impact commands. Require `--confirm` or `--dry-run`.

| Command | Description | Layer | Risk | Policy |
|---------|-------------|-------|------|--------|
| `bago auto` | Modo automático: evalúa y actúa. --loop para bucle, --infinite para sin límite (Ctrl+C) | ▶️ ejecución | **dangerous** | optional |
| `bago autonomous` | Loop autónomo BAGO: SENSE→PLAN→ACT→OBSERVE→LEARN→DECIDE [--dry-run] [--loop] [--unsafe] | 🔬 avanzado | **dangerous** | optional |
| `bago cabinet` | Gabinete BAGO: orquesta agentes en paralelo e informa unificado | 🔬 avanzado | **dangerous** | optional |
| `bago db` | Gestiona bago.db: estado de ideas, historial guardian, init/status/reset | 🔬 avanzado | **dangerous** | optional |
| `bago install` | Auto-lanzamiento al insertar el pendrive (macOS/Linux/Windows/Android/iPad) | 🔬 avanzado | **dangerous** | optional |
| `bago orchestrate` | Orquestador de workflows multi-tool en secuencia con condiciones | 🔬 avanzado | **dangerous** | optional |
| `bago peer` | Comunicacion peer-to-peer LAN (serve/discover/ping/send/chat) | 🔬 avanzado | **dangerous** | optional |

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
- **Risk** — `safe` (read-only) · `mutating` (writes state) · `**dangerous**` (destructive, needs `--confirm`)
- **Legacy** commands still execute but print a deprecation hint. They will be removed in v4.0.
- Run `bago help <cmd>` for per-command usage.

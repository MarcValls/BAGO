# DICCIONARIO BAGO

Glosario completo de términos, comandos, workflows, roles y conceptos del sistema BAGO.

---

## A

**AGENTS.md**
Archivo de instrucciones para agentes de IA. Puede aparecer en cualquier directorio del repo. Su scope aplica a todo el subtree bajo él. Los más anidados prevalecen en caso de conflicto. Las instrucciones de sistema/usuario prevalecen sobre AGENTS.md.

**ANALISTA (rol)**
Rol opcional en modos [B] y [A]. Contextualiza la tarea antes de ejecutar. Se activa con ago session o por workflow.

**API BAGO**
Servidor FastAPI que expone endpoints compatibles con Ollama + extensiones propias (routing, health, escalate). Puerto por defecto: 11435. Se arranca con ago serve.

**ARQUITECTO (rol)**
Rol opcional en modos [A] y [G]. Diseña soluciones y toma decisiones técnicas de arquitectura.

**audit**
Comando: ago audit. Auditoría integral del pack: sync + validate + health + vértice + workflow.

---

## B

**BAGO**
Acrónimo de **B**alanceado · **A**daptativo · **G**enerativo · **O**rganizativo. Sistema operativo de trabajo técnico para programación y generación compleja. Versión actual: 3.5.0.

**bago (CLI)**
Interfaz de línea de comandos. Punto de entrada principal: ago launch abre el chat interactivo donde el usuario habla con BAGO (que orquesta modelos internamente).

**bago.db**
Base de datos SQLite en .bago/state/bago.db. Almacena ideas implementadas, métricas y datos operativos.

**bago update**
Ejecuta actualización completa: pull de modelos Ollama, check de dependencias, auto-heal y diagnosis del entorno. Equivalente a ago_update.py --yes.

**BAGO Health Score**
Puntuación 0-100 que mide la salud del pack. Dimensiones: integridad (25), disciplina workflow (20), captura de decisiones (20), estado stale (15), consistencia inventario (20). Se consulta con ago health.

**bootstrap**
Proceso de arranque obligatorio definido en AGENT_START.md. Secuencia: leer pack.json → README → CEREBRO → GOBERNANZA → MATRIZ_ACTIVACION → global_state → repo_context_guard → ESTADO_BAGO_ACTUAL → identificar modo → activar roles → ejecutar bloque mínimo → actualizar estado.

---

## C

**canon/**
Directorio normativo dentro de .bago/core/. Contiene los contratos del sistema (workflow, rol, cambio, evidencia). Fuente de verdad normativa.

**cambio (contrato)**
Protocolo para modificaciones sensibles (arquitectura, contratos, migraciones, seguridad). Definido en core/canon/CONTRATOS/contrato_cambio.md. Tipos: patch, minor, major, critical.

**cabinet**
Comando: ago cabinet. Orquesta el gabinete de agentes BAGO y emite informe unificado.

**check**
Comando: ago check. Verificación estática de pureza — confirma que herramientas de validación no realizan operaciones de escritura.

**chronicle**
Comando: ago chronicle. Historial de sesiones y recomendaciones, integrado con Copilot CLI.

**cosecha**
Comando: ago cosecha. Cierra la sesión activa, captura valor producido y actualiza estado. Equivalente al workflow W9 (cosecha contextual).

**cold start (W1)**
Workflow de arranque desde cero en un repositorio desconocido. Analiza estructura, dependencias y genera contexto mínimo para operar.

---

## D

**db**
Comando: ago db. Gestión de la base de datos SQLite BAGO. Subcomandos: init, status, ideas, eset-ideas.

**deps**
Comando: ago deps. Auditoría de dependencias del proyecto. Flag --install para instalar automáticamente.

**detector**
Comando: ago detector. Ejecuta context_detector.py — detecta el contexto del repositorio actual.

---

## E

**eficiency**
Comando: ago efficiency. Medidor de eficiencia inter-versiones del pack.

**env**
Comando: ago env. Gestión de archivos de entorno (.env). Subcomandos: list, 	able, diff, check, set, setup. check diagnostica el entorno y ofrece instalar herramientas faltantes (npm, etc.).

**ESCENARIO-001**
Escenario activo en global_state.json. Cuando está presente, toda sesión productiva debe pasar el preflight (	ools/session_preflight.py) antes de arrancar.

**ESCENARIO-002**
Escenario de competición on vs off. Define el modo .bago/off para sesiones libres sin preflight ni restricción de roles.

**evidencia (contrato)**
Define cómo se documenta el resultado de un cambio. Contrato en core/canon/CONTRATOS/contrato_evidencia.md. Toda evidencia debe ser trazable, verificable y oponible.

---

## F

**find-tool**
Comando: ago find-tool. Busca la herramienta BAGO adecuada para un problema dado.

**flow**
Comando: ago flow. Lista los workflows BAGO disponibles.

**foco de sesión (W7)**
Workflow para sesiones productivas con preflight obligatorio cuando ESCENARIO-001 está activo. Requiere: objetivo, roles, artefactos y tipo de tarea.

---

## G

**GENERADOR (rol)**
Rol opcional en modo [G]. Produce artefactos útiles: código, tests, docs, scripts, configuraciones, planes técnicos.

**git**
Comando: ago git. Proporciona contexto git (log/diff/brief) para workflows.

**global_state.json**
Archivo canónico en .bago/state/. Fuente de verdad estructural del pack: versión, sesión activa, inventario, validaciones, health, proveedores, escenarios activos. Manda sobre cualquier otro archivo en caso de conflicto.

**GOBERNANZA_DE_SESION**
Documento en core/05_GOBERNANZA_DE_SESION.md. Define principios: claridad sobre estética, cambios sensibles con validación humana, trazabilidad sobre velocidad ciega, reparar antes que castigar, supervisión solo con evidencia.

---

## H

**health**
Comando: ago health. Calcula y muestra el BAGO Health Score (0-100). Dimensiones: integridad, disciplina workflow, captura decisiones, estado stale, consistencia inventario.

**ideas**
Comando: ago ideas. Emite ideas del catálogo W2. Con --accept N acepta una idea y genera tarea.

---

## I

**intent_router / ask**
Comando: ago ask. Router de lenguaje natural hacia tools BAGO. Interpreta una petición en lenguaje natural y la dirige a la herramienta adecuada.

---

## K

**knowledge/**
Directorio en .bago/. Memoria operativa sincronizable del BAGO local. Misma categoría que canon/. Contiene: 	opics/ (superficie canónica), xamples/ (planes y prompts), schemas/ (validación), ssets/ (diagramas). Indexado por knowledge_index.json.

---

## L

**launch**
Comando principal: ago launch. Abre la interfaz conversacional donde el usuario habla con BAGO. Opciones: --provider copilot, --provider ollama, --model <modelo>.

**lenovo-connect / lenovo-http / lenovo-monitor**
Comandos de red para detección y conexión con PC Lenovo en Ethernet directo (169.254.31.155/16). WinRM, SMB, NetBIOS, HTTP discovery.

**lsp**
Comando: ago lsp. Orquestación de Language Servers — registra y gestiona servidores LSP para inteligencia de código en tiempo real.

---

## M

**MAESTRO_BAGO (rol)**
Rol obligatorio en todos los modos BAGO. Es el conductor de la sesión: entiende el objetivo, activa los roles necesarios, coordina la ejecución y asegura la trazabilidad.

**map**
Comando: ago map. Genera mapa de contexto del repositorio (estructura, dependencias, puntos de entrada).

**MATRIZ_DE_ACTIVACION**
Documento en core/06_MATRIZ_DE_ACTIVACION.md. Define qué roles son obligatorios y opcionales para cada modo BAGO:
- Modo [B]: MAESTRO_BAGO + opcional ANALISTA_Contexto
- Modo [A]: MAESTRO_BAGO + opcional ANALISTA, ARQUITECTO
- Modo [G]: MAESTRO_BAGO + opcional GENERADOR, ARQUITECTO
- Modo [O]: MAESTRO_BAGO + opcional ORGANIZADOR

**mode-gate**
Función del menú BAGO. Controla el fallback entre modelos cuando el principal no responde o falla.

**model list / model set**
ago model list lista agentes y modelos asignados. ago model set <id> <modelo> asigna un modelo a un agente.

---

## N

**naming**
Comando: ago naming. Lint de convenciones de nombres en el código del proyecto.

**Neural Bus**
Sistema de comunicación entre agentes BAGO. Gestión con ago neural [cmd]. Endpoints SSE para comunicación en tiempo real.

**Neural Path**
Grafo cognitivo de BAGO. Gestión con ago npath [cmd]. Permite rastrear relaciones entre conceptos, decisiones y artefactos.

**net / net-interact**
ago net — estado de red y cables: detecta adaptadores, velocidad de enlace y dispositivos vecinos. ago net-interact — interacción con red Ethernet interna (10.0.0.x): PC Suite, llamadas, SMS.

---

## O

**ORGANIZADOR (rol)**
Rol opcional en modo [O]. Ordena, empaqueta, actualiza estado y deja continuidad para la siguiente sesión.

---

## P

**pack.json**
Manifiesto principal del pack BAGO. Contiene: id, versión, entrypoints, contratos, workflows, comandos, conocimiento, configuración de bootstrap y providers. Ubicado en .bago/pack.json.

**preflight**
Verificación previa obligatoria para sesiones productivas bajo ESCENARIO-001. Ejecuta 	ools/session_preflight.py con objetivo, roles, artefactos y tipo de tarea. Resultado GO → abrir sesión, KO → corregir y repetir.

**project init / link / state**
ago project init — inicializa .bago/ en el proyecto actual. ago project link — vincula el proyecto al framework. ago project state — muestra estado del proyecto vinculado.

---

## R

**report**
Comando: ago report. Genera health report en Markdown.

**research**
Comando: ago research. Modo Research integrando GitHub Copilot CLI /research — investigación temática estructurada.

**roles (contrato)**
Define las responsabilidades y límites de cada rol BAGO. Contrato en core/canon/CONTRATOS/contrato_rol.md. Cada rol tiene: propósito, permisos, herramientas autorizadas y restricciones.

**rubber-duck**
ago rubber-duck <file> — debugging interactivo: repite qué hace el código. --last analiza el último .py modificado. --watch modo polling continuo.

**rules**
Comando: ago rules. Catálogo de reglas BAGO activas.

---

## S

**select**
Comando: ago select. Selector interactivo de ideas por slot con plan de implementación.

**serve**
Comando: ago serve. Arranca el **servidor API BAGO** — un servidor FastAPI en puerto 11435 compatible con endpoints Ollama y con extensiones propias (routing de modelos, health checks, escalation a cloud). Puertos: 11434 (Ollama local), 11435 (BAGO), 11436 (Copilot proxy), 11437 (OpenAI proxy), 11438 (Ollama Cloud), 11439 (Telegram bot), 11440 (Utopia bot).

**session**
Comando: ago session. Abre sesión W2 con preflight pre-rellenado. --dry muestra args sin ejecutar.

**sincerity**
Comando: ago sincerity. Centinela de sinceridad: detecta sincronía y trampas en archivos .md.

**siembra**
ago siembra create . — planta una siembra (proyecto hijo) en el directorio actual. ago siembra list — lista siembras registradas. ago siembra ideas — alias de ago ideas.

**sprint**
Comando: ago sprint. Resumen automático de sprint (batch de N ideas implementadas).

**stability**
Comando: ago stability. Resumen único de estabilidad (smoke/VM/soak/validadores).

**stale**
Comando: ago stale. Detecta archivos de estado obsoletos o desactualizados.

**sync**
Comando: ago sync. Regenera TREE.txt y CHECKSUMS.sha256 a partir del contenido actual del pack.

---

## T

**task**
Comando: ago task. Muestra la tarea W2 pendiente. --done marca como completada. --assign <ROL> asigna la tarea a un agente.

**token-analytics**
Función del menú BAGO. Tracking de tokens consumidos por modelo y sesión.

**types**
Comando: ago types. Chequeo de tipos estáticos del código del proyecto.

---

## V

**validate**
Comando: ago validate. Verifica integridad del pack (manifest + state + pack) sin modificar archivos. Resultados: GO (válido) o KO (con errores).

**VERTICE (rol)**
Rol de revisión evolutiva. Solo se activa con evidencia de: deriva, contradicción estado/repo, inflación de roles, rediseño no controlado o pérdida de trazabilidad. No entra por defecto.

---

## W

**wizard**
ago wizard — wizard de instalación (acepta contrato, instala packs). --reset borra marker y vuelve a ejecutar. --status muestra estado de instalación.

**workflow (contrato)**
Define la estructura canónica de un workflow BAGO. Contrato en core/canon/CONTRATOS/contrato_workflow.md. Todo workflow tiene: id, propósito, pasos, pre/post condiciones.

**Workflows BAGO**

| Código | Nombre | Propósito |
|--------|--------|-----------|
| W0 | Sesión Libre | Trabajo libre sin estructura, sin preflight, sin restricción de roles |
| W1 | Cold Start | Arranque desde cero en repositorio desconocido |
| W2 | Implementación Controlada | Sprint de implementación atómica con evidencia |
| W3 | Refactor Sensible | Refactorización de código existente con cambios mínimos |
| W4 | Debug Multicausa | Diagnóstico y resolución de bugs con múltiples causas posibles |
| W5 | Cierre y Continuidad | Cierre de sesión dejando siguiente paso claro |
| W6 | Ideación Aplicada | Generación y priorización de ideas para el catálogo |
| W7 | Foco de Sesión | Sesión productiva con preflight obligatorio (ESCENARIO-001) |
| W8 | Exploración | Sesión de exploración libre con captura opcional |
| W9 | Cosecha Contextual | Captura de valor producido en la sesión |
| W10 | Auditoría de Sinceridad | Revisión de sinceridad del estado vs. realidad del repo |

**WORKFLOW_MAESTRO_BAGO**
Secuencia canónica de workflows: canon -> integración -> entorno -> validación escalonada -> baseline -> regresión -> operación continua. Definido en workflows/WORKFLOW_MAESTRO_BAGO.md.

---

## Agentes BAGO

| Agente | Descripción |
|--------|-------------|
| agent_architect | Diseña sistemas, APIs, estructuras de datos y toma decisiones técnicas |
| agent_coder | Implementa features, escribe módulos y refactoriza código |
| agent_debugger | Analiza errores, causa raíz y genera fix con test de regresión |
| agent_docs | Documentación y generación de contenido |
| agent_git | Commits, PRs, diffs, resolución de conflictos y estrategia de branching |
| agent_ops | Operaciones con cobertura cruzada |
| agent_planner | Sprints, roadmaps, backlogs y desglose de tareas |
| agent_refactor | Mejora código existente, elimina deuda técnica, aplica patrones SOLID |
| agent_tests | Ejecución y validación de tests |
| agent_tools | Herramientas y revisión de código |

---

## Capas de estado

| Archivo | Capa | Responsabilidad |
|---------|------|-----------------|
| global_state.json | Canónica | Fuente de verdad estructural: inventario, sesión activa, validaciones, sprint_status |
| ESTADO_BAGO_ACTUAL.md | Snapshot legible | Resumen humano del estado del pack |
| epo_context.json | Puntero externo | Fingerprint y ruta del repo externo. working_mode: self o xternal |

---

## Proveedores de modelos

| Provider | Puerto | Descripción |
|----------|--------|-------------|
| Ollama (local) | 11434 | Modelos locales via Ollama |
| BAGO API | 11435 | Servidor API propio (FastAPI) |
| GitHub Copilot | 11436 | Proxy a GitHub Models |
| OpenAI | 11437 | Proxy a OpenAI API |
| Ollama Cloud | 11438 | Proxy a Ollama Cloud |
| Telegram bot | 11439 | Bot de Telegram |
| Utopia bot | 11440 | Cliente Utopia |

---

*Última actualización: 2026-05-22 · BAGO v3.5.0*
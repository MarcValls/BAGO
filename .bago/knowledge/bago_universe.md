# BAGO Universe — Referencia Maestra
_Absorbido de 26 instancias .bago | 2026-05-05_
_Uso: consultar antes de sugerir agentes, workflows, herramientas o estructuras de plan_

---

## ÍNDICE

1. [Núcleo del Framework — B·A·G·O](#1-núcleo-del-framework--bago)
2. [Agentes disponibles](#2-agentes-disponibles)
3. [Workflows — cuándo usar cada uno](#3-workflows--cuándo-usar-cada-uno)
4. [Herramientas por categoría](#4-herramientas-por-categoría)
5. [Estructuras de plan / plantillas](#5-estructuras-de-plan--plantillas)
6. [Proyectos conocidos + patrones](#6-proyectos-conocidos--patrones)
7. [Reglas de activación y gobierno](#7-reglas-de-activación-y-gobierno)
8. [Instancias .bago en el sistema](#8-instancias-bago-en-el-sistema)

---

## 1. Núcleo del Framework — B·A·G·O

```
[B] Balanceado  → Clarifica objetivo, alcance, restricciones, riesgos, criterio de éxito
[A] Adaptativo  → Elige estrategia según estado REAL del repositorio
[G] Generativo  → Produce artefactos: código, tests, docs, scripts, planes
[O] Organizativo → Ordena, empaqueta, actualiza estado, deja continuidad
```

### Reglas maestras (siempre vigentes)
- No generar antes de entender.
- No rediseñar por impulso.
- No cerrar sin dejar siguiente paso claro.
- No confundir documentación con progreso.
- Preferir cambios mínimos, claros y trazables.
- **Repo-first**: inspeccionar antes de actuar.
- Máximo **3 roles activos** simultáneamente.
- Cambios sensibles requieren validación humana.

### Tipos de tarea (taxonomía canónica)
| Tipo | Cuándo |
|------|--------|
| `analysis` | Comprender, auditar, comparar |
| `design` | Definir estructura, contratos, árbol |
| `execution` | Crear artefactos, implementar |
| `validation` | Emitir juicio formal sobre artefacto |
| `organization` | Ordenar, empaquetar, dejar navegable |
| `system_change` | Alterar BAGO como sistema |
| `project_bootstrap` | Arrancar en repo desconocido |
| `repository_audit` | Auditar coherencia de repo |
| `history_migration` | Preservar historia operativa |

---

## 2. Agentes disponibles

### 🏛️ Familia: GOBIERNO

| Agente | ID | Propósito | Activar cuando |
|--------|----|-----------|----------------|
| **MAESTRO_BAGO** / COORDINADOR_BAGO | `role_coordinator_bago` | Interfaz principal con el usuario. Integra resultados, presenta salida coherente. | Siempre — apertura y cierre de toda sesión |
| **ORQUESTADOR_CENTRAL** | `role_orchestrator` | Clasifica tarea, elige workflow, activa roles, secuencia trabajo sin invadir fronteras. | Siempre — antes de activar producción |

### ⚙️ Familia: PRODUCCIÓN

| Agente | ID | Propósito | Activar cuando |
|--------|----|-----------|----------------|
| **ANALISTA_Contexto** | `role_analyst` | Audita, compara, diagnostica. Lee repo real. | Antes de diseñar o ejecutar algo complejo |
| **ARQUITECTO_Soluciones** | `role_architect` | Diseña límites técnicos, contratos, secuencia. | Cuando hay diseño no congelado o rediseño |
| **GENERADOR_Contenido** | `role_generator` | Produce artefactos: código, docs, scripts, configs. | Fase de ejecución/generación |
| **ORGANIZADOR_Entregables** | `role_organizer` | Ordena salidas, crea árbol, ZIP, handoff estructurado. | Cuando la salida exige orden estructural |

### 🔍 Familia: SUPERVISIÓN

| Agente | ID | Propósito | Activar cuando |
|--------|----|-----------|----------------|
| **VÉRTICE** | `role_vertice` | Detecta deriva, complejidad innecesaria, repetición, deuda. | Revisión post-sesión; sprints largos |
| **AUDITOR_CANÓNICO** | `role_auditor` | Valida conflictos semánticos, coherencia canónica. | Cambios sistémicos; validación formal |
| **CENTINELA_SINCERIDAD** | — | Honestidad y rigor — detecta simulación de progreso. | Cuando sospechas que el sistema miente |

### 🚀 Familia: BOOTSTRAP

| Agente | ID | Propósito | Activar cuando |
|--------|----|-----------|----------------|
| **ADAPTADOR_PROYECTO** | — | Inspecciona repo real → traduce a contexto operativo. | Primer contacto con repo desconocido |
| **INICIADOR_MAESTRO** | — | Arranca el maestro con objetivo, modo, roles iniciales. | Después de ADAPTADOR en cold start |
| **GUIA_VERTICE** | — | Guía hacia el siguiente paso útil. | Cuando no está claro el siguiente movimiento |

### 🔧 Familia: ESPECIALISTAS

| Agente | Propósito |
|--------|-----------|
| **INTEGRADOR_REPO** | Integración de cambios en repo, merges, conflictos |
| **REVISOR_PERFORMANCE** | Análisis de rendimiento, bundle size, métricas |
| **REVISOR_SEGURIDAD** | Scan de vulnerabilidades, secretos, permisos |
| **REVISOR_UX** | Análisis de experiencia de usuario |
| **COPILOT_ALIADO_BAGO** | Versión adaptada para GitHub Copilot CLI |

---

## 3. Workflows — cuándo usar cada uno

### Workflows Canónicos (nivel sistema)

| ID | Nombre | Cuándo | Roles mínimos |
|----|--------|--------|---------------|
| `workflow_analisis` | Análisis | Comprender, auditar, comparar | Orquestador, Analista, Validador |
| `workflow_diseno` | Diseño | Definir estructura, contratos, arquitectura | Orquestador, Analista, Arquitecto, Validador |
| `workflow_ejecucion` | Ejecución | Crear artefactos, implementar, redactar | Orquestador, Generador, Validador |
| `workflow_validacion` | Validación | Juicio formal sobre artefacto ya producido | Orquestador, Validador |
| `workflow_cambio_sistemico` | Cambio sistémico | Alterar BAGO como sistema | Orquestador, Auditor, Validador |
| `workflow_migracion_historial` | Migración histórica | Preservar historia operativa a estructuras actuales | Orquestador, Analista, Auditor, Validador |
| `workflow_bootstrap_repo_first` | Bootstrap repo-first | Repo desconocido sin contexto cargado | ADAPTADOR_PROYECTO, INICIADOR_MAESTRO |

### Workflows Tácticos (nivel sesión)

| ID | Nombre | Cuándo usar | Tip |
|----|--------|-------------|-----|
| **W1_COLD_START** | Cold Start | Repo desconocido → contexto útil en ≤1 iteración | Resultado: objetivo + restricciones + siguiente paso |
| **W2_IMPLEMENTACION_CONTROLADA** | Implementación Controlada | Tarea técnica concreta sin dispersión | Flujo: [B]entender→[A]elegir→[G]implementar→[O]cerrar |
| **W3_REFACTOR_SENSIBLE** | Refactor Sensible | Refactorizar sin romper contratos | Nunca expandir alcance sin justificación |
| **W4_DEBUG_MULTICAUSA** | Debug Multicausa | Fallos con múltiples causas posibles | Lista causas plausibles → prioriza → elimina |
| **W5_CIERRE_Y_CONTINUIDAD** | Cierre y Continuidad | Cerrar sesión con siguiente paso claro | Genera: resumen + CHG + handoff |
| **W6_IDEACION_APLICADA** | Ideación Aplicada | Explorar repo y proponer ideas priorizadas | Output: lista corta de ideas accionables para W2 |
| **W7_FOCO_SESION** | Foco de Sesión | Sesión productiva con objetivo único | Preferir sobre W1 en sesiones normales |
| **W8_EXPLORACION** | Exploración | Sin objetivo previo claro | W7-lite: ≥1 artefacto, ≥1 decisión |
| **W9_COSECHA** | Cosecha | Post-exploración libre — 3 preguntas ≤5min | Genera: sesión harvest + CHG + EVD |
| **W0_FREE_SESSION** | Sesión libre | `.bago/off` — sin control | Solo ESCENARIO-002, no en producción |

### Regla de selección rápida
```
¿Repo desconocido?          → W1 o workflow_bootstrap_repo_first
¿Tarea técnica concreta?    → W7 + W2
¿Fallos/bugs?               → W4
¿Ideas para el repo?        → W6
¿Cerrar sesión?             → W5 + W9
¿Refactorizar?              → W3
¿Cambiar el framework?      → workflow_cambio_sistemico
```

---

## 4. Herramientas por categoría

> Todas en `~/Desktop/BAGO_CAJAFISICA/.bago/tools/`

### 🔍 Diagnóstico y Auditoría
| Herramienta | Función |
|-------------|---------|
| `audit_v2.py` | Auditoría completa del proyecto |
| `check.py` | Verificación rápida de estado |
| `health_report.py` / `health_score.py` | Salud del proyecto (score numérico) |
| `doctor.py` | Diagnóstico integral — detecta problemas |
| `dead_code.py` | Código muerto en el repo |
| `duplicate_check.py` | Duplicidades en código/docs |
| `secret_scan.py` | Scan de secretos expuestos |
| `dep_audit.py` | Auditoría de dependencias |
| `license_check.py` | Verificación de licencias |
| `naming_check.py` | Convenciones de nomenclatura |
| `stale_detector.py` | Archivos/docs obsoletos |
| `hotspot.py` | Hotspots de complejidad en código |
| `debt_ledger.py` | Ledger de deuda técnica |

### 📊 Métricas y Reportes
| Herramienta | Función |
|-------------|---------|
| `metrics_dashboard.py` | Dashboard de métricas del proyecto |
| `metrics_trends.py` | Tendencias de métricas a lo largo del tiempo |
| `metrics_export.py` | Exportar métricas |
| `velocity.py` | Velocidad de desarrollo (features/sprint) |
| `size_tracker.py` | Tracking de tamaño del bundle |
| `stability_summary.py` | Resumen de estabilidad |
| `timeline.py` | Timeline de cambios |
| `efficiency_meter.py` | Eficiencia por sesión |
| `session_stats.py` | Estadísticas de sesiones |
| `stats.py` | Stats generales |
| `report_generator.py` | Generación de reportes |
| `ci_report.py` | Reporte de CI |
| `chart_engine.py` | Motor de gráficos |
| `insights.py` | Insights automáticos del proyecto |

### 🏗️ Gestión de Estado y Sesión
| Herramienta | Función |
|-------------|---------|
| `state_store.py` | Gestión de estado global |
| `session_opener.py` | Apertura de sesión con preflight |
| `session_preflight.py` | Validación antes de abrir sesión |
| `session_details.py` | Detalles de sesión actual |
| `snapshot.py` | Snapshot del estado |
| `archive.py` | Archivado de sesiones |
| `iteration_logger.py` | Log de iteraciones |
| `notes.py` | Notas de sesión |
| `remind.py` | Recordatorios de continuidad |

### 🚀 Sprint y Backlog
| Herramienta | Función |
|-------------|---------|
| `sprint_manager.py` | Gestión de sprints |
| `emit_ideas.py` | Emitir ideas al backlog |
| `cosecha.py` | Cosecha contextual post-exploración |
| `goals.py` | Gestión de objetivos |
| `target_selector.py` | Selector de target/objetivo |
| `show_task.py` | Mostrar tarea actual |
| `generate_task_closure.py` | Generar cierre de tarea |

### 🔧 Herramientas de Código
| Herramienta | Función |
|-------------|---------|
| `refactor_suggest.py` | Sugerencias de refactoring |
| `test_gen.py` / `testgen.py` | Generación de tests |
| `type_check.py` | Verificación de tipos |
| `complexity.py` | Análisis de complejidad ciclomática |
| `doc_coverage.py` | Cobertura de documentación |
| `code_review.py` | Revisión de código |
| `pre_commit_gen.py` | Generación de hooks pre-commit |
| `js_ast_scanner.js` / `ts_ast.js` | AST scanners para JS/TS |
| `coverage_gate.py` | Gate de cobertura de tests |
| `smoke_runner.py` | Runner de smoke tests |
| `integration_tests.py` | Tests de integración |
| `autofix.py` | Corrección automática de problemas |
| `auto_heal.py` | Auto-reparación de estado |
| `patch.py` | Aplicar parches |
| `legacy_fixer.py` | Arreglar código legacy |

### 🗺️ Contexto y Navegación
| Herramienta | Función |
|-------------|---------|
| `context_collector.py` | Recopilar contexto del proyecto |
| `context_detector.py` | Detectar contexto automáticamente |
| `context_map.py` | Mapa de contexto |
| `impact_engine.py` | Análisis de impacto de cambios |
| `impact_map.py` | Mapa de impacto |
| `risk_matrix.py` | Matriz de riesgo |
| `flow.py` | Visualización de flujos |
| `workspace_selector.py` | Selector de workspace |
| `repo_context_guard.py` | Guardia de contexto de repo |
| `repo_runner.py` | Runner en contexto de repo |
| `tool_search.py` | Búsqueda de herramientas |
| `bago_search.py` | Búsqueda en el framework BAGO |
| `intent_router.py` | Routing de intenciones |
| `workflow_selector.py` | Selector de workflow |

### 🌐 Integración Externa
| Herramienta | Función |
|-------------|---------|
| `git_context.py` | Contexto Git (branch, commits, diff) |
| `gh_integration.py` | GitHub integration (PRs, issues) |
| `ci_generator.py` | Generación de configuración CI |
| `ci_baseline.py` | Baseline de CI |
| `install_deps.py` | Instalación de dependencias |
| `env_check.py` | Verificación de variables de entorno |
| `api_check.py` | Verificación de APIs externas |
| `sync_badges.py` | Sincronización de badges README |
| `validate_pack.py` | Validación del pack BAGO |
| `validate_manifest.py` | Validación del manifest |
| `validate_state.py` | Validación del estado |

### 🎮 Herramientas Especiales (proyectos creativos)
| Herramienta | Fuente | Función |
|-------------|--------|---------|
| `bago_chat_server.py` | CAJAFISICA | Servidor de chat con contexto BAGO |
| `generate_bago_evolution_report.py` | CAJAFISICA | Reporte de evolución del framework |
| `competition_report.py` | CAJAFISICA | Reporte para competición |
| `personality_panel.py` | CAJAFISICA | Panel de personalidad del proyecto |
| `pack_dashboard.py` | CAJAFISICA | Dashboard del pack |
| `findings_engine.py` | CAJAFISICA | Motor de hallazgos |
| `multi_scan.py` | CAJAFISICA | Scan múltiple paralelo |

---

## 5. Estructuras de plan / plantillas

### Plantilla W7 — Sesión con foco (uso más frecuente)
```
En esta sesión voy a [VERBO] [OBJETO] para que [CRITERIO DE DONE].

Roles: [max 2]
Artefactos a producir: [lista concreta]
Tipo de tarea: [execution|design|analysis|...]
```

### Plantilla Sprint (estilo BIANCA)
```json
{
  "sprint": NNN,
  "escena": "NombreScene",
  "efecto": "nombreEfecto — descripción breve",
  "bundle_antes": X KB,
  "bundle_despues": Y KB
}
```

### Plantilla Sesión formal (estilo CAOS/DERIVA)
```
ID: SES-W2-[PROYECTO]-[OBJETIVO]-[FECHA]-001
Workflow: w2_implementacion_controlada
Roles: ARQUITECTO, GENERADOR, VALIDADOR
Tarea type: execution
Cambios: CHG-[PROYECTO]-[DESC]-[FECHA]-001
Criterio done: [específico y verificable]
Continuidad: docs/CONTINUIDAD_SES-[ID].md
```

### Plantilla Cambio (CHG)
```
ID: CHG-[PROYECTO]-[DESC]-[FECHA]-NNN
Tipo: patch|minor|major
Descripción: [qué cambió]
Archivos: [lista]
Evidencia: EVD-xxx
Estado: GO|GO_WITH_RESERVATIONS|KO
```

### Plantilla Idea (backlog)
```json
{
  "id": "IDEA-NNN",
  "title": "Título corto",
  "category": "game_feel|architecture|ux|performance|...",
  "priority": "alta|media|baja",
  "status": "pending|in_progress|done",
  "description": "Descripción funcional",
  "implementation": "Cómo hacerlo técnicamente",
  "files": ["path/al/archivo"],
  "effort": "pequeño|medio|grande"
}
```

### Plantilla Backlog (estilo BIANCA sprint-series)
```
## ALTA PRIORIDAD
- Sprint NNN — [Escena]: [efecto/feature] — [impacto]

## MEDIA PRIORIDAD
- Sprint NNN — [descripción]

## IDEAS FUTURAS
- [escena]: [idea concreta]

## DEUDA TÉCNICA
- [archivo] línea X: [descripción del problema]
```

### Flujo de plan completo (multi-sesión)
```
1. [W1/W8] Exploración → entender estado real
2. [W6]    Ideación    → lista de ideas priorizadas
3. [W7+W2] Ejecución   → implementar idea elegida
4. [W5+W9] Cierre      → estado + continuidad + cosecha
```

---

## 6. Proyectos conocidos + patrones

### BIANCA — El Juego
- **Stack**: TypeScript + Vite + Canvas 2D isométrico
- **Patrón**: Sprint-series (197-287+), cada sprint = 1 efecto FX o feature
- **Límite**: Bundle 325 KB (actualmente 326.47 KB — atención)
- **Sprites**: Method 6 (Codex), frames_m6, 4 válidos / 28 pendientes
- **Estado**: `.bago/state/global_state.json`

### DERIVA — RPG
- **Stack**: React/TypeScript, monorepo, engine + ui-runtime separados
- **Sprint activo**: 14 | 446 tests | bundle 470 KB
- **Patrón**: Intervenciones numeradas por componente (Engine.ts, GameController.ts, etc.)
- **Estado**: `/Volumes/Warehouse/AMTEC/DERIVA/.bago/state/`

### CAOS — El Sigarrito
- **Stack**: React/TypeScript, SQLite + IndexedDB
- **Sprint**: W2 completada | Cap. 1 jugable | branch alpha-0
- **Patrón**: Sesiones W2 formales con CHG tracking
- **Ideas**: 18 implementadas, backlog en `ideas/caos_game_ideas.json`

### TPV Contabilidad
- **Stack**: Contabilidad / TPV
- **BAGO**: Instancia en Documents + Warehouse (sincronizadas)

### amTech / Pandamien
- **Stack**: Documentación técnica
- **BAGO**: `/Volumes/Warehouse/AMTEC/2026/ABRIL2026/`

### CESAR_WOODS
- **Stack**: Desconocido (tiene `play.sh` y `play.command` → ejecutable)
- **BAGO**: Instancia completa en `/Volumes/Warehouse/CESAR_WOODS/`

---

## 7. Reglas de activación y gobierno

### Matriz de enrutado
| Tipo de tarea | Riesgo | Workflow | Escalado típico |
|---------------|--------|----------|-----------------|
| analysis | bajo | workflow_analisis | Arquitecto |
| design | medio | workflow_diseno | Auditor Canónico |
| execution | bajo | workflow_ejecucion | Organizador |
| execution | alto | workflow_ejecucion | Auditor Canónico |
| validation | bajo | workflow_validacion | Auditor Canónico |
| organization | bajo | workflow_ejecucion | Arquitecto |
| system_change | alto | workflow_cambio_sistemico | Arquitecto, Vértice |
| history_migration | medio/alto | workflow_migracion_historial | Arquitecto, Organizador |
| project_bootstrap | medio | workflow_bootstrap_repo_first | Analista |

### Cuándo escalar
- → **Arquitecto**: si se rediseña la estructura
- → **Auditor**: si hay conflicto semántico o de rutas
- → **Vértice**: si el problema revela pauta repetida de deuda
- → **Organizador**: cuando la salida exige árbol, ZIP o handoff

### Anti-patrones a evitar
- Tratar legado como basura que molesta
- Tratar legado como estado vivo
- Generar sin haber inspeccionado el repo
- Cerrar una ruta sin validación
- Confundir documentación con progreso
- Simular comprensión sin haber leído

### Resultados de validación
- `GO` — proceder
- `GO_WITH_RESERVATIONS` — proceder con cuidado
- `KO` — no proceder

---

## 8. Instancias .bago en el sistema

| Ruta | Versión | Estado | Uso |
|------|---------|--------|-----|
| `~/bago-framework/.bago` | 3.0 | **CANÓNICA MÁS COMPLETA** | Framework de referencia |
| `~/Desktop/BAGO_CAJAFISICA/.bago` | 3.0 | Activo | Framework + tools completos |
| `~/Desktop/BAGO_CAJAFISICA/RELEASE/bago-framework/.bago` | 3.0 | Release | Versión distribuible |
| `BAGO_5_OFICIAL/.bago` | 2.2.2 | Canónica V5 | Última línea canónica AMTEC |
| `BAGO_4_OFICIAL/.bago` | 2.3-clean | Consolidada | Anterior a V5 |
| `CAOS_SIGARRITO/.bago` | 2.5-stable | Proyecto activo | CAOS game |
| `TEST_BAGO_03(IMG)/.bago` | — | Test activo | Pipeline de imágenes |
| `TEST_BAGO_01/.bago` | — | Test | Seed template |
| `TEST_BAGO_02/.bago` | — | Test | CAOS testing |
| `DERIVA/.bago` | — | Estado only | Audits + state |
| `CESAR_WOODS/.bago` | 3.0 | Proyecto | Play framework |
| `TPV_Contabilidad/.bago` | — | Activo | Contabilidad |
| `~/.bago` | — | Runtime | Plans + sessions locales |

### Framework canónico de referencia
```
~/bago-framework/.bago/
├── AGENT_START.md          ← Punto de entrada para agentes
├── pack.json               ← Manifiesto completo del framework
├── agents/                 ← Todos los agentes definidos
├── core/
│   ├── 00_CEREBRO_BAGO.md  ← Núcleo B·A·G·O
│   ├── orchestrator/       ← Orquestador + matriz enrutado
│   ├── supervision/        ← Vértice + alertas
│   ├── workflows/          ← 7 workflows canónicos
│   └── canon/              ← Taxonomía + contratos + protocolo
├── workflows/              ← W0-W9 tácticos
├── roles/                  ← gobierno, producción, supervisión, especialistas
├── tools/                  ← 80+ herramientas Python
├── docs/                   ← Canon, glosario, mapa del sistema
├── knowledge/              ← Aprendizajes del framework
└── state/                  ← Estado activo
```

---

## REFERENCIA RÁPIDA — Sugiero usar cuando...

| Situación | Qué sugerir |
|-----------|-------------|
| "no sé por dónde empezar" | W1_COLD_START + ADAPTADOR_PROYECTO |
| "quiero implementar X" | W7_FOCO_SESION + W2_IMPLEMENTACION_CONTROLADA |
| "tengo un bug difícil" | W4_DEBUG_MULTICAUSA + ANALISTA_Contexto |
| "qué ideas hay para mejorar" | W6_IDEACION_APLICADA + GENERADOR_Contenido |
| "quiero refactorizar" | W3_REFACTOR_SENSIBLE + ARQUITECTO_Soluciones |
| "cerrar la sesión bien" | W5_CIERRE_Y_CONTINUIDAD + W9_COSECHA |
| "algo va mal en el framework" | VÉRTICE + CENTINELA_SINCERIDAD |
| "auditar el proyecto" | `audit_v2.py` + `health_report.py` |
| "ver métricas" | `metrics_dashboard.py` + `velocity.py` |
| "ideas al backlog" | `emit_ideas.py` + `cosecha.py` |
| "analizar impacto de cambio" | `impact_engine.py` + `risk_matrix.py` |
| "deuda técnica" | `debt_ledger.py` + `hotspot.py` + VÉRTICE |
| "generar sprites/imágenes" | Ver `toolkit.md` — 11 métodos disponibles |


---

## ACTUALIZACIÓN 2026-05-05 — Secuencias y Absorción Cross-Disco

### Nuevos artefactos absorbidos

| Artefacto | Origen | Tipo |
|-----------|--------|------|
| `sequences_catalog.md` | Esta sesión | 10 secuencias ordenadas de comandos |
| `GUIA_VERTICE.md` | Warehouse/ABRIL2026 | Rol de supervisión evolutiva |
| `repo_context_guard.py` | Warehouse/TPV | Fingerprint de repo, bloquea drift de contexto |
| `launch_workflow_maestro.sh` | Warehouse/TPV | Lanzador táctico con validación canónica |
| `inspect_workflow.py` | Warehouse/TPV | Guía interactiva de workflows W1-W10 |
| `bago_consistency_check.py` | Esta sesión (fix audit) | Guard anti-drift CI/registry/README |

### Patrones de datos nuevos aprendidos

- **Sprint tracking (DERIVA):** `completed_interventions[]` en `global_state.json` — historial por sprint con prefijo `--- SPRINT N ---`
- **Ideas estructuradas (CAoS):** formato JSON `{id, title, category, priority, status, description, implementation, files, effort}`  
- **Baseline congelada (CESAR_WOODS):** v2.2.1 como referencia de comparación. Solo `validate_*.py`, sin modificación.

### Estado del framework tras auditoría MarcValls

- 7 bugs corregidos (5 reales + 1 N/A + 1 guard nuevo)
- Registry: 36 comandos · 112 tools · 20 workflows
- CI real operativo en `.github/workflows/bago.yml`
- `bago consistency --json` → `{"status": "ok", "errors": 0, "warnings": 0}`

### Secuencias disponibles

Ver `sequences_catalog.md` para el catálogo completo de 10 secuencias (SEQ-01 a SEQ-10) con comandos ordenados, criterios de salida y notas de campo cross-disco.

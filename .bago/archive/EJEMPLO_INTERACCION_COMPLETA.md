# BAGO: Ejemplo Completo de Interacción

## Escenario: Analizar un proyecto con errores y dejar que BAGO orqueste

---

## PASO 1: Iniciar BAGO desde la línea de comandos

```powershell
PS C:\Marc_max_20gb> cd .bago
PS C:\Marc_max_20gb\.bago> .\bago.ps1 help
```

**OUTPUT:**
```
╔════════════════════════════════════════════════╗
║           BAGO - Code Quality Leader           ║
║        Orquestador de Agentes y Roles          ║
╚════════════════════════════════════════════════╝

Comandos disponibles:
  help                - Mostrar esta ayuda
  analyze <path>      - Analizar proyecto
  list-agents         - Listar AGENTS disponibles
  list-roles          - Listar ROLES disponibles
  new-agent <nombre>  - Crear nuevo AGENT
  remove-agent <nom>  - Eliminar AGENT
  cli                 - Menú interactivo
```

---

## PASO 2: Ver los AGENTS disponibles

```powershell
PS C:\Marc_max_20gb\.bago> .\bago.ps1 list-agents
```

**OUTPUT:**
```
╔════════════════════════════════════════════════╗
║              AGENTS DISPONIBLES                ║
╚════════════════════════════════════════════════╝

[1] SECURITY_ANALYZER
    Categoría: Seguridad
    Descripción: Detecta vulnerabilidades (XSS, SQL Injection, credentials, HTTP insecurity)
    Archivo: .\agents\security_analyzer.py
    Estado: ✓ Activo

[2] LOGIC_CHECKER
    Categoría: Lógica
    Descripción: Busca TODOs, inconsistencias, lógica inválida
    Archivo: .\agents\logic_checker.py
    Estado: ✓ Activo

[3] SMELL_DETECTOR
    Categoría: Calidad
    Descripción: Detecta variables globales, complejidad excesiva, duplicación de lógica
    Archivo: .\agents\smell_detector.py
    Estado: ✓ Activo

[4] DUPLICATION_FINDER
    Categoría: Duplicación
    Descripción: Busca código duplicado en ficheros
    Archivo: .\agents\duplication_finder.py
    Estado: ✓ Activo

Total: 4 AGENTS disponibles
```

---

## PASO 3: Ver los ROLES disponibles

```powershell
PS C:\Marc_max_20gb\.bago> .\bago.ps1 list-roles
```

**OUTPUT:**
```
╔════════════════════════════════════════════════╗
║             ROLES DISPONIBLES                  ║
╚════════════════════════════════════════════════╝

FAMILIA: GOBIERNO
  • MAESTRO_BAGO (Síntesis final, verdicts)
  • ORQUESTADOR_CENTRAL (Orquestación de workflow)

FAMILIA: ESPECIALISTAS
  • REVISOR_SEGURIDAD (Evalúa vulnerabilidades)
  • REVISOR_PERFORMANCE (Evalúa rendimiento)
  • REVISOR_UX (Evalúa experiencia)
  • INTEGRADOR_REPO (Integración de repositorio)

FAMILIA: SUPERVISIÓN
  • AUDITOR_CANONICO (Auditoría de normas)
  • CENTINELA_SINCERIDAD (Control de calidad)
  • VERTICE (Decisión final)

FAMILIA: PRODUCCIÓN
  • ANALISTA (Análisis de requisitos)
  • ARQUITECTO (Decisiones arquitectónicas)
  • GENERADOR (Generación de código)
  • ORGANIZADOR (Organización de proyecto)
  • VALIDADOR (Validación final)

Total: 16 ROLES disponibles
```

---

## PASO 4: Analizar un proyecto

```powershell
PS C:\Marc_max_20gb\.bago> .\bago.ps1 analyze ..\typing-course\src
```

**OUTPUT - FASE 1: EJECUTAR AGENTS**
```
╔════════════════════════════════════════════════�════════════════════════════════════════════════╗
║                    BAGO INICIANDO ANÁLISIS                                                      ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝

Directorio: C:\Marc_max_20gb\typing-course\src
Archivos a analizar: lesson.js, utils.js, app.js (3 archivos)

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FASE 1: EJECUTANDO AGENTS EN PARALELO (ORQUESTACIÓN)                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

→ [SECURITY_ANALYZER] Iniciando análisis de seguridad...
→ [LOGIC_CHECKER] Iniciando verificación de lógica...
→ [SMELL_DETECTOR] Iniciando detección de olores...
→ [DUPLICATION_FINDER] Iniciando búsqueda de duplicación...

  ✓ [SECURITY_ANALYZER] Completado - 2 hallazgos
  ✓ [LOGIC_CHECKER] Completado - 5 hallazgos
  ✓ [SMELL_DETECTOR] Completado - 3 hallazgos
  ✓ [DUPLICATION_FINDER] Completado - 5 hallazgos

RESUMEN DE HALLAZGOS:
```

**OUTPUT - FASE 2: HALLAZGOS AGREGADOS POR SEVERITY**
```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FASE 2: HALLAZGOS AGREGADOS (15 TOTAL)                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

🔴 HALLAZGOS CRÍTICOS: 0
   (Bloquearían producción)

🔴 HALLAZGOS ALTOS: 2
   [1] lesson.js:42 - XSS_VULNERABILITY (SECURITY_ANALYZER)
       Descripción: Posible vulnerabilidad de XSS - innerHTML sin sanitizar
       Línea: element.innerHTML = userInput;
       Recomendación: Usar textContent o DOMPurify
       
   [2] lesson.js:78 - HTTP_INSECURITY (SECURITY_ANALYZER)
       Descripción: URL hardcodeada sin HTTPS
       Línea: const url = "http://api.example.com/data";
       Recomendación: Cambiar a HTTPS

🟡 HALLAZGOS MEDIOS: 8
   [3] lesson.js:15 - TODO_COMMENT (LOGIC_CHECKER)
       Descripción: Comentario TODO sin resolver
       Línea: // TODO: mejorar rendimiento aquí
       
   [4] lesson.js:33 - INCONSISTENT_RETURN (LOGIC_CHECKER)
       Descripción: Función retorna undefined a veces
       Línea: if (condition) return value; // sin else
       
   [5] utils.js:12 - GLOBAL_VARIABLE (SMELL_DETECTOR)
       Descripción: Variable global detectada
       Línea: globalCounter = 0;
       
   [6] utils.js:45 - COMPLEX_FUNCTION (SMELL_DETECTOR)
       Descripción: Función con complejidad ciclomática > 10
       Línea: function processData(...) { ... }
       
   [7] app.js:8 - DUPLICATED_LOGIC (DUPLICATION_FINDER)
       Descripción: Lógica duplicada encontrada
       Comparado con: lesson.js:50
       
   [8] app.js:22 - DUPLICATED_CODE_BLOCK (DUPLICATION_FINDER)
       Descripción: Bloque de código duplicado (5 líneas idénticas)
       Comparado con: utils.js:30

🟢 HALLAZGOS BAJOS: 5
   [9-13] Otros hallazgos de bajo impacto...
```

**OUTPUT - FASE 3: CONSULTAR ROLES**
```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FASE 3: CONSULTANDO ROLES (GOBERNANZA)                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

[ROL 1] REVISOR_SEGURIDAD analizando hallazgos...
├─ Evaluando: XSS_VULNERABILITY (HIGH) → RECHAZADO ❌
├─ Evaluando: HTTP_INSECURITY (HIGH) → RECHAZADO ❌
├─ Evaluando: GLOBAL_VARIABLE (MEDIUM) → ACEPTADO ✓
└─ VEREDICTO: NOT_READY
   Razón: Vulnerabilidades críticas deben corregirse ANTES de producción
   Severidad: CRITICAL
   Acción: Solicitar corrección de XSS y HTTPS

[ROL 2] REVISOR_PERFORMANCE analizando hallazgos...
├─ Evaluando: COMPLEX_FUNCTION (MEDIUM) → CONDITIONAL ⚠️
├─ Evaluando: DUPLICATED_CODE_BLOCK (MEDIUM) → CONDITIONAL ⚠️
└─ VEREDICTO: CONDITIONAL
   Razón: Se debe refactorizar para mejorar rendimiento
   Severidad: HIGH
   Acción: Refactorización recomendada

[ROL 3] MAESTRO_BAGO sintetizando veredictos...
├─ REVISOR_SEGURIDAD: NOT_READY (bloquea)
├─ REVISOR_PERFORMANCE: CONDITIONAL (permite con revisión)
└─ VEREDICTO FINAL: NOT_READY
   Razón: Existen bloqueadores de seguridad
   Estado: RECHAZADO PARA PRODUCCIÓN
   Próximos pasos: Resolver hallazgos de seguridad
```

**OUTPUT - FASE 4: REPORTE FINAL**
```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FASE 4: REPORTE FINAL Y ACCIONES                                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════════════════
                              RESUMEN EJECUTIVO
═══════════════════════════════════════════════════════════════════════════════════════════════════

Estado del Proyecto: ❌ NOT_READY (No listo para producción)

Hallazgos Totales: 15
├─ CRÍTICOS: 0
├─ ALTOS: 2 (Bloqueadores de seguridad)
├─ MEDIOS: 8
└─ BAJOS: 5

Veredictos de Roles:
├─ REVISOR_SEGURIDAD: NOT_READY ❌
├─ REVISOR_PERFORMANCE: CONDITIONAL ⚠️
└─ MAESTRO_BAGO (Síntesis): NOT_READY ❌

═══════════════════════════════════════════════════════════════════════════════════════════════════
                            ACCIONES RECOMENDADAS
═══════════════════════════════════════════════════════════════════════════════════════════════════

BLOQUEOS (Deben resolverse):
[1] ✋ SEGURIDAD: Corregir XSS en lesson.js:42
    Cambiar: element.innerHTML = userInput;
    A:      element.textContent = userInput;  // O usar DOMPurify
    Impacto: CRÍTICO - Impide producción

[2] ✋ SEGURIDAD: Cambiar HTTP a HTTPS en lesson.js:78
    Cambiar: const url = "http://api.example.com/data";
    A:      const url = "https://api.example.com/data";
    Impacto: CRÍTICO - Impide producción

MEJORAS RECOMENDADAS (Para siguiente release):
[3] 🔧 Resolver TODO en lesson.js:15
[4] 🔧 Refactorizar función en utils.js:45 (complejidad alta)
[5] 🔧 Eliminar duplicación de código en app.js

═══════════════════════════════════════════════════════════════════════════════════════════════════
Timestamp: 2026-04-28 05:18:38
Duración análisis: 2.3 segundos
Próximo análisis: En cualquier momento (ejecutar .\bago.ps1 analyze <path>)
═══════════════════════════════════════════════════════════════════════════════════════════════════
```

---

## PASO 5: Correcciones y Re-análisis

El desarrollador ve los hallazgos y corrige los dos bloqueadores de seguridad:

```powershell
# Editar lesson.js para corregir XSS
# Cambiar línea 42 de: element.innerHTML = userInput;
# A: element.textContent = userInput;

# Editar lesson.js para corregir HTTP
# Cambiar línea 78 de: const url = "http://api.example.com/data";
# A: const url = "https://api.example.com/data";

PS C:\Marc_max_20gb\.bago> .\bago.ps1 analyze ..\typing-course\src
```

**OUTPUT - ANÁLISIS DESPUÉS DE CORRECCIONES:**
```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ BAGO INICIANDO ANÁLISIS (SEGUNDO INTENTO)                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

FASE 1: EJECUTANDO AGENTS...
  ✓ [SECURITY_ANALYZER] Completado - 0 hallazgos (MEJORÓ ✓)
  ✓ [LOGIC_CHECKER] Completado - 5 hallazgos
  ✓ [SMELL_DETECTOR] Completado - 3 hallazgos
  ✓ [DUPLICATION_FINDER] Completado - 5 hallazgos

RESUMEN: 13 hallazgos (antes: 15) - 2 resueltos ✓

FASE 2: HALLAZGOS (ORDENADOS POR SEVERIDAD)...
  • HALLAZGOS CRÍTICOS: 0 ✓ (Mejoró)
  • HALLAZGOS ALTOS: 0 ✓ (Mejoró)
  • HALLAZGOS MEDIOS: 8
  • HALLAZGOS BAJOS: 5

FASE 3: CONSULTANDO ROLES...

[ROL 1] REVISOR_SEGURIDAD
├─ Hallazgos CRÍTICOS: 0 ✓
├─ Hallazgos ALTOS: 0 ✓
└─ VEREDICTO: READY ✓

[ROL 2] REVISOR_PERFORMANCE
├─ Hallazgos MEDIOS: 8 (aceptable)
└─ VEREDICTO: CONDITIONAL ⚠️

[ROL 3] MAESTRO_BAGO (Síntesis)
└─ VEREDICTO FINAL: CONDITIONAL ⚠️

═══════════════════════════════════════════════════════════════════════════════════════════════════
                           ESTADO FINAL: CONDITIONAL
═══════════════════════════════════════════════════════════════════════════════════════════════════

Significado: ✓ Listo para producción con condiciones
Hallazgos: 13 totales (Todos medios o bajos - ninguno crítico)

Condiciones:
1. ✓ Seguridad: CLEARED (sin vulnerabilidades)
2. ⚠️ Rendimiento: Refactorizar antes de próxima release
   • Función compleja en utils.js:45
   • Código duplicado en app.js

RECOMENDACIÓN: 
✅ PUEDES PASAR A PRODUCCIÓN
⚠️  Pero planifica refactorización para siguiente sprint

═══════════════════════════════════════════════════════════════════════════════════════════════════
```

---

## PASO 6: Usar Menú Interactivo

```powershell
PS C:\Marc_max_20gb\.bago> .\cli.ps1
```

**OUTPUT:**
```
╔════════════════════════════════════════════════╗
║            BAGO - MENÚ INTERACTIVO             ║
║         Orquestador de Agentes y Roles         ║
╚════════════════════════════════════════════════╝

[1] Analizar un proyecto
[2] Ver AGENTS disponibles
[3] Ver ROLES disponibles
[4] Crear nuevo AGENT
[5] Ver estadísticas
[6] Salir

Selecciona una opción: 1

╔════════════════════════════════════════════════╗
║         ANALIZAR PROYECTO CON BAGO             ║
╚════════════════════════════════════════════════╝

Ruta del proyecto (ej: ..\typing-course\src): ..\typing-course\src

[ANALIZANDO]...
(Se ejecuta el workflow completo como arriba)
```

---

## RESUMEN DEL FLUJO COMPLETO

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USUARIO INICIA BAGO                                          │
│    ↓                                                             │
│ 2. BAGO CARGA MANIFIESTOS                                       │
│    - 4 AGENTS disponibles                                       │
│    - 16 ROLES disponibles                                       │
│    ↓                                                             │
│ 3. USUARIO EJECUTA: analyze <directorio>                        │
│    ↓                                                             │
│ 4. ORQUESTADOR LANZA 4 AGENTS EN PARALELO                       │
│    ├─ SECURITY_ANALYZER → Encuentra vulnerabilidades           │
│    ├─ LOGIC_CHECKER → Encuentra TODOs e inconsistencias        │
│    ├─ SMELL_DETECTOR → Encuentra variables globales            │
│    └─ DUPLICATION_FINDER → Encuentra código duplicado          │
│    ↓                                                             │
│ 5. HALLAZGOS SE AGREGAN Y ORDENAN POR SEVERIDAD                │
│    (CRÍTICO > ALTO > MEDIO > BAJO)                             │
│    ↓                                                             │
│ 6. ROLE ORCHESTRATOR CONSULTA 3 ROLES PRINCIPALES              │
│    ├─ REVISOR_SEGURIDAD → Evalúa vulnerabilidades             │
│    ├─ REVISOR_PERFORMANCE → Evalúa rendimiento                │
│    └─ MAESTRO_BAGO → Sintetiza veredictos finales             │
│    ↓                                                             │
│ 7. CADA ROL EMITE VEREDICTO                                     │
│    READY / CONDITIONAL / NOT_READY                             │
│    ↓                                                             │
│ 8. MAESTRO_BAGO SINTETIZA:                                     │
│    - Si ALGUNO = NOT_READY → Final = NOT_READY                │
│    - Si ALGUNO = CONDITIONAL → Final = CONDITIONAL            │
│    - Si TODOS = READY → Final = READY                         │
│    ↓                                                             │
│ 9. REPORTE FINAL CON:                                          │
│    - Resumen ejecutivo                                          │
│    - Hallazgos detallados                                       │
│    - Acciones bloqueantes vs recomendaciones                    │
│    - Próximos pasos                                             │
│    ↓                                                             │
│ 10. USUARIO IMPLEMENTA CORRECCIONES                             │
│    ↓                                                             │
│ 11. USUARIO RE-EJECUTA: analyze <directorio>                   │
│    (Vuelve al paso 4 con código mejorado)                      │
│    ↓                                                             │
│ 12. VEREDICTO MEJORA → READY o CONDITIONAL                     │
│    ✓ Veredicto de ejemplo para producción condicionada           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Conceptos Clave Demostrados

| Concepto | En el Ejemplo |
|----------|--------------|
| **Orquestación de AGENTS** | Los 4 agents (security, logic, smell, duplication) se ejecutan automáticamente |
| **Liderazgo de BAGO** | BAGO coordina agents y roles, NO hace análisis directo |
| **Factory Pattern** | Agents y roles registrados en manifiestos, descubiertos dinámicamente |
| **Gobernanza por Roles** | Cada rol tiene dominio específico y emite veredicto independiente |
| **Severidad Jerárquica** | CRÍTICO bloquea, ALTO requiere acción, MEDIO es recomendado, BAJO es informativo |
| **Síntesis de Veredictos** | MAESTRO_BAGO combina veredictos de múltiples roles en decisión final |
| **Flujo Iterativo** | Usuario corrige, re-analiza, mejora veredictos progresivamente |
| **Reporte Accionable** | Hallazgos incluyen línea de código, recomendación clara, impacto |

---

**¡BAGO en acción!** 🎯

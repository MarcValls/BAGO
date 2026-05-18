# BAGO Role Factory - Documentación Completa

## Estructura de Roles

BAGO tiene una **fábrica de roles** con 4 familias de especialistas:

### 1. GOBIERNO (Government)
Roles que gobiernan el sistema central:
- **MAESTRO_BAGO** — Interfaz principal, síntesis de verdicts
- **ORQUESTADOR_CENTRAL** — Orquestación central de flujos

### 2. ESPECIALISTAS (Specialists)
Roles que analizan dominios específicos:
- **REVISOR_SEGURIDAD** — Evaluación de seguridad
- **REVISOR_PERFORMANCE** — Evaluación de performance
- **REVISOR_UX** — Evaluación de experiencia de usuario
- **INTEGRADOR_REPO** — Integración de repositorio

### 3. SUPERVISIÓN (Supervision)
Roles que verifican calidad y canonicidad:
- **AUDITOR_CANONICO** — Valida conformidad con canon
- **CENTINELA_SINCERIDAD** — Verifica sinceridad del análisis
- **VERTICE** — Punto máximo de escalación

### 4. PRODUCCIÓN (Production)
Roles que operan en producción:
- **ANALISTA** — Análisis contextual
- **ARQUITECTO** — Decisiones arquitectónicas
- **GENERADOR** — Generación de código/contenido
- **ORGANIZADOR** — Organización de entregas
- **VALIDADOR** — Validación final

---

## Plantilla de Rol BAGO

Ubicación: `.bago/roles/ROLE_TEMPLATE.md`

Estructura canónica que todo rol debe seguir:

```markdown
# {NOMBRE_ROL}

## Identidad
- id: role_{family}_{name}
- family: {gobierno|especialistas|supervision|produccion}
- version: 2.5-stable

## Propósito
{Descripción clara de qué hace}

## Alcance
- {Responsabilidad 1}
- {Responsabilidad 2}
- {Responsabilidad 3}

## Límites
- {Lo que NO hace}
- {Lo que NO valida}
- {Lo que NO puede decidir}

## Entradas
- {Qué información recibe}
- {Qué artefactos procesa}

## Salidas
- {Qué produce}
- {Formato de verdicts}
- {Recomendaciones}

## Activación
{Cuándo se activa este rol}

## No Activación
{Cuándo NO debe activarse}

## Dependencias
- {Roles o systems que necesita}
- {Canon o reglas que sigue}

## Criterio de Éxito
{Cuándo se considera exitoso}
```

---

## Factory de Roles (`role_factory.py`)

Ubicación: `.bago/roles/role_factory.py`

### Comandos Disponibles

```bash
# Crear nuevo rol
python role_factory.py create --family especialistas --name "mi_rol"

# Validar estructura de rol
python role_factory.py validate ROLE_NAME.md

# Listar todos los roles
python role_factory.py list

# Listar por familia
python role_factory.py list --family especialistas
python role_factory.py list --family gobierno
python role_factory.py list --family supervision
python role_factory.py list --family produccion

# Obtener detalles de un rol
python role_factory.py describe MAESTRO_BAGO
```

### Funcionamiento

La factory:
1. **Crea roles** usando plantilla estándar
2. **Valida estructura** (todas 10 secciones obligatorias)
3. **Registra en manifest** (`.bago/roles/manifest.json`)
4. **Genera ID único** (role_{family}_{name})
5. **Persiste rol** en subcarpeta según familia

---

## Manifest de Roles

Ubicación: `.bago/roles/manifest.json`

Ejemplo:
```json
{
  "roles": {
    "role_gobierno_maestro_bago": {
      "name": "MAESTRO_BAGO",
      "family": "gobierno",
      "version": "2.5-stable",
      "created": "2026-01-15T10:30:00Z",
      "updated": "2026-04-28T05:00:00Z",
      "status": "active",
      "sections": 10
    },
    "role_especialistas_revisor_seguridad": {
      "name": "REVISOR_SEGURIDAD",
      "family": "especialistas",
      "version": "2.5-stable",
      "created": "2026-01-20T14:15:00Z",
      "updated": "2026-04-28T05:00:00Z",
      "status": "active",
      "sections": 10
    }
  },
  "total_roles": 16,
  "by_family": {
    "gobierno": 2,
    "especialistas": 4,
    "supervision": 3,
    "produccion": 5,
    "custom": 0
  }
}
```

---

## Ciclo de Vida de un Rol

### 1. Creación
```bash
python role_factory.py create --family especialistas --name "performance_auditor"
```
Genera: `.bago/roles/especialistas/PERFORMANCE_AUDITOR.md`

### 2. Definición (10 secciones obligatorias)
- Identidad (id, family, version)
- Propósito (qué hace)
- Alcance (responsabilidades)
- Límites (qué no hace)
- Entradas (qué recibe)
- Salidas (qué produce)
- Activación (cuándo actúa)
- No Activación (cuándo no)
- Dependencias (de qué depende)
- Criterio de Éxito (cómo sabe que lo hizo bien)

### 3. Validación
```bash
python role_factory.py validate PERFORMANCE_AUDITOR.md
```
Verifica:
- Todas 10 secciones presentes
- Identidad válida (role_family_name)
- Markdown bien formado

### 4. Registro en Manifest
Factory registra automáticamente en `manifest.json`

### 5. Activación
En code_quality_orchestrator:
```powershell
$securityVerdict = Invoke-SecurityReviewer -Findings $findings
$performanceVerdict = Invoke-PerformanceReviewer -Findings $findings
$maestroVerdict = Invoke-MAESTROBago -SecurityVerdict $securityVerdict -PerformanceVerdict $performanceVerdict
```

### 6. Emisión de Verdicts
Cada rol retorna:
```json
{
  "role": "REVISOR_SEGURIDAD",
  "status": "CONDITIONAL",
  "findings_reviewed": 12,
  "critical_issues": 0,
  "high_issues": 5,
  "reason": "High severity issues must be addressed"
}
```

---

## Integración con BAGO

### En code_quality_orchestrator.ps1

```powershell
# Después de ejecutar AGENTS, consultar ROLES
& "$BAGOPath\role_orchestrator.ps1" -AgentFindings $all -TargetPath $TargetPath
```

### En role_orchestrator.ps1

```powershell
function Invoke-SecurityReviewer {
    # Consulta REVISOR_SEGURIDAD con hallazgos
    # Retorna verdict (READY, CONDITIONAL, NOT_READY)
}

function Invoke-MAESTROBago {
    # Sintetiza verdicts de todos los roles
    # Retorna status final de producción-readiness
}
```

---

## Ejemplos de Roles Existentes

### MAESTRO_BAGO (Gobierno)
```
Propósito: Ser interfaz principal y presentar salida integrada
Alcance: Apertura/cierre conversacional, integración de resultados
Criterio: Salida clara, fiel al trabajo interno
```

### REVISOR_SEGURIDAD (Especialista)
```
Propósito: Evaluar si introduce exposición o riesgos
Alcance: Revisión de secretos, validación de permisos, análisis de exposición
Criterio: Issues de seguridad son clasificados correctamente
```

### REVISOR_PERFORMANCE (Especialista)
```
Propósito: Evaluar rendimiento y eficiencia
Alcance: Duplication, complejidad, recursos
Criterio: Performance issues son identificados y categorizados
```

### AUDITOR_CANONICO (Supervisión)
```
Propósito: Validar conformidad con canon BAGO
Alcance: Estructura, nomenclatura, criterios
Criterio: Trabajo sigue normas establecidas
```

---

## Extensión: Crear Nuevo Rol

### Paso 1: Crear usando Factory

```bash
python role_factory.py create --family especialistas --name "tester_qa"
```

### Paso 2: Completar Secciones (en `.bago/roles/especialistas/TESTER_QA.md`)

```markdown
# TESTER_QA

## Identidad
- id: role_especialistas_tester_qa
- family: especialistas
- version: 2.5-stable

## Propósito
Validar que los tests cubren casos críticos y riesgos identificados

## Alcance
- Revisión de cobertura de tests
- Validación de casos edge
- Evaluación de suites de regresión

## Límites
- No escribe tests
- No implementa fixes
- No valida funcionalidad

## Entradas
- Reporte de cobertura
- Issues identificadas por otros roles
- Código modificado

## Salidas
- Verdict de cobertura (ADEQUATE, INSUFFICIENT, EXCELLENT)
- Recomendación de test cases faltantes

## Activación
Después de REVISOR_SEGURIDAD y cuando hay cambios críticos

## No Activación
En cambios triviales o comentarios

## Dependencias
- REVISOR_SEGURIDAD
- Herramientas de cobertura (jest, nyc)

## Criterio de Éxito
Test suite cubre >80% de paths críticos
```

### Paso 3: Validar

```bash
python role_factory.py validate TESTER_QA.md
```

### Paso 4: Registrar

Automático en manifest.json cuando se valida

### Paso 5: Integrar en Orchestrador

En `role_orchestrator.ps1`:
```powershell
function Invoke-TesterQA {
    param([object]$Findings)
    # Tu lógica de validación
    return @{ role = "TESTER_QA"; status = "ADEQUATE" }
}
```

---

## Estructura de Archivos

```
.bago/
└── roles/
    ├── ROLE_TEMPLATE.md              ← Plantilla universal
    ├── role_factory.py               ← Factory (crea, valida, lista)
    ├── manifest.json                 ← Registry de roles
    ├── README.md                     ← Guía de roles
    ├── gobierno/                     ← Family 1: GOBIERNO
    │   ├── MAESTRO_BAGO.md
    │   └── ORQUESTADOR_CENTRAL.md
    ├── especialistas/                ← Family 2: ESPECIALISTAS
    │   ├── REVISOR_SEGURIDAD.md
    │   ├── REVISOR_PERFORMANCE.md
    │   ├── REVISOR_UX.md
    │   └── INTEGRADOR_REPO.md
    ├── supervision/                  ← Family 3: SUPERVISIÓN
    │   ├── AUDITOR_CANONICO.md
    │   ├── CENTINELA_SINCERIDAD.md
    │   └── VERTICE.md
    └── produccion/                   ← Family 4: PRODUCCIÓN
        ├── ANALISTA.md
        ├── ARQUITECTO.md
        ├── GENERADOR.md
        ├── ORGANIZADOR.md
        └── VALIDADOR.md
```

---

## Verdicts y Estatuses

Cada rol emite un **verdict** que es su evaluación:

```
READY           → Cumple todos los criterios
CONDITIONAL     → Cumple con condiciones/caveats
NOT_READY       → No cumple criterios
ESCALATE        → Requiere decisión humana
```

MAESTRO_BAGO sintetiza:
- Si ANY role = NOT_READY → Final = NOT_READY
- Si ANY role = CONDITIONAL → Final = CONDITIONAL
- Si ALL roles = READY → Final = READY

---

## Integración CI/CD

Los verdicts pueden:
1. **Bloquear merge** si NOT_READY
2. **Requerir review** si CONDITIONAL
3. **Pasar automático** si READY

```yaml
# GitHub Actions ejemplo
- name: BAGO Role Review
  run: |
    powershell .bago\code_quality_orchestrator.ps1 -TargetPath ${{ github.workspace }}
    if ($verdict -eq "NOT_READY") { exit 1 }
```

---

**Conclusión**: La fábrica de roles de BAGO proporciona un sistema extensible, validado y registrado para crear especialistas que gobiernan la calidad del código. Cada rol tiene responsabilidades claras, emite verdicts transparentes y se integra en el flujo de gobernanza.

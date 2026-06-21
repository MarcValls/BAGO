# PLANTILLA DE ROL BAGO

**Estructura canónica para definir cualquier rol especializado en BAGO**

Usa esta plantilla para crear roles nuevos. Cada sección es obligatoria.

---

## Identidad

```
- id: role_{familia}_{nombre}         ← Identificador único (snake_case)
- family: {government|specialist|supervision|production}
- version: 2.5-stable                 ← Versión de BAGO compatible
```

**Ejemplos:**
- `role_specialist_security_reviewer`
- `role_government_maestro_bago`
- `role_production_deployment_manager`

---

## Propósito

**Una frase clara:** ¿Qué hace este rol?

```
Ejemplo (Revisor Seguridad):
Evaluar si una propuesta, artefacto o flujo introduce exposición, 
fuga de datos, relajación de permisos o superficies innecesarias de riesgo.
```

---

## Alcance

**Lista de responsabilidades específicas** (qué ENTRA en su dominio)

```
- item1
- item2
- item3
```

**Ejemplos:**
- revisión de secretos
- validación de permisos
- análisis de exposición
- auditoria de datos

---

## Límites

**Lo que EXPLÍCITAMENTE NO hace** (qué se excluye)

```
- no reemplaza {otro_rol}
- no juzga {aspecto} excepto {condición}
```

**Ejemplos:**
- no reemplaza Auditor Canónico
- no juzga UX salvo impacto de seguridad

---

## Entradas

**Qué recibe este rol como input**

```
- input1 (descripción)
- input2 (descripción)
```

**Ejemplos:**
- artefacto (código, doc, config)
- flujo (workflow, proceso)
- contexto (requisitos, restricciones)

---

## Salidas

**Qué produce este rol como output**

```
- output1 (formato, descripción)
- output2 (formato, descripción)
```

**Ejemplos:**
- hallazgos de riesgo (lista, JSON, Markdown)
- recomendaciones (texto estructurado)
- veredicto (aceptación/rechazo/condicionado)

---

## Activación

**Cuándo se DEBE activar este rol** (condiciones de disparo)

```
Cuando [condición1] y [condición2]
```

**Ejemplos:**
- Cuando la tarea toca permisos, datos, credenciales
- Cuando hay cambios en infraestructura
- Cuando se modifica documentación crítica

---

## No Activación

**Cuándo se DEBE EVITAR** activar este rol (casos de exclusión)

```
No en [situación1]
No si [condición2]
```

**Ejemplos:**
- No en tareas puramente documentales sin riesgo
- No si el cambio es cosmético
- No si el contexto es local/experimental

---

## Dependencias

**Qué necesita este rol para funcionar**

```
- recurso1 (descripción)
- información2 (descripción)
```

**Ejemplos:**
- contexto técnico suficiente
- criterios de seguridad del proyecto
- acceso a repositorio o base de datos

---

## Criterio de Éxito

**Cómo medir si el rol funcionó bien**

```
✓ Condición 1
✓ Condición 2
```

**Ejemplos:**
- Identifica riesgos reales y evita falsos positivos
- Las recomendaciones son accionables
- El tiempo de respuesta es < 5 minutos

---

## Ejemplos de Roles Implementados

### Familia: GOVERNMENT (Gobierno de BAGO)

```
role_government_maestro_bago
  → Interfaz principal con usuario
  → Integra resultados
  → Explica siguiente paso

role_government_orquestador_central
  → Coordina especialistas
  → Toma decisiones de flujo
  → Maneja excepciones
```

### Familia: SPECIALIST (Especialistas)

```
role_specialist_security_reviewer
  → Evalúa riesgos de seguridad

role_specialist_performance_auditor
  → Analiza performance

role_specialist_ux_reviewer
  → Valida experiencia de usuario
```

### Familia: SUPERVISION (Supervisión)

```
role_supervision_calidad_verifiador
  → Verifica criterios de calidad
  → Audita proceso
```

### Familia: PRODUCTION (Producción)

```
role_production_deployment_manager
  → Gestiona despliegues
  → Maneja infraestructura
```

---

## Cómo Crear un Rol Nuevo

### 1. Copiar esta plantilla
```bash
cp .bago/roles/ROLE_TEMPLATE.md .bago/roles/{familia}/{NOMBRE_ROL}.md
```

### 2. Rellenar secciones
```bash
# Editar archivo
nano .bago/roles/{familia}/{NOMBRE_ROL}.md
```

### 3. Usar factory para registrar (opcional)
```bash
python .bago/roles/role_factory.py create \
  --family specialist \
  --name security_auditor \
  --file .bago/roles/especialistas/SECURITY_AUDITOR.md
```

### 4. Validar
```bash
python .bago/roles/role_factory.py validate SECURITY_AUDITOR.md
```

---

## Estructura de Directorio

```
.bago/roles/
├── ROLE_TEMPLATE.md              ← Esta plantilla
├── role_factory.py               ← Factory para crear/validar roles
├── manifest.json                 ← Registry de roles
│
├── especialistas/
│   ├── REVISOR_SEGURIDAD.md
│   ├── REVISOR_PERFORMANCE.md
│   ├── REVISOR_UX.md
│   └── INTEGRADOR_REPO.md
│
├── gobierno/
│   ├── MAESTRO_BAGO.md
│   └── ORQUESTADOR_CENTRAL.md
│
├── production/
│   ├── DEPLOYMENT_MANAGER.md
│   └── ...
│
└── supervision/
    ├── QUALITY_VERIFIER.md
    └── ...
```

---

## Familia de Roles

### GOVERNMENT
- **Propósito:** Gobierno central de BAGO
- **Responsabilidades:** Decisiones arquitectónicas, orquestación, interfaz usuario
- **Ejemplos:** Maestro, Orquestador Central

### SPECIALIST (Especialistas)
- **Propósito:** Análisis profundo en dominio específico
- **Responsabilidades:** Validación, auditoría, revisión técnica
- **Ejemplos:** Revisor Seguridad, Performance, UX

### SUPERVISION (Supervisión)
- **Propósito:** Verificación de calidad y proceso
- **Responsabilidades:** Auditoría, compliance, calidad
- **Ejemplos:** Quality Verifier, Compliance Officer

### PRODUCTION (Producción)
- **Propósito:** Operaciones y despliegue
- **Responsabilidades:** Infraestructura, releases, monitoring
- **Ejemplos:** Deployment Manager, Incident Commander

---

## Checklist para Validar Rol

- [ ] ID único en formato `role_{familia}_{nombre}`
- [ ] Propósito claro en una frase
- [ ] Alcance específico (4-6 items)
- [ ] Límites explícitos
- [ ] Entradas definidas
- [ ] Salidas esperadas
- [ ] Activación clara
- [ ] No-activación clara
- [ ] Dependencias realistas
- [ ] Criterios de éxito medibles

---

**Version:** 1.0  
**Creado:** 2026-04-28  
**Status:** Template Activo

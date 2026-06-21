# W7 · FOCO DE SESIÓN

## id

`w7_foco_sesion`

---

**Código:** W7_FOCO_SESION  
**Propósito:** Arrancar una sesión de trabajo con objetivo único, roles mínimos y artefactos pre-declarados. Diseñado para mejorar las métricas de Producción de artefactos y Foco de sesión.  
**Cuándo usarlo:** Siempre que el objetivo sea concreto y acotado (no bootstrap ni evaluación abierta). Preferir sobre W1 en sesiones productivas normales.  
**Prerequisito:** Pack en estado GO · Escenario ESCENARIO-001 activo  

---

## Secuencia obligatoria

### PASO 0 · Ejecutar preflight (antes del PASO 1)

```bash
python3 tools/session_preflight.py \
  --objetivo "..." \
  --roles "role_principal[,role_apoyo]" \
  --artefactos "ruta1,ruta2,ruta3" \
  --task-type system_change
```

Si devuelve `KO`: corregir según indicaciones antes de continuar. No abrir sesión con preflight fallido.

---

### PASO 1 · Declarar el objetivo único (2 min)

Completar esta frase antes de abrir la sesión:

> **"En esta sesión voy a [VERBO] [OBJETO] para que [CRITERIO DE DONE]."**

Ejemplos válidos:
- "Voy a **crear** la guía de onboarding para que cualquier nuevo colaborador pueda arrancar el pack en < 10 min."
- "Voy a **corregir** el bug en `compute_evolution()` para que el radar muestre valores reales al recargar."
- "Voy a **actualizar** `global_state.json` para que el inventario cuadre con los archivos reales."

❌ No válido: "Voy a revisar cosas del pack y mejorar lo que haga falta."

---

### PASO 2 · Seleccionar máximo 2 roles

| Necesito... | Rol principal | ¿Rol de apoyo? |
|-------------|--------------|----------------|
| Crear/modificar arquitectura | `role_architect` | `role_validator` si hay validación |
| Auditar estado o coherencia | `role_auditor` | `role_organizer` si hay que actualizar estado |
| Ejecutar una tarea operativa | `role_executor` | — |
| Cerrar una sesión o sprint | `role_organizer` | `role_vertice` si hay revisión |
| Análisis de datos/métricas | `role_auditor` | — |

Si necesitas más de 2 roles: **la sesión tiene demasiado scope → dividirla**.

---

### PASO 3 · Pre-declarar artefactos (antes de tocar nada)

Listar **mínimo 3 archivos concretos** que existirán al cerrar la sesión:

```
artifacts_planned:
  1. <ruta/al/archivo1.md>   — [descripción en 1 línea]
  2. <ruta/al/archivo2.json> — [descripción en 1 línea]
  3. <ruta/al/archivo3.ext>  — [descripción en 1 línea]
```

Regla: el JSON de sesión **no cuenta**. Solo cuentan archivos que aporten valor fuera del protocolo.

**Plantillas disponibles** (para producción rápida):
- `docs/operation/templates/tpl_system_change.md` — sesiones de cambio
- `docs/operation/templates/tpl_analysis.md` — sesiones de análisis
- `docs/operation/templates/tpl_sprint.md` — sesiones de sprint

**Meta por sesión:** ≥4 artefactos útiles. Ver `docs/operation/GUIA_ARTEFACTOS.md` para más estrategias.

---

### PASO 4 · Ejecutar

Trabajar únicamente en el objetivo declarado en PASO 1.  
Si aparece trabajo no planificado: **anotarlo en `decisions` como "emergente"** y abrir sesión nueva para ello.

---

### PASO 5 · Cierre y verificación

Antes de cerrar la sesión, verificar:

```
[ ] El objetivo del PASO 1 está cumplido
[ ] Se entregaron ≥ 3 artefactos pre-declarados (meta real: ≥ 4)
[ ] Se usaron ≤ 2 roles
[ ] validate_pack.py → GO
[ ] El campo `artifacts` del JSON de sesión coincide con los pre-declarados
```

**Medir producción:**
```bash
python3 tools/artifact_counter.py -n 1 -v
```

Si algún punto falla: documentarlo en `decisions` con causa y siguiente paso.

---

## Anti-patrones a evitar

| Anti-patrón | Señal de alarma | Corrección |
|-------------|-----------------|------------|
| Scope drift | El objetivo cambió durante la sesión | Abrir sesión nueva para el nuevo objetivo |
| Roles por defecto | Se activaron todos los roles "por si acaso" | Revisar qué rol realmente tomó decisiones |
| Artefactos de protocolo | Solo hay JSON de sesión y cambio | Preguntar: ¿qué queda en el repo que no sea overhead? |
| Sesión mega | La sesión tiene 8+ artefactos de tipos muy distintos | Dividir en sesiones especializadas |

---

## Métrica de éxito del workflow

El W7 está funcionando si, tras 5 sesiones:
- Media de roles/sesión ≤ 2.0
- Media de artefactos/sesión ≥ 4.0
- 0 sesiones con objetivo sin cumplir

Ver medición en `state/scenarios/ESCENARIO-MEJORA-ARTEFACTOS-FOCO.md § 6`.

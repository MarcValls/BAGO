# Workflows · BAGO

Este directorio contiene los workflows tácticos y el workflow maestro.

## Discrepancia conocida: contrato vs realidad (INC-001)

El contrato canónico `core/canon/CONTRATOS/contrato_workflow.md` exige **10 campos**
obligatorios para todo workflow:

1. id
2. objetivo
3. cuándo usarlo
4. roles mínimos
5. entradas
6. fases
7. salidas
8. escalado
9. incidencia típica
10. criterio de cierre

Los workflows reales de este directorio **NO cumplen** ese esquema. Usan un formato
más ligero (título, id, objetivo, secuencia/flujo, criterio de salida) que prioriza
legibilidad sobre estructura rígida.

| Campo canónico | Presente en workflows reales |
|----------------|---------------------------|
| id | ✅ Sí |
| objetivo | ✅ Sí |
| cuándo usarlo | ⚠️ A veces implícito en el título |
| roles mínimos | ❌ No |
| entradas | ❌ No |
| fases | ✅ Sí (como "Secuencia" o "Flujo") |
| salidas | ⚠️ A veces implícito |
| escalado | ❌ No |
| incidencia típica | ❌ No |
| criterio de cierre | ✅ Sí (como "Criterio de salida") |

> **Decisión pendiente**: Adaptar el contrato canónico al formato real, o migrar
> todos los workflows a un esquema JSON/YAML que cumpla el contrato.

## Índice de workflows

| Workflow | id | Propósito |
|----------|----|-----------|
| [W1_COLD_START](W1_COLD_START.md) | `w1_cold_start` | Arrancar desde repo desconocido |
| [W2_IMPLEMENTACION_CONTROLADA](W2_IMPLEMENTACION_CONTROLADA.md) | `w2_implementacion_controlada` | Implementar sin pérdida de trazabilidad |
| [W3_REFACTOR_SENSIBLE](W3_REFACTOR_SENSIBLE.md) | `w3_refactor_sensible` | Refactorizar sin romper contratos |
| [W4_DEBUG_MULTICAUSA](W4_DEBUG_MULTICAUSA.md) | `w4_debug_multicausa` | Diagnosticar fallos multi-causa |
| [W5_CIERRE_Y_CONTINUIDAD](W5_CIERRE_Y_CONTINUIDAD.md) | `w5_cierre_y_continuidad` | Cerrar sesión con continuidad |
| [W6_IDEACION_APLICADA](W6_IDEACION_APLICADA.md) | `w6_ideacion_aplicada` | Ideas concretas priorizadas |
| [W7_FOCO_SESION](W7_FOCO_SESION.md) | `w7_foco_sesion` | Sesión productiva normal |
| [W8_EXPLORACION](W8_EXPLORACION.md) | `w8_exploracion` | Exploración ligera |
| [W9_COSECHA](W9_COSECHA.md) | `w9_cosecha` | Cosecha post-exploración |
| [W10_AUDITORIA_SINCERIDAD](W10_AUDITORIA_SINCERIDAD.md) | `w10_auditoria_sinceridad` | Auditoría de sinceridad |
| [W0_FREE_SESSION](W0_FREE_SESSION.md) | `w0_free_session` | Control off/BAGO-off |
| [WORKFLOW_MAESTRO_BAGO](WORKFLOW_MAESTRO_BAGO.md) | `workflow_maestro_bago` | Ruta maestra global |

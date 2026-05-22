# W8 · Sesión de Exploración

## id
`w8_exploracion`

**Tipo:** workflow-lite  
**Uso:** sesiones sin objetivo concreto previo — explorar el pack, auditar estado, buscar qué mejorar  
**Cuándo usar:** cuando no sabes exactamente qué vas a cambiar pero sí quieres hacer algo útil  
**Cuándo NO usar:** si ya tienes un objetivo concreto → usar W7_FOCO_SESION

---

## Diferencia con W7 y W0

| | W7 (foco) | W8 (exploración) | W0 (libre/control) |
|---|:---:|:---:|:---:|
| Preflight obligatorio | ✅ | ✅ mínimo | ❌ |
| Objetivo declarado | ✅ concreto | 📋 área de interés | ❌ |
| Artefactos planificados | ≥3 obligatorio | ≥1 orientativo | ❌ |
| Roles máximos | 2 | 2 | libre |
| Decisiones esperadas | ≥2 | ≥1 | — |
| Para ESCENARIO-002 | grupo ON | — | grupo OFF |

---

## PASO 0 — Preflight mínimo

```bash
python3 .bago/tools/validate_pack.py   # debe ser GO
python3 .bago/tools/pack_dashboard.py  # leer estado de producción
```

Si KO → resolver antes de continuar.

---

## PASO 1 — Declarar área de exploración

En el JSON de sesión:
```json
{
  "session_id": "SES-W8-YYYY-MM-DD-001",
  "task_type": "analysis",
  "selected_workflow": "w8_exploracion",
  "user_goal": "<área: e.g. 'explorar gaps en documentación operativa'>",
  "artifacts_planned": ["<al menos un artefacto orientativo>"],
  "roles_activated": ["role_auditor"]
}
```

**El área de exploración puede quedar abierta** — no es necesario saber el artefacto exacto.  
Al cerrar, declarar lo que realmente se creó.

---

## PASO 2 — Explorar y decidir

1. Leer `state/global_state.json` y `docs/analysis/INFORME_EFICACIA_WORKFLOWS.md`
2. Identificar el gap más concreto con más valor
3. **Convertirlo en un objetivo accionable** — si el gap es claro, abrirlo como sesión W7

Si durante la exploración encuentras algo accionable:
- **Pequeño** (≤30 min): resolverlo en esta misma sesión W8
- **Mediano/grande**: documentarlo y abrir sesión W7 nueva

---

## PASO 3 — Producir ≥1 artefacto útil

W8 exige al menos 1 artefacto de valor real al cierre:

| Tipo | Ejemplos válidos |
|------|-----------------|
| Hallazgo | `state/evaluations/EVAL-XXX.md` con gap identificado + recomendación |
| Fix pequeño | corrección de artefacto stale |
| Documentación | sección nueva en doc existente |
| Herramienta | script pequeño de diagnóstico |

**No válido:** nota genérica sin acción ni decisión.

---

## PASO 4 — Cierre

```
✅ ≥1 artefacto útil real
✅ ≥1 decisión documentada (lo que descubriste o decidiste)
✅ status: "closed"
✅ validate_pack GO
```

Ver procedimiento completo: `docs/governance/PROTOCOLO_CIERRE_SESION.md`

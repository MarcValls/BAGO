# Auditoría de estados BAGO · 2026-07-17

## Resultado ejecutivo

- `falta cerrar` **no aparece** en superficies operativas auditadas (UI activa, contratos y canon operativo).
- La ambigüedad actual no viene de ese literal, sino de mezclar estados de dominios distintos bajo etiquetas genéricas como `pending` o `partial`.
- Se detectó una incoherencia documental: se referenciaba `docs/contracts/bago_v4_pipeline_contract.md` como fuente vigente. En este árbol el contenido equivalente también estaba presente en `docs/contracts/workspace_seed_contract/`, así que el riesgo era de espejo/ruta y no de ausencia total.

## Evidencia revisada

1. Canon taxonómico y contratos legacy:
   - `.bago/core/canon/TAXONOMIA.md`
   - `.bago/core/canon/CONTRATOS/README.md`
   - `.bago/core/canon/CONTRATOS/contrato_workflow.md`
2. Contratos operativos v4:
   - `docs/contracts/README.md`
   - `docs/contracts/bago_v4_runtime_contract.json`
   - `docs/contracts/bago_v4_pipeline_contract.md`
   - `docs/contracts/workspace_seed_contract/bago_v4_pipeline_contract.md`
3. UI activa y única fuente canónica (`frontend/src`):
   - `shared/quiet-status.ts`
   - `layout/ChatPanel.tsx`
   - `features/sections.tsx`
   - `contracts/backend.ts`

## Hallazgos

### 1) Estados canónicos existentes están separados por dominio

- Pipeline: `pending`, `running`, `done`, `failed`, `blocked`.
- Sesión: `created`, `loaded`, `in_progress`, `blocked`, `awaiting_validation`, `completed`, `closed`.
- Bootstrap/contexto/modelo/proyecto usan otros sets (`confirmed`, `partial`, `stale`, `valid`, `recoverable`, etc.).

Conclusión: la base canónica ya evita `falta cerrar`, pero no explicita una capa única de madurez de implementación.

### 2) Ambigüedad funcional en UI

La UI traduce estados heterogéneos con una misma lógica de tono/etiqueta:

- `quiet-status.ts`: muestra `pending -> Pendiente`, `partial -> Parcial`.
- `ChatPanel.tsx` y `sections.tsx`: agrupan `running/pending/partial/stale` en la misma familia visual.

Conclusión: dos estados con semántica distinta pueden verse casi iguales para la gestión.

### 3) Incoherencia de fuente de verdad contractual

Varios documentos apuntan a `docs/contracts/bago_v4_pipeline_contract.md` como referencia vigente.
La ruta principal existe ahora, pero el auditor debe seguir vigilando espejos para evitar divergencia futura.

Acción tomada en esta auditoría:

- Se mantuvo `docs/contracts/bago_v4_pipeline_contract.md` como referencia principal y se conservó el espejo en `workspace_seed_contract` como material de legado/seed.

## Regla operativa propuesta para BAGO

Mantener los estados técnicos actuales por dominio, y añadir una dimensión explícita de madurez de implementación para gestión:

- `No iniciado`
- `En implementación`
- `Implementado parcialmente`
- `Implementado y pendiente de integración`
- `Integrado y pendiente de validación`
- `Validado`
- `Canonizado`

## Criterios de paso (resumen)

1. `No iniciado -> En implementación`: hay trabajo activo en curso.
2. `En implementación -> Implementado parcialmente`: existe código pero cobertura incompleta.
3. `Implementado parcialmente -> Implementado y pendiente de integración`: construcción funcional completa del alcance local.
4. `Implementado y pendiente de integración -> Integrado y pendiente de validación`: integración cableada con superficies dependientes.
5. `Integrado y pendiente de validación -> Validado`: validación completada con evidencia.
6. `Validado -> Canonizado`: aprobado como referencia oficial.

## Representación recomendada

### Backend

- No reutilizar `status` genérico para esto.
- Añadir campo específico, por ejemplo `implementation_state`.
- Mantener `status/state` actual para runtime técnico.

### UI

- Mostrar siempre el dominio del estado (ej. `Pipeline`, `Contexto`, `Implementación`).
- Para gestión, usar etiqueta textual exacta de `implementation_state`, sin traducirla a `pending/partial`.

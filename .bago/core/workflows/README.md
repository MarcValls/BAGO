# Workflows Canónicos · BAGO

Este directorio contiene los workflows canónicos que definen el comportamiento
estructurado del framework.

## Estado de cumplimiento del contrato

El contrato canónico [`core/canon/CONTRATOS/contrato_workflow.md`](../canon/CONTRATOS/contrato_workflow.md) exige **10 campos**:

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

### Workflow compliance audit

| Workflow | id | objetivo | cuándo | roles | entradas | fases | salidas | escalado | incidencia | cierre |
|----------|:--:|:--------:|:------:|:-----:|:--------:|:-----:|:-------:|:--------:|:----------:|:------:|
| workflow_analisis.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| workflow_bootstrap_repo_first.md | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ |
| workflow_cambio_sistemico.md | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ |
| workflow_cross_learning.md | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ |
| workflow_diseno.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| workflow_ejecucion.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| workflow_migracion_historial.md | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ |
| workflow_validacion.md | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |

> **Observación**: Ningún workflow incluye la sección `escalado`. Esto es una
gap consistente que debería resolverse en una futura revisión del contrato
o de los workflows.

## Índice

| Workflow | id | Propósito |
|----------|----|-----------|
| [workflow_analisis](workflow_analisis.md) | `workflow_analysis` | Comprender antes de actuar |
| [workflow_diseno](workflow_diseno.md) | `workflow_design` | Diseñar con trazabilidad |
| [workflow_ejecucion](workflow_ejecucion.md) | `workflow_execution` | Ejecutar con control |
| [workflow_validacion](workflow_validacion.md) | `workflow_validation` | Validar antes de cerrar |
| [workflow_cambio_sistemico](workflow_cambio_sistemico.md) | `workflow_system_change` | Cambios que afectan al framework |
| [workflow_migracion_historial](workflow_migracion_historial.md) | `workflow_history_migration` | Migrar historia sin pérdida |
| [workflow_bootstrap_repo_first](workflow_bootstrap_repo_first.md) | `workflow_bootstrap_repo_first` | Primer contacto con un repo |
| [workflow_cross_learning](workflow_cross_learning.md) | `workflow_cross_learning` | Aprendizaje entre sesiones |

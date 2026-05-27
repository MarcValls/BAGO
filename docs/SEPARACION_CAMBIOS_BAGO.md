# Separación de Cambios BAGO

Este documento divide el árbol en bloques para decidir qué entra en un commit y qué no.

## 1. Cambios de código

Estos archivos son lógica o integración. Si el commit es de producto/runtime, son candidatos reales.

- [`.bago/tools/bago/ui.py`](../.bago/tools/bago/ui.py)
- [`.bago/tools/cosecha.py`](../.bago/tools/cosecha.py)
- [`.bago/tools/smoke_runner.py`](../.bago/tools/smoke_runner.py)
- [`.bago/tools/validate_pack.py`](../.bago/tools/validate_pack.py)
- [`.bago/tools/_registry_entries_core.py`](../.bago/tools/_registry_entries_core.py)
- [`bago_core/installer.py`](../bago_core/installer.py)
- [`bago_core/launcher.py`](../bago_core/launcher.py)
- [`install.ps1`](../install.ps1)
- [`smoke-test.ps1`](../smoke-test.ps1)

### Lectura práctica

- Si el objetivo es runtime estable, estos son los cambios que importan.
- Si el objetivo es limpiar estado, no tocar más lógica hasta separar el resto.

## 2. Estado generado

Estos archivos son memoria o salida del runtime. Normalmente no deben mezclarse con un commit de código salvo que el commit sea precisamente sobre estado.

- [`.bago/state/global_state.json`](../.bago/state/global_state.json)
- [`.bago/state/benchmark_last.json`](../.bago/state/benchmark_last.json)
- [`.bago/state/canon_log.json`](../.bago/state/canon_log.json)
- [`.bago/state/pending_w2_task.json`](../.bago/state/pending_w2_task.json)
- [`.bago/state/recent_projects.json`](../.bago/state/recent_projects.json)
- [`.bago/state/self_state.json`](../.bago/state/self_state.json)
- [`.bago/state/sprint_plan.json`](../.bago/state/sprint_plan.json)
- [`.bago/state/sprint_summary_07.md`](../.bago/state/sprint_summary_07.md)
- [`.bago/state/changes/BAGO-CHG-001.json`](../.bago/state/changes/BAGO-CHG-001.json)
- [`.bago/state/evidences/BAGO-EVD-001.json`](../.bago/state/evidences/BAGO-EVD-001.json)
- [`.bago/state/sac_locks/`](../.bago/state/sac_locks/)
- [`.bago/sandbox/`](../.bago/sandbox/)

### Lectura práctica

- Si el commit busca ser limpio, esto debería ir fuera.
- Si el commit busca fijar una sesión o una cosecha, entonces se decide explícitamente.

## 3. Documentación nueva

Estos archivos son útiles, pero conviene separarlos del runtime si quieres un commit técnico limpio.

- [`docs/BAGO_CANON.md`](../docs/BAGO_CANON.md)
- [`docs/MAPA_MENTAL_BAGO_DETALLADO.md`](../docs/MAPA_MENTAL_BAGO_DETALLADO.md)
- [`docs/MAPA_MENTAL_BAGO_ASCII.md`](../docs/MAPA_MENTAL_BAGO_ASCII.md)
- [`docs/RETOMA_RAPIDA_BAGO.md`](../docs/RETOMA_RAPIDA_BAGO.md)
- [`docs/RETOMA_HOY_3_PASOS.md`](../docs/RETOMA_HOY_3_PASOS.md)
- [`docs/SEPARACION_CAMBIOS_BAGO.md`](../docs/SEPARACION_CAMBIOS_BAGO.md)
- [`docs/PLANTILLA_EVALUACION_BRUTAL_BAGO.md`](../docs/PLANTILLA_EVALUACION_BRUTAL_BAGO.md)
- [`docs/operation/GUIA_DE_USO.md`](../docs/operation/GUIA_DE_USO.md)
- [`docs/operation/INSTALACION.md`](../docs/operation/INSTALACION.md)
- [`docs/governance/PROTOCOLO_CIERRE_SESION.md`](../docs/governance/PROTOCOLO_CIERRE_SESION.md)
- [`docs/governance/REGLA_INMUTABILIDAD_VALIDACION.md`](../docs/governance/REGLA_INMUTABILIDAD_VALIDACION.md)
- [`docs/runtime_contract.json`](../docs/runtime_contract.json)
- [`runtime_contract.json`](../runtime_contract.json)
- [`INICIO_RAPIDO_PORTABLE.md`](../INICIO_RAPIDO_PORTABLE.md)
- [`SIMULACION_MAC.md`](../SIMULACION_MAC.md)
- [`SIMULACION_WINDOWS.md`](../SIMULACION_WINDOWS.md)
- [`make-portable.ps1`](../make-portable.ps1)
- [`bago.sh`](../bago.sh)

### Lectura práctica

- Si haces un commit de documentación, este bloque tiene sentido.
- Si haces un commit de runtime, revisa si de verdad quieres mezclar docs nuevas.

## 4. Ruido / revisar antes de tocar

Estos archivos aparecen en el árbol y conviene decidir caso por caso.

- [`AGENTS.md`](../AGENTS.md)
- [`.bago/docs/`](../.bago/docs/)
- [`state.example/`](../state.example/)
- [`docs/`](../docs/)

### Lectura práctica

- No asumir que todo lo que aparece aquí debe ir al commit.
- Algunos son fuentes canónicas, otros son espejos, otros son soporte.

## 5. Reglas de separación

### Si el objetivo es limpiar

- No mezclar `state/` con `bago_core/`.
- No mezclar documentación con correcciones de encoding o launcher.
- No mezclar datos de sesión con refactors de código.

### Si el objetivo es entregar funcionalidad

- Cambios de runtime primero.
- Estado generado fuera salvo que sea parte de la feature.
- Docs solo si explican la feature nueva.

### Si el objetivo es retomar trabajo sin perderte

- Un commit por frente.
- Un árbol de verdad.
- Un criterio explícito para el estado generado.

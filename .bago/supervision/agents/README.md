# Agentes de supervisión · BAGO

Este directorio (`\.bago\supervision\agents\`) contiene las definiciones declarativas de los agentes de supervisión autónoma.

## Agentes registrados

| Agente | Rol | Misión | Loop asociado |
|--------|-----|--------|---------------|
| `contract_auditor` | GUIA_VERTICE | Mantener coherencia del registry | `contract_drift_loop` |
| `dangerous_command_agent` | — | Vigilar comandos peligrosos | — |
| `doc_sync_agent` | — | Sincronizar docs con código | `contract_drift_loop` |
| `legacy_migration_agent` | — | Gestionar migraciones legado | — |
| `release_guardian` | — | Proteger releases | `contract_drift_loop` |
| `state_sandbox_agent` | — | Validar estado en sandbox | — |

## Esquema mínimo

```json
{
  "agent": "nombre_agente",
  "version": "1.0.0",
  "role": "ROL_BAGO",
  "mission": "Descripción clara de la misión",
  "reads": [],
  "writes": [],
  "tools": [],
  "gate": "condición de éxito cuantificable",
  "on_failure": "warn|block|auto_heal",
  "loop": "loop_asociado",
  "sense": "comando de sensado",
  "plan": "plan de acción",
  "act": "acción a ejecutar",
  "observe": "comando de observación",
  "learn": "comando de aprendizaje"
}
```

## Regla

Un agente de supervisión nunca modifica código directamente sin paso por el `loop` y el `orquestador`.

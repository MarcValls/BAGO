# Supervisión · BAGO

Este directorio (`\.bago\supervision\`) contiene el sistema de supervisión autónoma del framework: agentes especializados, artefactos de auditoría, hooks de ciclo de vida y loops de control continuo.

## Subdirectorios

| Directorio | Contenido | Ejemplo / Placeholder |
|------------|-----------|----------------------|
| `agents/` | Agentes de supervisión especializados (JSON) | `contract_auditor.agent.json` |
| `artifacts/` | Artefactos generados por la supervisión | `VERSION_CONTRACT.json`, `REGISTRY_CONTRACT_AUDIT.json` |
| `hooks/` | Hooks de pre/post-commit o pre/post-release | `pre-commit.sh` |
| `loops/` | Definiciones de loops de supervisión continua | `contract_drift_loop.json` |

## Agente de supervisión

Cada agente es un archivo `.agent.json` con la siguiente estructura:

```json
{
  "agent": "nombre_del_agente",
  "version": "1.0.0",
  "role": "ROL_ASIGNADO",
  "mission": "Descripción de la misión",
  "reads": ["ruta/entrada/1", "ruta/entrada/2"],
  "writes": ["ruta/salida/1"],
  "tools": ["tool_1.py", "tool_2.py"],
  "gate": "condición de éxito",
  "on_failure": "warn|block|auto_heal",
  "loop": "nombre_del_loop",
  "sense": "comando de sensado",
  "plan": "plan de acción",
  "act": "acción a ejecutar",
  "observe": "comando de observación",
  "learn": "comando de aprendizaje"
}
```

## Loop de supervisión

Cada loop es un archivo `.json` que orquesta agentes en secuencia:

```json
{
  "loop": "nombre_del_loop",
  "version": "1.0.0",
  "description": "Qué hace el loop",
  "trigger": "manual or scheduled",
  "mode": "advisory|enforcing",
  "agents": [
    {"agent": "agente_1", "order": 1, "on_failure": "warn"},
    {"agent": "agente_2", "order": 2, "on_failure": "block"}
  ],
  "exit_code_on_block": 0,
  "report_artifact": ".bago/state/contracts/resultado.json"
}
```

## Regla

Los agentes y loops son **declarativos**: describen qué vigilar, no cómo hacerlo. La implementación vive en `tools/` y es invocada por los comandos `sense`/`act`.

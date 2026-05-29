# Loops de supervisión · BAGO

Este directorio (`\.bago\supervision\loops\`) contiene las definiciones de loops de control continuo.

## Loops registrados

| Loop | Descripción | Modo |
|------|-------------|------|
| `contract_drift_loop` | Detecta deriva en contratos, registry, docs y versiones | advisory |
| `legacy_decay_loop` | Monitorea degradación de componentes legacy | advisory |
| `post_test_cleanup_loop` | Limpieza post-ejecución de tests | enforcing |
| `pre_release_loop` | Validaciones previas a release | block |

## Esquema mínimo

```json
{
  "loop": "nombre_loop",
  "version": "1.0.0",
  "description": "Qué vigila este loop",
  "trigger": "manual|scheduled|event",
  "mode": "advisory|enforcing|block",
  "agents": [
    {"agent": "agente_1", "order": 1, "on_failure": "warn"}
  ],
  "exit_code_on_block": 0,
  "report_artifact": ".bago/state/supervision/resultado.json"
}
```

## Regla

Los loops son **secuenciales**: cada agente espera al anterior. Si un agente falla y `on_failure` es `block`, el loop se detiene.
